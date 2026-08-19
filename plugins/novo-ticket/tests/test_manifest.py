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
    assert data.get("version") == "1.0.0"
    assert data.get("language") == "python"
    assert data.get("entry") == "main.py"
    assert (plugin_dir / data["entry"]).exists()


def test_python_syntax():
    plugin_dir = Path(__file__).parent.parent
    py_files = list(plugin_dir.glob("*.py"))
    assert len(py_files) >= 1, "Devem existir arquivos python do plugin"
    for py_file in py_files:
        py_compile.compile(str(py_file), doraise=True)