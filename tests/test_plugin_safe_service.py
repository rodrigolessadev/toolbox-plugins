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
        eid = save_res["data"]["id"]

        get_res = api.get_secret(eid)
        assert get_res["success"] is True
        assert get_res["data"]["payload"]["host"] == "10.0.0.1"

        lock_res = api.lock_vault()
        assert lock_res["success"] is True

        unlock_res = api.unlock_vault(password="ApiPassword123!")
        assert unlock_res["success"] is True
