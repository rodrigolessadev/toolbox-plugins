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

class CalcJornadasApi(BasePluginApi):
    def calcular(self, entradas: list, saidas: list, jornada_prevista: str) -> dict:
        j_min = domain.hora_para_min(jornada_prevista) if jornada_prevista else 480
        return domain.calcular_totais_jornada(entradas, saidas, j_min)

def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.calcjornadas")
        except Exception:
            pass

    api = CalcJornadasApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Calculadora de Jornadas",
        entry_html=ui_index,
        js_api=api,
        width=740,
        height=660,
        min_size=(640, 580),
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
