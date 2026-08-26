import importlib.util
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

from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import webview

domain_path = PLUGIN_DIR / "domain.py"
spec = importlib.util.spec_from_file_location("stract_json_domain", domain_path)
domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain)


def handle_ipc(input_data: dict) -> dict:
    req_id = input_data.get("request_id") or "req_stract_json"
    raw_content = input_data.get("content") or input_data.get("raw_content") or ""
    target_field = input_data.get("field") or input_data.get("target_field") or ""
    try:
        result = domain.extract_json_from_text(raw_content, target_field)
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "success",
            "result": result
        }
    except Exception as e:
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "error",
            "error": str(e)
        }


class StractJsonApi(BasePluginApi):
    def extract_json(self, raw_text: str, target_field: str = "") -> dict:
        return domain.extract_json_from_text(raw_text, target_field)

    def copy_text(self, text: str) -> dict:
        try:
            copy_to_clipboard(text or "")
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_plugin_version(self) -> dict:
        try:
            pj = PLUGIN_DIR / "plugin.json"
            if pj.exists():
                data = json.loads(pj.read_text(encoding="utf-8"))
                return {"success": True, "version": data.get("version", "1.2.0")}
        except Exception:
            pass
        return {"success": True, "version": "1.2.0"}


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.stractjson")
        except Exception:
            pass

    api = StractJsonApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Stract JSON",
        entry_html=ui_index,
        js_api=api,
        width=800,
        height=740,
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
