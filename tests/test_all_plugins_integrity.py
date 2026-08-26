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
