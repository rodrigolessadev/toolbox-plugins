import sys
from pathlib import Path
PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import domain
import webview

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

    def filter_logs(self, text: str, regex_term: str, level: str, deduplicate: bool) -> dict:
        return domain.filter_log_text(text, regex_term, level, deduplicate)

def main():
    api = StractLogApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="Stract Log",
        entry_html=ui_index,
        js_api=api,
        width=780,
        height=760,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
