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


