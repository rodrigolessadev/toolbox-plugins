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

class ConverterDataApi(BasePluginApi):
    def convert(self, val: str) -> dict:
        return domain.convert_timestamp(val)

def main():
    api = ConverterDataApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="Converter Data",
        entry_html=ui_index,
        js_api=api,
        width=680,
        height=620,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
