"""
Testes unitários para o entrypoint e inicialização do plugin Safe.
Valida que main.py e service.py inicializam sem erros de importação relativa em diferentes contextos de execução.
"""

import sys
import subprocess
from pathlib import Path
import pytest

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

SAFE_DIR = PLUGINS_DIR / "safe"
if str(SAFE_DIR) not in sys.path:
    sys.path.insert(0, str(SAFE_DIR))

from safe import main as safe_main
from safe import service as safe_service


def test_safe_plugin_api_instantiation(tmp_path):
    """Valida instanciação da API com banco isolado."""
    db_file = tmp_path / "test_vault.db"
    svc = safe_service.SafeService(db_path=db_file)
    api = safe_main.SafePluginApi(service=svc)
    
    status_res = api.get_vault_status()
    assert status_res["success"] is True
    assert status_res["data"]["configured"] is False
    assert status_res["data"]["status"] == "UNCONFIGURED"


def test_direct_script_import_execution():
    """Valida execução do main.py via subprocesso isolado como __main__."""
    main_py = SAFE_DIR / "main.py"
    code = f"""
import sys
sys.path.insert(0, r'{PLUGINS_DIR}')
import main
api = main.SafePluginApi()
assert api is not None
print('IMPORT_SUCCESS')
"""
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(SAFE_DIR),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0, f"Erro na execução direta: {res.stderr}"
    assert "IMPORT_SUCCESS" in res.stdout


def test_safe_service_isolated_execution(tmp_path):
    """Valida service.py executado isoladamente com banco temporário."""
    code = f"""
import sys
from pathlib import Path
sys.path.insert(0, r'{PLUGINS_DIR}')
import service
svc = service.SafeService(db_path=r'{tmp_path / "sub_vault.db"}')
status = svc.get_status()
assert status['configured'] is False
print('SERVICE_SUCCESS')
"""
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(SAFE_DIR),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0, f"Erro na execução do service: {res.stderr}"
    assert "SERVICE_SUCCESS" in res.stdout


def test_safe_taskbar_icon_exists():
    """Valida que o ícone oficial shield-check.ico existe no diretório de assets."""
    assert safe_main.SHIELD_CHECK_ICON_PATH.exists()
    assert safe_main.SHIELD_CHECK_ICON_PATH.is_file()
    assert safe_main.SHIELD_CHECK_ICON_PATH.stat().st_size > 0


def test_windows_hello_availability_detection():
    """Valida que a função de detecção do Windows Hello executa e retorna booleano no Windows."""
    from safe import windows_hello
    avail = windows_hello.is_windows_hello_available()
    assert isinstance(avail, bool)
    if sys.platform == "win32":
        # No ambiente Windows 10/11 atual, o retorno deve ser True
        assert avail is True


def test_safe_plugin_api_exposed_methods(tmp_path):
    """Valida que todos os métodos RPC esperados pelo frontend (app.js) estão implementados e chamáveis."""
    db_file = tmp_path / "test_api_vault.db"
    svc = safe_service.SafeService(db_path=db_file)
    api = safe_main.SafePluginApi(service=svc)

    required_methods = [
        "get_vault_status",
        "setup_vault",
        "unlock_vault",
        "lock_vault",
        "touch_activity",
        "list_secrets",
        "save_secret",
        "get_secret",
        "delete_secret",
        "generate_password",
        "set_master_password",
        "update_security_settings",
        "grant_plugin_access",
        "revoke_plugin_access",
        "list_plugin_grants",
        "export_secrets",
        "preview_import_data",
        "import_secrets",
        "select_file_for_import",
        "import_secrets_from_file_path",
        "copy_secret_to_clipboard",
        "log_frontend_error",
    ]

    for method_name in required_methods:
        assert hasattr(api, method_name), f"Método '{method_name}' não encontrado em SafePluginApi"
        assert callable(getattr(api, method_name)), f"Atributo '{method_name}' não é chamável em SafePluginApi"


def test_safe_plugin_api_frontend_error_logging(tmp_path):
    """Valida o endpoint de log de erros do frontend."""
    db_file = tmp_path / "test_api_err.db"
    svc = safe_service.SafeService(db_path=db_file)
    api = safe_main.SafePluginApi(service=svc)

    res = api.log_frontend_error("Erro de teste no frontend", "Stacktrace line 1\nline 2")
    assert res["success"] is True


def test_get_plugin_version_and_window_title():
    """Valida que a versão é lida de plugin.json e que o título da janela segue o padrão 'Cofre - vX.Y.Z'."""
    manifest = safe_main.get_plugin_manifest()
    assert isinstance(manifest, dict)
    assert "version" in manifest
    
    version = safe_main.get_plugin_version()
    assert version == manifest["version"]
    assert len(version.split(".")) >= 3  # SemVer x.y.z

    window_title = safe_main.get_window_title()
    assert window_title == f"Cofre - v{version}"
    assert " - v" in window_title


def test_get_vault_status_includes_version_metadata(tmp_path):
    """Valida que get_vault_status retorna plugin_version e window_title para o frontend."""
    db_file = tmp_path / "test_status_ver.db"
    svc = safe_service.SafeService(db_path=db_file)
    api = safe_main.SafePluginApi(service=svc)

    status_res = api.get_vault_status()
    assert status_res["success"] is True
    assert "plugin_version" in status_res["data"]
    assert "window_title" in status_res["data"]
    assert status_res["data"]["plugin_version"] == safe_main.get_plugin_version()
    assert status_res["data"]["window_title"] == safe_main.get_window_title()




