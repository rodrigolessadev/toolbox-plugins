"""
Testes unitários para a integração do SafeService e SafePluginApi com o Hub KeePassXC.
Valida status, pareamento, consulta de credenciais, geração de senhas e bloqueio.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))
SAFE_DIR = PLUGINS_DIR / "safe"
if str(SAFE_DIR) not in sys.path:
    sys.path.insert(0, str(SAFE_DIR))

from safe.service import SafeService
from safe.main import SafePluginApi


@pytest.fixture(autouse=True)
def disable_background_listeners(monkeypatch):
    import safe.service as s_svc
    monkeypatch.setattr(s_svc, "windows_session", None)
    monkeypatch.setattr(s_svc, "windows_hello", None)




def test_safe_service_keepassxc_status_connected(tmp_path: Path):
    """Valida retorno do status quando o KeePassXC está conectado e desbloqueado."""
    mock_client = MagicMock()
    mock_client.get_database_status.return_value = {
        "available": True,
        "connected": True,
        "associated": True,
        "client_id": "test-client-123",
        "unlocked": True
    }

    db_path = tmp_path / "test_safe.db"
    service = SafeService(db_path=db_path, keepassxc_client=mock_client)

    status = service.get_keepassxc_status()
    assert status["available"] is True
    assert status["connected"] is True
    assert status["unlocked"] is True
    assert status["client_id"] == "test-client-123"


def test_safe_service_keepassxc_associate(tmp_path: Path):
    """Valida acionamento do método associate no cliente."""
    mock_client = MagicMock()
    mock_client.associate.return_value = {
        "success": True,
        "id": "associated-id-456",
        "message": "Pareado com sucesso!"
    }

    db_path = tmp_path / "test_safe.db"
    service = SafeService(db_path=db_path, keepassxc_client=mock_client)

    res = service.associate_keepassxc("Toolbox Test")
    assert res["success"] is True
    assert res["id"] == "associated-id-456"
    mock_client.associate.assert_called_once_with(client_name="Toolbox Test")


def test_safe_service_search_keepassxc_entries(tmp_path: Path):
    """Valida busca e filtragem de entradas retornadas pelo KeePassXC."""
    mock_client = MagicMock()
    mock_client.get_logins.return_value = [
        {"name": "AWS Production", "login": "aws_admin", "password": "pass1", "uuid": "u1"},
        {"name": "GitHub Account", "login": "dev_user", "password": "pass2", "uuid": "u2"},
    ]

    db_path = tmp_path / "test_safe.db"
    service = SafeService(db_path=db_path, keepassxc_client=mock_client)

    # Busca com termo de filtro
    results = service.search_keepassxc_entries(query="aws")
    assert len(results) == 1
    assert results[0]["name"] == "AWS Production"

    # Busca geral
    all_results = service.search_keepassxc_entries()
    assert len(all_results) == 2


def test_safe_service_totp_and_password_generator(tmp_path: Path):
    """Valida recuperação de TOTP e geração de senha forte via KeePassXC."""
    mock_client = MagicMock()
    mock_client.get_totp.return_value = "123456"
    mock_client.generate_password.return_value = "G3n3r4t3d-Str0ng-Pwd!"
    mock_client.lock_database.return_value = True

    db_path = tmp_path / "test_safe.db"
    service = SafeService(db_path=db_path, keepassxc_client=mock_client)

    assert service.get_keepassxc_totp("u1") == "123456"
    assert service.generate_keepassxc_password() == "G3n3r4t3d-Str0ng-Pwd!"
    assert service.lock_keepassxc_database() is True


def test_safe_plugin_api_keepassxc_bridge(tmp_path: Path):
    """Valida os métodos expostos na JS bridge SafePluginApi."""
    mock_client = MagicMock()
    mock_client.get_database_status.return_value = {"connected": True, "unlocked": True}
    mock_client.associate.return_value = {"success": True, "id": "assoc-789"}
    mock_client.get_logins.return_value = [{"name": "Entry 1", "login": "user1"}]
    mock_client.get_totp.return_value = "654321"
    mock_client.generate_password.return_value = "Password123!"
    mock_client.lock_database.return_value = True

    db_path = tmp_path / "test_safe.db"
    service = SafeService(db_path=db_path, keepassxc_client=mock_client)
    api = SafePluginApi(service=service)

    # get_keepassxc_status
    st = api.get_keepassxc_status()
    assert st["success"] is True
    assert st["data"]["connected"] is True

    # associate_keepassxc
    assoc = api.associate_keepassxc("Test App")
    assert assoc["success"] is True
    assert assoc["data"]["id"] == "assoc-789"

    # search_keepassxc_entries
    srch = api.search_keepassxc_entries("Entry")
    assert srch["success"] is True
    assert len(srch["data"]) == 1

    # get_keepassxc_totp
    totp = api.get_keepassxc_totp("e1")
    assert totp["success"] is True
    assert totp["totp"] == "654321"

    # generate_keepassxc_password
    pwd = api.generate_keepassxc_password()
    assert pwd["success"] is True
    assert pwd["password"] == "Password123!"

    # lock_keepassxc_database
    lk = api.lock_keepassxc_database()
    assert lk["success"] is True
