import json
import py_compile
from pathlib import Path


def test_manifest_structure():
    plugin_dir = Path(__file__).parent.parent
    manifest_path = plugin_dir / "plugin.json"
    assert manifest_path.exists(), "plugin.json deve existir"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("name") == "Novo Ticket"
    assert data.get("version") is not None
    assert len(data.get("version").split(".")) >= 3
    assert data.get("language") == "python"
    assert data.get("entry") == "main.py"
    assert (plugin_dir / data["entry"]).exists()

    # Valida autossuficiência de assets locais
    ui_dir = plugin_dir / "ui"
    assert (ui_dir / "index.html").exists()
    assert (ui_dir / "toolbox-theme.css").exists()
    assert (ui_dir / "icons.js").exists()
    assert (ui_dir / "style.css").exists()
    assert (ui_dir / "app.js").exists()
    assert (ui_dir / "assets" / "ticket.ico").exists()

    # Valida que index.html NÃO possui referências relativas externas quebradas
    html_content = (ui_dir / "index.html").read_text(encoding="utf-8")
    assert "../../shared" not in html_content, "index.html não deve depender de caminhos relativos externos"


def test_python_syntax():
    plugin_dir = Path(__file__).parent.parent
    py_files = list(plugin_dir.glob("*.py"))
    assert len(py_files) >= 1, "Devem existir arquivos python do plugin"
    for py_file in py_files:
        py_compile.compile(str(py_file), doraise=True)
