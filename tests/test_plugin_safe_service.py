"""
Testes unitários e de integração para o SafeService e API pública do plugin Safe.
"""

import tempfile
import sys
import time
import pytest
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from safe.service import SafeService, SafeAccessDeniedError, SafeVaultLockedError
from safe.main import SafePluginApi


def test_service_lifecycle_setup_lock_unlock():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)

        # Status inicial não configurado
        status = service.get_status()
        assert status["configured"] is False
        assert status["status"] == "UNCONFIGURED"

        # Setup
        res = service.setup_vault(auth_mode="master_password", password="MasterPassword123!", auto_lock_timeout=300)
        assert res["success"] is True

        # Status desbloqueado imediatamente após setup
        status_unlocked = service.get_status()
        assert status_unlocked["configured"] is True
        assert status_unlocked["status"] == "UNCONFIGURED" or status_unlocked["status"] == "UNLOCKED"

        # Bloquear
        service.lock()
        assert service.get_status()["status"] == "LOCKED"

        # Tentativa de leitura com cofre bloqueado deve falhar
        with pytest.raises(SafeVaultLockedError):
            service.list_secrets()

        # Desbloqueio com senha errada
        with pytest.raises(SafeAccessDeniedError):
            service.unlock(password="SenhaIncorreta")

        # Desbloqueio com senha correta
        assert service.unlock(password="MasterPassword123!") is True
        assert service.get_status()["status"] == "UNLOCKED"


def test_service_secret_encryption_and_acl():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)
        service.setup_vault(auth_mode="master_password", password="SecretMasterPassword!", auto_lock_timeout=300)

        # Salvar segredo
        saved = service.save_secret(
            title="GitHub Personal Access Token",
            secret_payload="ghp_1234567890abcdef",
            category="token",
            username_or_key="rodrigolessadev",
            tags=["github", "dev"],
        )
        entry_id = saved["id"]

        # Recuperar segredo
        secret = service.get_secret(entry_id)
        assert secret["title"] == "GitHub Personal Access Token"
        assert secret["payload"] == "ghp_1234567890abcdef"
        assert secret["username_or_key"] == "rodrigolessadev"

        # Outro plugin tentando acessar sem permissão deve ser barrado por ACL
        with pytest.raises(SafeAccessDeniedError):
            service.get_secret(entry_id, requester_plugin_id="plugin-git")

        # Concede permissão ao plugin-git
        service.grant_permission("plugin-git", entry_id, access_level="read")

        # Agora plugin-git consegue acessar
        secret_by_plugin = service.get_secret(entry_id, requester_plugin_id="plugin-git")
        assert secret_by_plugin["payload"] == "ghp_1234567890abcdef"

        # Revogar permissão
        grants = service.list_grants("plugin-git")
        assert len(grants) == 1
        service.revoke_permission(grants[0]["id"])

        # Deve falhar novamente
        with pytest.raises(SafeAccessDeniedError):
            service.get_secret(entry_id, requester_plugin_id="plugin-git")


def test_service_auto_lock():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)
        # Timeout de 1 segundo para teste
        service.setup_vault(auth_mode="master_password", password="SecretMasterPassword!", auto_lock_timeout=1)

        assert service.get_status()["status"] == "UNLOCKED"
        
        # Simula passagem de tempo
        service._last_activity_time = time.time() - 2
        
        assert service.check_auto_lock() is True
        assert service.get_status()["status"] == "LOCKED"


def test_service_touch_activity_prevents_autolock():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)
        # Timeout de 2 segundos
        service.setup_vault(password="SecretMasterPassword!", auto_lock_timeout=2)
        assert service.get_status()["status"] == "UNLOCKED"

        # Simula 1 segundo de tempo passado
        service._last_activity_time = time.time() - 1
        assert service.check_auto_lock() is False
        assert service.get_status()["status"] == "UNLOCKED"

        # Usuário interage -> touch_activity()
        service.touch_activity()

        # Mais 1 segundo se passa (total de 2 segundos desde o setup, mas apenas 1s desde a última atividade)
        service._last_activity_time = time.time() - 1
        assert service.check_auto_lock() is False
        assert service.get_status()["status"] == "UNLOCKED"

        # Agora deixa 3 segundos inativo
        service._last_activity_time = time.time() - 3
        assert service.check_auto_lock() is True
        assert service.get_status()["status"] == "LOCKED"


def test_password_generator():
    service = SafeService()
    pwd = service.generate_secure_password(length=24, use_upper=True, use_lower=True, use_digits=True, use_symbols=True)
    assert len(pwd) == 24
    assert any(c.isupper() for c in pwd)
    assert any(c.islower() for c in pwd)
    assert any(c.isdigit() for c in pwd)


def test_safe_plugin_api_bridge():
    with tempfile.TemporaryDirectory() as tmpdir:
        service = SafeService(Path(tmpdir) / "vault.db")
        api = SafePluginApi(service)

        status = api.get_vault_status()
        assert status["success"] is True
        assert status["data"]["configured"] is False

        setup_res = api.setup_vault(auth_mode="master_password", password="ApiPassword123!", timeout=300)
        assert setup_res["success"] is True

        save_res = api.save_secret(
            title="Database Prod",
            secret_payload={"host": "10.0.0.1", "pwd": "dbpwd"},
            category="password",
            username_or_key="dbadmin",
        )
        assert save_res["success"] is True

        list_res = api.list_secrets()
        assert list_res["success"] is True
        assert len(list_res["data"]) == 1

        eid = save_res["data"]["id"]

        get_res = api.get_secret(eid)
        assert get_res["success"] is True
        assert get_res["data"]["payload"]["host"] == "10.0.0.1"

        # Export via API
        exp_res = api.export_secrets()
        assert exp_res["success"] is True
        assert len(exp_res["data"]) == 1

        # Import via API
        imp_res = api.import_secrets([{"title": "API Secret", "payload": "123456", "category": "general"}])
        assert imp_res["success"] is True
        assert imp_res["imported"] == 1

        # Update security settings
        sec_res = api.update_security_settings(auto_lock_timeout=600, lock_on_os_lock=True)
        assert sec_res["success"] is True

        lock_res = api.lock_vault()
        assert lock_res["success"] is True

        unlock_res = api.unlock_vault(password="ApiPassword123!")
        assert unlock_res["success"] is True


def test_service_mandatory_password_and_migration():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)

        # Tentativa de setup sem senha deve falhar
        with pytest.raises(ValueError, match="A senha mestre é obrigatória"):
            service.setup_vault(password="")

        with pytest.raises(ValueError, match="A senha mestre é obrigatória"):
            service.setup_vault(password="123")

        # Setup com senha e modo hybrid
        res = service.setup_vault(auth_mode="hybrid", password="StrongPassword123!", use_hello=True, lock_on_os_lock=True)
        assert res["success"] is True

        status = service.get_status()
        assert status["auth_mode"] == "hybrid"
        assert status["lock_on_os_lock"] is True
        assert status["needs_password_migration"] is False

        # Alteração / definição de senha mestre
        pwd_res = service.set_master_password("NewStrongPassword456!")
        assert pwd_res["success"] is True

        # Testa lock e unlock com a nova senha
        service.lock()
        assert service.unlock(password="NewStrongPassword456!") is True


def test_service_os_session_lock():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)
        service.setup_vault(password="VaultPassword123!", lock_on_os_lock=True)
        assert service.get_status()["status"] == "UNLOCKED"

        # Simula evento de lock do sistema operacional
        service._handle_os_session_lock()
        assert service.get_status()["status"] == "LOCKED"

        # Com lock_on_os_lock = False
        service.unlock(password="VaultPassword123!")
        service.update_security_settings(auto_lock_timeout=300, lock_on_os_lock=False)
        assert service.get_status()["lock_on_os_lock"] is False

        service._handle_os_session_lock()
        # Não deve bloquear quando a opção estiver desativada
        assert service.get_status()["status"] == "UNLOCKED"


def test_service_import_export_save_in_cloud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)
        service.setup_vault(password="VaultPassword123!")

        # Importar lista de segredos / Save in Cloud format
        import_payload = [
            {
                "title": "AWS Root Account",
                "payload": "SuperSecretAwsKey",
                "category": "api_key",
                "username_or_key": "root@empresa.com",
                "tags": ["cloud", "aws"],
            },
            {
                "name": "Database Staging",
                "password": "StagingPassword999",
                "category": "password",
                "username": "pgadmin",
            },
            {
                "title": "Sem Conteúdo",
                "payload": None,
            }
        ]

        import_res = service.import_secrets(import_payload)
        assert import_res["success"] is True
        assert import_res["imported"] == 2
        assert import_res["skipped"] == 1

        # Listar e validar
        secrets = service.list_secrets()
        assert len(secrets) == 2

        # Exportar segredos
        exported = service.export_secrets()
        assert len(exported) == 2
        titles = [e["title"] for e in exported]
        assert "AWS Root Account" in titles
        assert "Database Staging" in titles


def test_service_windows_hello_and_password_dual_wrapping(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)

        # Mock das funções do Windows Hello para simular DPAPI em qualquer SO / ambiente de teste
        fake_dpapi_store = {}

        def mock_is_available():
            return True

        def mock_verify(reason=""):
            return True, "OK"

        def mock_protect(data: bytes, entropy: bytes = None) -> bytes:
            fake_blob = b"DPAPI_WRAPPED:" + data
            return fake_blob

        def mock_unprotect(blob: bytes, entropy: bytes = None) -> bytes:
            if not blob.startswith(b"DPAPI_WRAPPED:"):
                raise ValueError("Invalid DPAPI blob")
            return blob[len(b"DPAPI_WRAPPED:"):]

        import safe.service as ss
        monkeypatch.setattr(ss.windows_hello, "is_windows_hello_available", mock_is_available)
        monkeypatch.setattr(ss.windows_hello, "verify_windows_hello", mock_verify)
        monkeypatch.setattr(ss.windows_hello, "protect_data_dpapi", mock_protect)
        monkeypatch.setattr(ss.windows_hello, "unprotect_data_dpapi", mock_unprotect)

        # 1. Setup no modo Híbrido (com senha + Windows Hello)
        setup_res = service.setup_vault(auth_mode="hybrid", password="InitialPassword123!", use_hello=True)
        assert setup_res["success"] is True

        # Salva um segredo
        service.save_secret(title="Secret 1", secret_payload="Value 1")

        # 2. Testa desbloqueio com Senha Mestra
        service.lock()
        assert service.unlock(password="InitialPassword123!") is True
        assert service.get_secret(service.list_secrets()[0]["id"])["payload"] == "Value 1"

        # 3. Testa desbloqueio com Windows Hello
        service.lock()
        assert service.unlock(use_hello=True) is True
        assert service.get_secret(service.list_secrets()[0]["id"])["payload"] == "Value 1"

        # 4. Altera a Senha Mestra (migração / update)
        pwd_res = service.set_master_password("UpdatedPassword456!")
        assert pwd_res["success"] is True

        # 5. Após alterar a Senha Mestra, testa desbloqueio com a NOVA senha
        service.lock()
        assert service.unlock(password="UpdatedPassword456!") is True

        # 6. E testa desbloqueio com Windows Hello após alteração de senha (garante que o vínculo biométrico NÃO quebrou)
        service.lock()
        assert service.unlock(use_hello=True) is True
        assert service.get_secret(service.list_secrets()[0]["id"])["payload"] == "Value 1"


def test_service_auto_lock_disabled_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)
        
        # Setup com auto_lock_timeout = 0 (Desativado)
        service.setup_vault(password="SecretPassword123!", auto_lock_timeout=0)
        
        status = service.get_status()
        assert status["auto_lock_timeout"] == 0
        assert status["auto_lock_remaining"] == 0
        assert status["status"] == "UNLOCKED"

        # Simula passagem de tempo excessivo (ex: 1 hora)
        service._last_activity_time = time.time() - 3600

        # Não deve bloquear quando auto_lock_timeout <= 0
        assert service.check_auto_lock() is False
        assert service.get_status()["status"] == "UNLOCKED"


def test_service_windows_hello_self_healing_from_null_blob(monkeypatch):
    """
    Testa a capacidade de auto-cura (self-healing) quando uma base híbrida existente
    possui wrapped_hello_key = NULL (cenário exato da regressão na issue #162).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)

        def mock_is_available():
            return True

        def mock_verify(reason=""):
            return True, "OK"

        def mock_protect(data: bytes, entropy: bytes = None) -> bytes:
            return b"DPAPI_WRAPPED:" + data

        def mock_unprotect(blob: bytes, entropy: bytes = None) -> bytes:
            if not blob or not blob.startswith(b"DPAPI_WRAPPED:"):
                raise ValueError("Invalid DPAPI blob")
            return blob[len(b"DPAPI_WRAPPED:"):]

        import safe.service as ss
        monkeypatch.setattr(ss.windows_hello, "is_windows_hello_available", mock_is_available)
        monkeypatch.setattr(ss.windows_hello, "verify_windows_hello", mock_verify)
        monkeypatch.setattr(ss.windows_hello, "protect_data_dpapi", mock_protect)
        monkeypatch.setattr(ss.windows_hello, "unprotect_data_dpapi", mock_unprotect)

        # 1. Configura cofre apenas com Senha Mestra inicialmente
        service.setup_vault(auth_mode="master_password", password="MasterPassword123!")
        service.save_secret(title="Credencial Crítica", secret_payload="TokenSecret999")
        service.lock()

        # 2. Força o estado quebrado no banco: auth_mode = 'hybrid', mas wrapped_hello_key = NULL
        with service.db.connect() as conn:
            conn.execute("UPDATE safe_metadata SET auth_mode = 'hybrid', wrapped_hello_key = NULL WHERE id = 'default_vault'")
            conn.commit()

        # 3. Tenta desbloquear via Windows Hello: deve recusar com mensagem explicativa (sem quebrar)
        with pytest.raises(ss.SafeAccessDeniedError) as exc_info:
            service.unlock(use_hello=True)
        assert "Vínculo do Windows Hello desatualizado" in str(exc_info.value)

        # 4. Desbloqueia com a Senha Mestra: isso DEVE disparar a AUTO-CURA
        assert service.unlock(password="MasterPassword123!") is True

        # 5. Verifica se o banco agora contém o envelope wrapped_hello_key persistido
        meta_healed = service.db.get_metadata()
        assert meta_healed["wrapped_hello_key"] is not None
        assert meta_healed["wrapped_hello_key"].startswith(b"DPAPI_WRAPPED:")

        # 6. Bloqueia e agora tenta desbloquear via Windows Hello de forma 100% autônoma
        service.lock()
        assert service.unlock(use_hello=True) is True
        secret = service.get_secret(service.list_secrets()[0]["id"])
        assert secret["payload"] == "TokenSecret999"


def test_service_windows_hello_entropy_fallback(monkeypatch):
    """
    Testa a resiliência do Windows Hello com fallback quando o envelope foi protegido sem entropia.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)

        def mock_is_available():
            return True

        def mock_verify(reason=""):
            return True, "OK"

        def mock_protect(data: bytes, entropy: bytes = None) -> bytes:
            return b"RAW_DPAPI:" + data

        def mock_unprotect(blob: bytes, entropy: bytes = None) -> bytes:
            # Falha se entropy for fornecido (simula chave salva sem entropia)
            if entropy is not None:
                raise ValueError("CryptUnprotectData failed: invalid parameter / wrong entropy")
            if not blob or not blob.startswith(b"RAW_DPAPI:"):
                raise ValueError("Invalid blob")
            return blob[len(b"RAW_DPAPI:"):]

        import safe.service as ss
        monkeypatch.setattr(ss.windows_hello, "is_windows_hello_available", mock_is_available)
        monkeypatch.setattr(ss.windows_hello, "verify_windows_hello", mock_verify)
        monkeypatch.setattr(ss.windows_hello, "protect_data_dpapi", mock_protect)
        monkeypatch.setattr(ss.windows_hello, "unprotect_data_dpapi", mock_unprotect)

        service.setup_vault(auth_mode="hybrid", password="TestPassword123!", use_hello=True)
        service.lock()

        # Desbloqueio via Windows Hello deve conseguir decifrar usando o fallback sem entropia
        assert service.unlock(use_hello=True) is True


def test_service_update_security_settings_persistence():
    """
    Testa a persistência de configurações de segurança, garantindo que timeouts
    de 0s (desativado), 60s, 900s e flags de lock_on_os sejam mantidos entre consultas.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)

        service.setup_vault(password="TestPassword123!", auto_lock_timeout=300, lock_on_os_lock=True)
        status = service.get_status()
        assert status["auto_lock_timeout"] == 300
        assert status["lock_on_os_lock"] is True

        # 1. Altera para 0s (Desativado / Nunca) e lock_on_os = False
        res = service.update_security_settings(auto_lock_timeout=0, lock_on_os_lock=False)
        assert res["success"] is True

        # Instancia novo serviço apontando para o mesmo banco para validar persistência real em disco
        service2 = SafeService(db_path)
        status2 = service2.get_status()
        assert status2["auto_lock_timeout"] == 0
        assert status2["lock_on_os_lock"] is False

        # 2. Desbloqueia service2, altera para 900s (15 min) e lock_on_os = True
        service2.unlock(password="TestPassword123!")
        service2.update_security_settings(auto_lock_timeout=900, lock_on_os_lock=True)
        service3 = SafeService(db_path)
        status3 = service3.get_status()
        assert status3["auto_lock_timeout"] == 900
        assert status3["lock_on_os_lock"] is True


def test_service_os_session_lock_with_listeners():
    """
    Testa se o listener de bloqueio de sessão do Windows aciona os callbacks registrados
    quando lock_on_os_lock = True e respeita quando lock_on_os_lock = False.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vault.db"
        service = SafeService(db_path)

        service.setup_vault(password="MasterPassword123!", lock_on_os_lock=True)
        assert service.get_status()["status"] == "UNLOCKED"

        lock_events = []
        def lock_listener(reason: str):
            lock_events.append(reason)

        service.add_on_lock_listener(lock_listener)

        # 1. Simula evento Win+L com lock_on_os_lock = True
        service._handle_os_session_lock()
        assert service.get_status()["status"] == "LOCKED"
        assert len(lock_events) == 1
        assert "Bloqueio de Sessão do Windows" in lock_events[0]

        # 2. Desbloqueia e altera configuração para lock_on_os_lock = False
        service.unlock(password="MasterPassword123!")
        assert service.get_status()["status"] == "UNLOCKED"
        service.update_security_settings(auto_lock_timeout=300, lock_on_os_lock=False)

        # 3. Simula evento Win+L com lock_on_os_lock = False -> NÃO deve bloquear
        lock_events.clear()
        service._handle_os_session_lock()
        assert service.get_status()["status"] == "UNLOCKED"
        assert len(lock_events) == 0



