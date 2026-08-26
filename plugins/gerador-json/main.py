import json
import os
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

import importlib.util
from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import webview

domain_path = PLUGIN_DIR / "domain.py"
spec = importlib.util.spec_from_file_location("gerador_json_domain", domain_path)
domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain)


class GeradorJsonApi(BasePluginApi):
    """API Python exposta para a interface WebView do formatador/gerador de JSON."""

    def format_json(self, text: str, indent: int = 2, sort_keys: bool = False) -> dict:
        return domain.format_json(text, indent=indent, sort_keys=sort_keys)

    def minify_json(self, text: str) -> dict:
        return domain.minify_json(text)

    def validate_json(self, text: str) -> dict:
        return domain.validate_json(text)

    def generate_mock(self, template_type: str) -> dict:
        return domain.generate_mock_json(template_type)

    def get_plugin_version(self) -> dict:
        try:
            pj = PLUGIN_DIR / "plugin.json"
            if pj.exists():
                data = json.loads(pj.read_text(encoding="utf-8"))
                return {"success": True, "version": data.get("version", "1.2.0")}
        except Exception:
            pass
        return {"success": True, "version": "1.2.0"}

    def abrir_arquivo_dialog(self) -> dict:
        try:
            if not webview.windows:
                return {"success": False, "error": "Janela principal não encontrada."}
            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Arquivos JSON (*.json)", "Todos os arquivos (*.*)")
            )
            if not result:
                return {"success": False, "cancelled": True}

            selected_path = result[0] if isinstance(result, (list, tuple)) else result
            content = Path(selected_path).read_text(encoding="utf-8", errors="replace")
            return {
                "success": True,
                "path": str(selected_path),
                "filename": Path(selected_path).name,
                "content": content
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def salvar_arquivo_dialog(self, content: str, default_filename: str = "dados.json") -> dict:
        try:
            if not webview.windows:
                return {"success": False, "error": "Janela principal não encontrada."}
            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_filename or "dados.json",
                file_types=("Arquivos JSON (*.json)", "Todos os arquivos (*.*)")
            )
            if not result:
                return {"success": False, "cancelled": True}

            save_path = result[0] if isinstance(result, (list, tuple)) else result
            Path(save_path).write_text(content or "", encoding="utf-8")
            return {"success": True, "path": str(save_path)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.geradorjson")
        except Exception:
            pass

    api = GeradorJsonApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Formatador & Validador de JSON",
        entry_html=ui_index,
        js_api=api,
        width=840,
        height=760,
        min_size=(680, 560),
    )
    if webview and window:
        def on_shown():
            domain.set_window_taskbar_icon()
            import threading
            threading.Timer(0.6, domain.set_window_taskbar_icon).start()

        window.events.shown += on_shown

    if webview:
        webview.start(debug=False)


if __name__ == "__main__":
    main()
