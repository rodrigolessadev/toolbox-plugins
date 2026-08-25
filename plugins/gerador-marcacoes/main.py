"""Ponto de entrada do plugin Gerador de Marcações SQL (pywebview).
"""
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.geradormarcacoes")
    except Exception:
        pass

try:
    import webview
except ImportError:
    webview = None

from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import domain


class GeradorMarcacoesApi(BasePluginApi):
    """Ponte JavaScript (window.pywebview.api)."""

    def get_metadata(self) -> dict:
        """Retorna metadados de campos e defaults oficiais."""
        return {
            "fixed_fields": domain.FIXED_FIELDS,
            "main_fields": domain.MAIN_FIELDS,
            "optional_fields": domain.OPTIONAL_FIELDS,
            "default_values": domain.DEFAULT_VALUES,
        }

    def gerar_inserts(self, params: dict) -> dict:
        """Gera instruções SQL a partir dos dados do formulário."""
        return domain.gerar_sql_marcacoes(
            banco=params.get("banco", "sqlserver"),
            numcra=params.get("numcra", "600000010"),
            start_date=params.get("start_date", ""),
            end_date=params.get("end_date", ""),
            horarios=params.get("horarios", ["08:00", "12:00", "13:00", "18:00"]),
            week_days=params.get("week_days", [1, 2, 3, 4, 5]),
            main_fields=params.get("main_fields", {}),
            optional_values=params.get("optional_values", {}),
            selected_optional=params.get("selected_optional", []),
        )


def main():
    api = GeradorMarcacoesApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Gerador de Marcações SQL",
        entry_html=ui_index,
        js_api=api,
        width=840,
        height=820,
        min_size=(740, 640),
    )
    if webview and window:
        pass
    if webview:
        webview.start(debug=False)


if __name__ == "__main__":
    main()
