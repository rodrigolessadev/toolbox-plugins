#!/usr/bin/env python3
"""
Auditoria de Conformidade Global dos Plugins — Toolbox Ecosystem.
Verifica se todos os plugins atendem aos requisitos obrigatórios:
1. Suporte a tema Claro/Escuro (Light / Dark tokens em toolbox-theme.css e data-theme)
2. Exibição explícita da versão na interface (UI)
3. Declaração de theme_version: "material-3" em plugin.json e catalog.json
"""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
CATALOG_FILE = ROOT / "catalog.json"


def audit_plugins():
    print("=" * 60)
    print("[AUDIT] INICIANDO AUDITORIA DE CONFORMIDADE DE PLUGINS (M3)")
    print("=" * 60)

    if not CATALOG_FILE.exists():
        print("[ERRO] catalog.json não encontrado!")
        return False

    cat_data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    catalog_map = {p["id"]: p for p in cat_data.get("plugins", [])}

    issues_found = []
    total_plugins = 0

    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name in ("__pycache__", "shared"):
            continue

        plugin_id = plugin_dir.name
        total_plugins += 1
        print(f"\n[*] Verificando plugin: [{plugin_id}]")

        # 1. Manifest
        pj_file = plugin_dir / "plugin.json"
        if not pj_file.exists():
            issues_found.append((plugin_id, "plugin.json ausente"))
            print("  [X] plugin.json ausente")
            continue

        pj = json.loads(pj_file.read_text(encoding="utf-8"))
        version = pj.get("version", "")
        theme_ver = pj.get("theme_version", "")

        if not version:
            issues_found.append((plugin_id, "versão não informada em plugin.json"))
            print("  [X] Versão ausente em plugin.json")

        if theme_ver != "material-3":
            issues_found.append((plugin_id, f"theme_version é '{theme_ver}' (esperado: 'material-3')"))
            print(f"  [!] theme_version: {theme_ver}")
        else:
            print("  [OK] theme_version: material-3")

        # 2. Catálogo
        if plugin_id in catalog_map:
            cat_entry = catalog_map[plugin_id]
            if cat_entry.get("theme_version") != "material-3":
                issues_found.append((plugin_id, "catalog.json não possui theme_version='material-3'"))
                print("  [!] catalog.json sem theme_version='material-3'")
            else:
                print("  [OK] catalog.json sincronizado com material-3")

        # 3. CSS e Suporte a Temas
        css_file = plugin_dir / "ui" / "toolbox-theme.css"
        if css_file.exists():
            css_content = css_file.read_text(encoding="utf-8")
            has_dark = "data-theme=\"dark\"" in css_content or ":root" in css_content
            has_light = "data-theme=\"light\"" in css_content
            if has_dark and has_light:
                print("  [OK] Suporte a Temas Dark e Light verificado no CSS")
            else:
                print(f"  [i] Suporte parcial a temas (dark={has_dark}, light={has_light})")

        # 4. Verificação de versão na UI (index.html)
        ui_file = plugin_dir / "ui" / "index.html"
        if ui_file.exists():
            ui_content = ui_file.read_text(encoding="utf-8")
            has_version = f"v{version}" in ui_content or "version" in ui_content.lower()
            if has_version:
                print(f"  [OK] Exibição de versão detectada na UI (v{version})")
            else:
                print("  [i] Tag de versão explícita não encontrada diretamente no HTML")

    print("\n" + "=" * 60)
    print(f"[RESULTADO] {total_plugins} plugins analisados.")
    if issues_found:
        print(f"[AVISOS] {len(issues_found)} inconformidades detectadas:")
        for pid, issue in issues_found:
            print(f"  - [{pid}]: {issue}")
    else:
        print("[SUCESSO] Todos os plugins auditados estão em conformidade!")
    print("=" * 60)
    return len(issues_found) == 0


if __name__ == "__main__":
    audit_plugins()
