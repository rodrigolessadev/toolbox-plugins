import subprocess
import sys
import tempfile
import shutil
from pathlib import Path


def test_isolated_plugin_execution():
    """Valida que o plugin pode ser carregado de forma 100% autossuficiente em ambiente isolado (como no Marketplace)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        plugin_dir = Path(__file__).parent.parent
        
        # Copia apenas os arquivos do plugin (sem shared/)
        shutil.copy(plugin_dir / "main.py", tmp_path / "main.py")
        shutil.copy(plugin_dir / "domain.py", tmp_path / "domain.py")
        shutil.copy(plugin_dir / "plugin.json", tmp_path / "plugin.json")
        
        # Executa script de inicialização básica (sem abrir mainloop)
        check_code = (
            "import domain, main\n"
            "assert hasattr(main, 'THEME')\n"
            "assert hasattr(main, 'NovoTicketApp')\n"
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