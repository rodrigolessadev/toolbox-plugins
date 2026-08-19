import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def test_isolated_plugin_execution():
    """Valida que o plugin pode ser carregado de forma autossuficiente com sua pasta ui/ e shared/ empacotada."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        plugin_dir = Path(__file__).parent.parent
        shared_dir = plugin_dir.parent / "shared"

        # Copia arquivos do plugin e pasta ui/
        shutil.copy(plugin_dir / "main.py", tmp_path / "main.py")
        shutil.copy(plugin_dir / "domain.py", tmp_path / "domain.py")
        shutil.copy(plugin_dir / "plugin.json", tmp_path / "plugin.json")
        shutil.copytree(plugin_dir / "ui", tmp_path / "ui")

        # Copia shared/ como é feito no empacotamento de release
        if shared_dir.exists():
            shutil.copytree(shared_dir, tmp_path / "shared")

        # Executa script de inicialização básica da API
        check_code = (
            "import domain, main\n"
            "assert hasattr(main, 'NovoTicketApi')\n"
            "api = main.NovoTicketApi()\n"
            "assert hasattr(api, 'preview_ticket')\n"
            "assert hasattr(api, 'create_ticket')\n"
            "assert hasattr(api, 'execute_filter')\n"
            "print('ISOLATED_OK')\n"
        )
        (tmp_path / "check.py").write_text(check_code, encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(tmp_path / "check.py")],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=5
        )
        assert proc.returncode == 0, f"Falha na execução isolada: {proc.stderr}"
        assert "ISOLATED_OK" in proc.stdout
