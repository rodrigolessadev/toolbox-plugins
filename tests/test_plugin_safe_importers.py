"""
Testes unitários para o módulo de importação de dados do Microsoft Safe (XML, CSV, TXT, JSON).
"""

import sys
import tempfile
from pathlib import Path
import pytest

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from safe.service import SafeService
from safe.importers import (
    decode_file_bytes,
    parse_safe_xml,
    parse_safe_csv,
    parse_safe_txt,
    parse_safe_json,
    detect_and_parse_secrets,
)


def test_decode_file_bytes_encodings():
    # 1. UTF-8
    utf8_bytes = "Acesso Produção: João & Maria".encode("utf-8")
    assert decode_file_bytes(utf8_bytes) == "Acesso Produção: João & Maria"

    # 2. Windows-1252 / CP1252
    cp1252_bytes = "Acesso Produção: João & Maria".encode("windows-1252")
    assert decode_file_bytes(cp1252_bytes) == "Acesso Produção: João & Maria"

    # 3. UTF-8 com BOM
    bom_bytes = "\ufeffServidor de Contingência".encode("utf-8")
    assert decode_file_bytes(bom_bytes) == "Servidor de Contingência"


def test_parse_microsoft_safe_xml():
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
    <Safe>
      <Card id="1" title="Servidor AWS Produção" category="Servidores">
        <Field name="UserName">admin_cloud</Field>
        <Field name="Password">SuperSecret#2026!</Field>
        <Field name="URL">https://aws.amazon.com/console</Field>
        <Field name="Notes">Servidor primário de aplicação com acentuação: José</Field>
      </Card>
      <Card title="Banco Staging">
        <Title>Banco PostgreSQL Staging</Title>
        <Category>Banco de Dados</Category>
        <UserName>postgres_user</UserName>
        <Password>PgSecureP@ss123</Password>
        <URL>postgres://staging.internal:5432</URL>
        <Notes>Acesso de testes da equipe</Notes>
      </Card>
      <Card title="Anotação Segura" category="Notas">
        <Notes>Chave mestra física guardada no cofre B-12.</Notes>
      </Card>
    </Safe>
    """
    items = parse_safe_xml(xml_content)
    assert len(items) == 3

    # Item 1
    assert items[0]["title"] == "Servidor AWS Produção"
    assert items[0]["category"] == "server"
    assert items[0]["username_or_key"] == "admin_cloud"
    assert items[0]["payload"] == "SuperSecret#2026!"
    assert items[0]["metadata"]["url"] == "https://aws.amazon.com/console"
    assert "José" in items[0]["metadata"]["notes"]

    # Item 2
    assert items[1]["title"] == "Banco PostgreSQL Staging"
    assert items[1]["category"] == "database"
    assert items[1]["username_or_key"] == "postgres_user"
    assert items[1]["payload"] == "PgSecureP@ss123"

    # Item 3
    assert items[2]["title"] == "Anotação Segura"
    assert items[2]["category"] == "note"
    assert items[2]["payload"] == "Chave mestra física guardada no cofre B-12."


def test_parse_microsoft_safe_csv_comma_and_semicolon():
    # 1. CSV separado por vírgula
    csv_comma = """Title,User Name,Password,Category,URL,Notes
"GitHub Enterprise","rodrigo.lessa","ghp_SecretToken999","Web","https://github.com","Token pessoal com escopo repo"
"VPN Escritório","rlessa","VpnPass#456","Senhas","vpn.empresa.com","Conexão corporativa"
"""
    items1 = parse_safe_csv(csv_comma)
    assert len(items1) == 2
    assert items1[0]["title"] == "GitHub Enterprise"
    assert items1[0]["username_or_key"] == "rodrigo.lessa"
    assert items1[0]["payload"] == "ghp_SecretToken999"
    assert items1[0]["category"] == "password"

    # 2. CSV separado por ponto-e-vírgula com cabeçalhos em português
    csv_semicolon = """Título;Usuário;Senha;Categoria;Observações
"Banco Oracle";"SYSTEM";"Manager123";"Banco de Dados";"Instância legada de folha"
"Roteador Datacenter";"admin";"C1sco#Admin";"Servidor";"IP: 192.168.1.1"
"""
    items2 = parse_safe_csv(csv_semicolon)
    assert len(items2) == 2
    assert items2[0]["title"] == "Banco Oracle"
    assert items2[0]["username_or_key"] == "SYSTEM"
    assert items2[0]["payload"] == "Manager123"
    assert items2[0]["category"] == "database"
    assert items2[1]["title"] == "Roteador Datacenter"
    assert items2[1]["category"] == "server"


def test_parse_microsoft_safe_txt():
    txt_content = """
Title: Portal Corporativo
Category: Web
User Name: rodrigo
Password: SecretPassword@2026
URL: https://intranet.empresa.com
Notes: Acesso diário ao portal
Segunda linha de observações

----------------------------------------

[Servidor de Backup]
Category: Servidor
User: backup_admin
Password: BaculaSecretPassword!
Notes: Executa toda madrugada às 02:00
"""
    items = parse_safe_txt(txt_content)
    assert len(items) == 2

    assert items[0]["title"] == "Portal Corporativo"
    assert items[0]["username_or_key"] == "rodrigo"
    assert items[0]["payload"] == "SecretPassword@2026"
    assert "Segunda linha de observações" in items[0]["metadata"]["notes"]

    assert items[1]["title"] == "Servidor de Backup"
    assert items[1]["category"] == "server"
    assert items[1]["username_or_key"] == "backup_admin"
    assert items[1]["payload"] == "BaculaSecretPassword!"


def test_detect_and_parse_secrets():
    # Detecta XML
    xml_data = b"<Safe><Card title=\"AWS Root\"><Field name=\"Password\">pass123</Field></Card></Safe>"
    items_xml, fmt_xml = detect_and_parse_secrets(xml_data, filename="export.xml")
    assert fmt_xml == "xml"
    assert len(items_xml) == 1
    assert items_xml[0]["title"] == "AWS Root"

    # Detecta CSV
    csv_data = "Title,Password\nItem1,Pass1\nItem2,Pass2".encode("windows-1252")
    items_csv, fmt_csv = detect_and_parse_secrets(csv_data, filename="safe_export.csv")
    assert fmt_csv == "csv"
    assert len(items_csv) == 2

    # Detecta TXT
    txt_data = "Title: Test TXT\nPassword: 123456\n".encode("utf-8")
    items_txt, fmt_txt = detect_and_parse_secrets(txt_data, filename="notes.txt")
    assert fmt_txt == "txt"
    assert len(items_txt) == 1


def test_service_preview_and_conflict_policies():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)
        service.setup_vault(password="MasterPassword123!")

        # 1. Cria um registro inicial
        service.save_secret(title="AWS Produção", secret_payload="OriginalSecret123", username_or_key="root")

        # 2. Gera XML contendo item conflitante e item novo
        xml_data = """<?xml version="1.0" encoding="utf-8"?>
        <Safe>
          <Card title="AWS Produção">
            <Field name="UserName">novo_root</Field>
            <Field name="Password">NovoSecret456</Field>
          </Card>
          <Card title="Google Cloud">
            <Field name="UserName">gcp_admin</Field>
            <Field name="Password">GcpSecret789</Field>
          </Card>
        </Safe>
        """

        # Preview deve acusar 1 conflito e 2 itens totais
        preview = service.preview_import(xml_data, filename="import.xml")
        assert preview["success"] is True
        assert preview["total_detected"] == 2
        assert preview["conflicts_count"] == 1
        assert preview["format"] == "xml"

        # 3. Testa Política 'skip' (ignora duplicado)
        res_skip = service.import_secrets(xml_data, conflict_policy="skip", filename="import.xml")
        assert res_skip["success"] is True
        assert res_skip["imported"] == 1
        assert res_skip["skipped"] == 1

        # Verifica se o original manteve o valor antigo
        aws_entry = [e for e in service.list_secrets() if e["title"] == "AWS Produção"][0]
        secret = service.get_secret(aws_entry["id"])
        assert secret["payload"] == "OriginalSecret123"

        # 4. Testa Política 'overwrite' (atualiza os 2 registros que agora existem no cofre)
        res_overwrite = service.import_secrets(xml_data, conflict_policy="overwrite", filename="import.xml")
        assert res_overwrite["success"] is True
        assert res_overwrite["updated"] == 2

        secret_updated = service.get_secret(aws_entry["id"])
        assert secret_updated["payload"] == "NovoSecret456"
        assert secret_updated["username_or_key"] == "novo_root"

        # 5. Testa Política 'duplicate' (cria com sufixo)
        res_dup = service.import_secrets(xml_data, conflict_policy="duplicate", filename="import.xml")
        assert res_dup["success"] is True
        assert res_dup["imported"] == 2

        all_titles = [e["title"] for e in service.list_secrets()]
        assert "AWS Produção (Importado)" in all_titles


def test_service_batch_import_large_dataset_performance():
    """Valida a atomicidade, integridade e performance do import_secrets em lote único."""
    import json
    import time

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault_perf.db"
        service = SafeService(db_path)
        service.setup_vault(password="MasterPassword123!")

        # Gera dataset sintético de 250 credenciais
        items = []
        for i in range(250):
            items.append({
                "title": f"Serviço Corporativo {i}",
                "category": "password" if i % 2 == 0 else "token",
                "username_or_key": f"user_{i}@company.com",
                "payload": f"SecretValue_P@ss_{i}",
                "tags": ["corp", f"tag_{i % 5}"],
                "metadata": {"index": i, "server": f"srv-{i}.internal"},
            })

        json_data = json.dumps(items)

        start_time = time.time()
        res = service.import_secrets(json_data, conflict_policy="duplicate", filename="export.json")
        duration = time.time() - start_time

        assert res["success"] is True
        assert res["imported"] == 250
        assert res["updated"] == 0
        assert res["skipped"] == 0
        assert duration < 2.0  # Em lote único com SQLite deve concluir muito rápido

        # Valida que todos os registros foram inseridos e decriptam perfeitamente
        all_entries = service.list_secrets()
        assert len(all_entries) == 250

        # Amostra aleatória para checagem de decriptação
        sample = service.get_secret(all_entries[42]["id"])
        assert sample["payload"].startswith("SecretValue_P@ss_")
        assert "corp" in sample["tags"]
        assert "tag_2" in sample["tags"]


def test_service_safepack_export_and_import_flow():
    """Valida o fluxo completo de exportação em container .safepack, preview com senha e restauração."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_src_path = Path(tmpdir) / "vault_src.db"
        service_src = SafeService(db_src_path)
        service_src.setup_vault(password="MasterSource123!")

        # Cadastra segredos no cofre de origem
        service_src.save_secret(
            title="Credencial Bancária Safepack",
            category="finance",
            secret_payload="SuperSecret#SafepackPayload!2026",
            username_or_key="usuario.safepack",
            tags=["safepack", "backup"],
        )

        backup_pwd = "BackupEncryptionPassword#777"
        safepack_bytes = service_src.export_secrets(format="safepack", backup_password=backup_pwd)
        assert isinstance(safepack_bytes, bytes)
        assert safepack_bytes.startswith(b"SAFEPACK")

        # Configura cofre de destino
        db_dst_path = Path(tmpdir) / "vault_dst.db"
        service_dst = SafeService(db_dst_path)
        service_dst.setup_vault(password="MasterDest123!")

        # 1. Preview sem senha deve solicitar senha
        prev_no_pwd = service_dst.preview_import(safepack_bytes, filename="meu_backup.safepack")
        assert prev_no_pwd["format"] == "safepack_password_required"
        assert prev_no_pwd["total_detected"] == 0

        # 2. Preview com senha correta
        prev_ok = service_dst.preview_import(safepack_bytes, filename="meu_backup.safepack", backup_password=backup_pwd)
        assert prev_ok["format"] == "safepack"
        assert prev_ok["total_detected"] == 1
        assert prev_ok["preview_items"][0]["title"] == "Credencial Bancária Safepack"

        # 3. Importação com senha correta
        res_import = service_dst.import_secrets(
            safepack_bytes,
            conflict_policy="duplicate",
            filename="meu_backup.safepack",
            backup_password=backup_pwd,
        )
        assert res_import["success"] is True
        assert res_import["imported"] == 1

        # 4. Validação da credencial restaurada no destino
        entries = service_dst.list_secrets()
        assert len(entries) == 1
        secret = service_dst.get_secret(entries[0]["id"])
        assert secret["title"] == "Credencial Bancária Safepack"
        assert secret["payload"] == "SuperSecret#SafepackPayload!2026"
        assert "safepack" in secret["tags"]
