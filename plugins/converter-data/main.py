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
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.converterdata")
        except Exception:
            pass

    api = ConverterDataApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Converter Data",
        entry_html=ui_index,
        js_api=api,
        width=700,
        height=660,
        min_size=(620, 580),
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
