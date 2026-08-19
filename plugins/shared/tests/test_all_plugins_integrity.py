import json
import py_compile
from pathlib import Path
import pytest

plugins_dir = Path(__file__).parent.parent.parent

def test_all_plugins_manifest_and_assets():
    for p in plugins_dir.iterdir():
        if p.is_dir() and p.name not in ["shared", "__pycache__", ".git"]:
            pj = p / "plugin.json"
            assert pj.exists(), f"plugin.json deve existir em {p.name}"

            with open(pj, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "name" in data, f"name ausente em {p.name}"
            assert "version" in data, f"version ausente em {p.name}"
            assert "entry" in data, f"entry ausente em {p.name}"
            assert (p / data["entry"]).exists(), f"entrypoint {data['entry']} não existe em {p.name}"

            ui_dir = p / "ui"
            assert ui_dir.exists(), f"pasta ui/ ausente em {p.name}"
            assert (ui_dir / "index.html").exists(), f"ui/index.html ausente em {p.name}"
            assert (ui_dir / "toolbox-theme.css").exists(), f"ui/toolbox-theme.css ausente em {p.name}"
            assert (ui_dir / "icons.js").exists(), f"ui/icons.js ausente em {p.name}"

            html_txt = (ui_dir / "index.html").read_text(encoding="utf-8")
            assert "../../shared" not in html_txt, f"caminho relativo quebrado detectado no index.html de {p.name}"

            # Valida sintaxe Python
            for pyf in p.glob("*.py"):
                py_compile.compile(str(pyf), doraise=True)
