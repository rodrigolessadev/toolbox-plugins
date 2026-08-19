import sys
import importlib.util
from pathlib import Path

PLUGINS_ROOT = Path(__file__).parent.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import webview

def _load_domain():
    domain_path = Path(__file__).parent / "domain.py"
    spec = importlib.util.spec_from_file_location("ao_domain", domain_path)
    dom = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dom)
    return dom

domain = _load_domain()

def handle_ipc(input_data: dict) -> dict:
    action = input_data.get("action") or input_data.get("command") or ""
    inp = input_data.get("input") or {}
    dom = _load_domain()
    opts = inp.get("options") or {}
    try:
        if action in ["discover", "discovery"]:
            res = dom.discover_analysis_directory(inp.get("analysis_directory", ""), opts)
        elif action in ["orchestrate", "run_analysis", "run"]:
            res = dom.run_orchestration(inp.get("analysis_directory", ""), opts)
        elif action in ["run_single", "run_single_plugin"]:
            res = dom.run_single_plugin(inp.get("analysis_directory", ""), inp.get("plugin_name", ""), opts)
        elif action in ["validate", "validate_results"]:
            res = dom.validate_results_directory(inp.get("results_directory", ""))
        elif action in ["resume", "resume_orchestration"]:
            res = dom.resume_orchestration(inp.get("target_directory", ""), opts)
        else:
            return {"protocol_version": "1.0", "status": "error", "error": f"Ação desconhecida: {action}"}
        return {"protocol_version": "1.0", "status": "success", "result": res}
    except Exception as e:
        return {"protocol_version": "1.0", "status": "error", "error": str(e)}

class AnalysisOrchestratorApi(BasePluginApi):
    def pick_analysis_dir(self) -> dict:
        path = self.select_folder()
        if not path:
            return {"success": False}
        return {"success": True, "path": path}

    def discover_directory(self, dir_path: str) -> dict:
        try:
            dom = _load_domain()
            return dom.discover_analysis_directory(dir_path)
        except Exception as e:
            return {"success": False, "message": str(e)}

    def run_orchestration(self, dir_path: str, options: dict) -> dict:
        try:
            dom = _load_domain()
            return dom.run_orchestration(dir_path, options)
        except Exception as e:
            return {"success": False, "message": str(e)}

def main():
    api = AnalysisOrchestratorApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="Analysis Orchestrator",
        entry_html=ui_index,
        js_api=api,
        width=780,
        height=760,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
