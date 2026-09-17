import json
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
PLUGINS_DIR = ROOT / "plugins"
CATALOG_FILE = ROOT / "catalog.json"

OFFICIAL_LUCIDE_ICONS = {
    "analysis-orchestrator": "workflow",
    "calc-jornadas": "clock-3",
    "converter-data": "calendar-sync",
    "gerador-afd": "file-clock",
    "gerador-json": "file-json",
    "gerador-marcacoes": "database",
    "har-kibana-planner": "search-code",
    "stract-json": "scan-search",
    "stract-log": "file-search",
    "cpf": "badge-check",
    "novo-ticket": "ticket",
    "logon-aws": "cloud-cog",
    "markdown-viewer": "file-text",
    "tarefas": "check-square",
}

def test_catalog_exists_and_valid():
    assert CATALOG_FILE.exists(), "catalog.json deve existir"
    data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    assert "plugins" in data
    assert len(data["plugins"]) >= 11

def test_all_plugin_manifests_and_icons():
    cat_data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    cat_plugins = {p["id"]: p for p in cat_data["plugins"]}

    for plugin_id, expected_icon in OFFICIAL_LUCIDE_ICONS.items():
        p_dir = PLUGINS_DIR / plugin_id
        assert p_dir.exists(), f"Diretório do plugin {plugin_id} deve existir"
        
        pj_file = p_dir / "plugin.json"
        assert pj_file.exists(), f"plugin.json de {plugin_id} deve existir"
        
        pj_data = json.loads(pj_file.read_text(encoding="utf-8"))
        assert pj_data.get("icon") == expected_icon, f"Ícone de {plugin_id} deve ser {expected_icon}"
        assert pj_data.get("entry") == "main.py"
        
        # Validação cruzada com catalog.json
        assert plugin_id in cat_plugins, f"Plugin {plugin_id} deve estar no catalog.json"
        assert cat_plugins[plugin_id].get("icon") == expected_icon, f"Ícone no catálogo para {plugin_id} deve ser {expected_icon}"


def test_all_plugins_shared_ui_sync():
    """
    Valida que todos os plugins do catálogo possuem toolbox-theme.css e icons.js
    100% idênticos à fonte única da verdade em plugins/shared/ui/ (Critério 4 da Issue #237).
    """
    import hashlib

    shared_ui_dir = PLUGINS_DIR / "shared" / "ui"
    assert shared_ui_dir.is_dir(), "Diretório plugins/shared/ui deve existir"

    master_theme = shared_ui_dir / "toolbox-theme.css"
    master_icons = shared_ui_dir / "icons.js"
    assert master_theme.is_file(), "toolbox-theme.css mestre deve existir"
    assert master_icons.is_file(), "icons.js mestre deve existir"

    master_theme_hash = hashlib.sha256(master_theme.read_bytes()).hexdigest()
    master_icons_hash = hashlib.sha256(master_icons.read_bytes()).hexdigest()

    divergences = []
    processed_count = 0

    for pdir in sorted(PLUGINS_DIR.iterdir()):
        if not pdir.is_dir() or pdir.name in ("__pycache__", "shared", ".git"):
            continue

        plugin_id = pdir.name
        processed_count += 1
        ui_dir = pdir / "ui"

        p_theme = ui_dir / "toolbox-theme.css"
        p_icons = ui_dir / "icons.js"

        if not p_theme.is_file():
            divergences.append(f"{plugin_id}: toolbox-theme.css ausente em {ui_dir}")
        elif hashlib.sha256(p_theme.read_bytes()).hexdigest() != master_theme_hash:
            divergences.append(f"{plugin_id}: toolbox-theme.css diverge da fonte mestre shared/ui/")

        if not p_icons.is_file():
            divergences.append(f"{plugin_id}: icons.js ausente em {ui_dir}")
        elif hashlib.sha256(p_icons.read_bytes()).hexdigest() != master_icons_hash:
            divergences.append(f"{plugin_id}: icons.js diverge da fonte mestre shared/ui/")

    assert processed_count >= 15, f"Esperava pelo menos 15 plugins auditados, encontrou {processed_count}"
    assert not divergences, (
        f"Divergências detectadas contra a fonte mestre shared/ui/:\n"
        + "\n".join(f"  - {d}" for d in divergences)
        + "\nExecute 'python tb_auto.py sync-ui' para sincronizar os plugins."
    )

