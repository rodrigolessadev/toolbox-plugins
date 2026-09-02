"""
Testes unitários para integração e sincronização direta com arquivos KeePass (.kdbx) - Issue #217.
Valida:
1. Persistência de fontes KDBX no SQLite Central (SafeDatabase / plugin_safe_external_kdbx_sources).
2. Leitura, validação de credenciais e parsing de KDBX (KdbxReader).
3. Importação em lote e tratamento de conflitos no SafeService.
4. Exposição correta de endpoints na API Bridge do SafePluginApi.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pykeepass

from plugins.safe.db import SafeDatabase
from plugins.safe.kdbx_reader import KdbxReader, KdbxReaderError, KdbxAuthenticationError, KdbxNotFoundError
from plugins.safe.service import SafeService
from plugins.safe.main import SafePluginApi


@pytest.fixture
def temp_kdbx_file():
    """Gera um arquivo KDBX temporário válido com entradas de teste via pykeepass."""
    fd, path = tempfile.mkstemp(suffix=".kdbx")
    os.close(fd)
    kdbx_path = Path(path)

    # Cria database com senha 'mypassword123'
    kp = pykeepass.create_database(str(kdbx_path), password="mypassword123")
    group = kp.add_group(kp.root_group, "Producao")
    kp.add_entry(
        group,
        title="AWS Console",
        username="admin_cloud",
        password="secret_aws_password_999",
        url="https://console.aws.amazon.com",
        notes="Conta principal de produção",
        tags=["cloud", "aws"],
    )
    kp.add_entry(
        kp.root_group,
        title="Database Postgres",
        username="pg_user",
        password="pg_secure_password_456",
        url="postgres://db.internal:5432",
        notes="Banco relacional interno",
        tags=["db"],
    )
    kp.save()

    yield kdbx_path

    if kdbx_path.exists():
        try:
            kdbx_path.unlink()
        except Exception:
            pass


@pytest.fixture
def temp_safe_db():
    """Gera uma base SafeDatabase isolada em arquivo temporário."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_path = Path(path)

    db = SafeDatabase(db_path=db_path)
    yield db

    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass


def test_safe_db_kdbx_sources_crud(temp_safe_db):
    """Valida cadastro, leitura, listagem e remoção de fontes KDBX no SafeDatabase."""
    # 1. Cadastra fonte local
    src = temp_safe_db.add_kdbx_source(
        source_id="src_1",
        name="Cofre Principal",
        file_path="C:\\vaults\\main.kdbx",
        source_type="local",
        keyfile_path="C:\\vaults\\main.key",
    )
    assert src["id"] == "src_1"
    assert src["name"] == "Cofre Principal"
    assert src["source_type"] == "local"
    assert src["file_path"] == "C:\\vaults\\main.kdbx"
    assert src["keyfile_path"] == "C:\\vaults\\main.key"

    # 2. Cadastra fonte SSH
    temp_safe_db.add_kdbx_source(
        source_id="src_2",
        name="Servidor Remoto",
        file_path="/var/secure/remote.kdbx",
        source_type="ssh",
        ssh_host="192.168.1.50",
        ssh_port=2222,
        ssh_user="sysadmin",
    )

    # 3. Listagem
    sources = temp_safe_db.list_kdbx_sources()
    assert len(sources) == 2
    names = [s["name"] for s in sources]
    assert "Cofre Principal" in names
    assert "Servidor Remoto" in names

    # 4. Atualização de sync
    assert temp_safe_db.update_kdbx_source_last_sync("src_1") is True
    src_updated = temp_safe_db.get_kdbx_source("src_1")
    assert src_updated["last_sync_at"] is not None

    # 5. Exclusão
    assert temp_safe_db.delete_kdbx_source("src_2") is True
    assert len(temp_safe_db.list_kdbx_sources()) == 1


def test_kdbx_reader_validation_and_read(temp_kdbx_file):
    """Valida teste de credenciais e extração completa de entradas via KdbxReader."""
    # Senha incorreta
    ok, msg = KdbxReader.test_kdbx_credentials(temp_kdbx_file, password="wrongpassword")
    assert ok is False
    assert "incorreto" in msg.lower() or "falha" in msg.lower()

    # Senha correta
    ok, msg = KdbxReader.test_kdbx_credentials(temp_kdbx_file, password="mypassword123")
    assert ok is True
    assert "sucesso" in msg.lower()

    # Leitura de todas as entradas
    entries = KdbxReader.read_entries(temp_kdbx_file, password="mypassword123")
    assert len(entries) == 2

    aws_entry = next((e for e in entries if e["title"] == "AWS Console"), None)
    assert aws_entry is not None
    assert aws_entry["username_or_key"] == "admin_cloud"
    assert aws_entry["password"] == "secret_aws_password_999"
    assert aws_entry["url"] == "https://console.aws.amazon.com"
    assert aws_entry["metadata"]["group"] == "Producao"
    assert "Producao" in aws_entry["tags"]

    # Busca filtrada
    filtered = KdbxReader.read_entries(temp_kdbx_file, password="mypassword123", search_query="postgres")
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Database Postgres"


def test_safe_service_kdbx_import(temp_safe_db, temp_kdbx_file):
    """Valida fluxo completo no SafeService: leitura, desbloqueio e importação de entradas."""
    service = SafeService(db=temp_safe_db)
    service.setup_vault(password="vaultmasterpass", use_hello=False)

    # Cadastra fonte KDBX
    src = service.add_kdbx_source(
        name="Teste KDBX",
        file_path=str(temp_kdbx_file),
    )
    assert src["id"].startswith("kdbx_src_")

    # Lê entradas via serviço
    entries = service.read_kdbx_entries(src["id"], password="mypassword123")
    assert len(entries) == 2

    # Importa entradas para o Cofre Central
    res = service.import_kdbx_entries_to_vault(entries, conflict_policy="skip")
    assert res["success"] is True
    assert res["imported"] == 2

    # Confere se os segredos estão persistidos e acessíveis no cofre
    vault_secrets = service.list_secrets()
    assert len(vault_secrets) == 2
    titles = [s["title"] for s in vault_secrets]
    assert "AWS Console" in titles
    assert "Database Postgres" in titles

    # Importação repetida com política 'skip' não duplica
    res2 = service.import_kdbx_entries_to_vault(entries, conflict_policy="skip")
    assert res2["skipped"] == 2
    assert len(service.list_secrets()) == 2


def test_safe_plugin_api_kdbx_bridge(temp_safe_db, temp_kdbx_file):
    """Valida as chamadas JS Bridge expostas na API SafePluginApi."""
    api = SafePluginApi(db=temp_safe_db)
    setup_res = api.setup_vault(password="vaultpassword123", use_hello=False)
    assert setup_res["success"] is True

    # 1. Salvar fonte
    save_res = api.save_kdbx_source(
        name="Meu KDBX Bridge",
        file_path=str(temp_kdbx_file),
    )
    assert save_res["success"] is True
    source_id = save_res["data"]["id"]

    # 2. Listar fontes
    list_res = api.list_kdbx_sources()
    assert list_res["success"] is True
    assert len(list_res["data"]) == 1

    # 3. Testar fonte
    test_res = api.test_kdbx_source(source_id, password="mypassword123")
    assert test_res["success"] is True

    # 4. Ler entradas
    read_res = api.read_kdbx_entries(source_id, password="mypassword123")
    assert read_res["success"] is True
    assert read_res["count"] == 2

    # 5. Importar
    imp_res = api.import_kdbx_entries_to_vault(read_res["data"], conflict_policy="skip")
    assert imp_res["success"] is True
    assert imp_res["imported"] == 2
