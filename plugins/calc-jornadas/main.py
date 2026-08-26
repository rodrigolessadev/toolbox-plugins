import sys
import importlib.util
from pathlib import Path
from typing import Optional, Dict, Any, List

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import webview

domain_path = PLUGIN_DIR / "domain.py"
spec = importlib.util.spec_from_file_location("calc_jornadas_domain", domain_path)
domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain)


class CalcJornadasApi(BasePluginApi):
    """API bridge exposta para a interface WebView da Calculadora de Jornadas."""

    def consolidar(self, grupos: List[Dict[str, str]], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params_dict = params or {}
        
        ini_raw = params_dict.get("inicio_noturno", 1320)
        fim_raw = params_dict.get("fim_noturno", 300)
        fator_raw = params_dict.get("fator_minutos", 52.5)

        ini_min = domain.hora_para_min(str(ini_raw)) if isinstance(ini_raw, str) and ":" in ini_raw else int(ini_raw)
        fim_min = domain.hora_para_min(str(fim_raw)) if isinstance(fim_raw, str) and ":" in fim_raw else int(fim_raw)
        try:
            fator_val = float(str(fator_raw).replace(",", "."))
        except Exception:
            fator_val = 52.5

        p = domain.ParametrosJornada(
            inicio_noturno=ini_min,
            fim_noturno=fim_min,
            fator_minutos=fator_val,
        )
        return domain.consolidar_jornadas(grupos, p)

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
        width=780,
        height=680,
        min_size=(680, 580),
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
