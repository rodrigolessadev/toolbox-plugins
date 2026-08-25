import sys
import importlib.util
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import webview

def _load_domain():
    domain_path = Path(__file__).parent / "domain.py"
    spec = importlib.util.spec_from_file_location("har_kibana_domain", domain_path)
    dom = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dom)
    return dom

domain = _load_domain()

def handle_ipc(input_data: dict) -> dict:
    req_id = input_data.get("request_id") or "req_har_kibana"
    raw_content = input_data.get("content") or input_data.get("raw_content") or input_data.get("har_content") or ""
    options = input_data.get("options") or {}
    try:
        dom = _load_domain()
        result = dom.plan_har_kibana_queries(raw_content, options=options)
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

class HarKibanaApi(BasePluginApi):
    def pick_har_file(self) -> dict:
        path = self.select_file([("Arquivos HAR (*.har;*.json)", "*.har;*.json")])
        if not path:
            return {"success": False}
        p = Path(path)
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return {"success": True, "path": path, "name": p.name, "content": content}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def plan_queries(self, har_content: str) -> dict:
        try:
            dom = _load_domain()
            res = dom.plan_har_kibana_queries(har_content)
            return {"success": True, "data": res}
        except Exception as e:
            return {"success": False, "message": str(e)}

def main():
    api = HarKibanaApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="HAR Kibana Planner",
        entry_html=ui_index,
        js_api=api,
        width=780,
        height=760,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
