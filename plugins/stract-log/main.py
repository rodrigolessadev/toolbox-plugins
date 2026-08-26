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
spec = importlib.util.spec_from_file_location("stract_log_domain", domain_path)
domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain)


def handle_ipc(input_data: dict) -> dict:
    req_id = input_data.get("request_id") or "req_stract_log"
    content = input_data.get("content") or input_data.get("text") or ""
    regex_term = input_data.get("regex") or input_data.get("regex_term") or ""
    level = input_data.get("level") or "TODOS"
    deduplicate = bool(input_data.get("deduplicate", False))
    try:
        result = domain.filter_log_text(content, regex_term, level, deduplicate)
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


class StractLogApi(BasePluginApi):
    def pick_log_file(self) -> dict:
        path = self.select_file([("Arquivos de Log (*.log;*.txt)", "*.log;*.txt")])
        if not path:
            return {"success": False}
        p = Path(path)
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return {"success": True, "path": path, "name": p.name, "content": content}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def filter_logs(self, text: str, regex_term: str = "", level: str = "", deduplicate: bool = False) -> dict:
        return domain.filter_log_text(text, regex_term, level, deduplicate)

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
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.stractlog")
        except Exception:
            pass

    api = StractLogApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Stract Log",
        entry_html=ui_index,
        js_api=api,
        width=820,
        height=780,
        min_size=(700, 580),
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
