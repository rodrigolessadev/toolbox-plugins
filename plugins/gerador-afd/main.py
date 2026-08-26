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

class GeradorAfdApi(BasePluginApi):
    def gerar(self, params: dict) -> dict:
        return domain.gerar_afd(
            rep_number=params.get("rep_number", "00000000000000001"),
            cnpj_cpf=params.get("cnpj_cpf", "00000000000191"),
            razao_social=params.get("razao_social", "EMPRESA TESTE LTDA"),
            local_prestacao=params.get("local_prestacao", "MATRIZ"),
            pis=params.get("pis", "12345678901"),
            nome_empregado=params.get("nome_empregado", "COLABORADOR TESTE"),
            start_date=params.get("start_date", ""),
            end_date=params.get("end_date", ""),
            horarios=params.get("horarios", ["08:00", "12:00", "13:00", "18:00"]),
            variacao_minutos=int(params.get("variacao_minutos", 2)),
            pular_fins_de_semana=bool(params.get("pular_fins_de_semana", True)),
        )

    def salvar_arquivo(self, filename: str, content: str) -> dict:
        try:
            if not webview.windows:
                return {"success": False, "error": "Janela não encontrada."}
            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=filename or "AFD.txt",
                file_types=("Arquivo AFD (*.txt)", "Todos os arquivos (*.*)")
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
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.geradorafd")
        except Exception:
            pass

    api = GeradorAfdApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Gerador de AFD",
        entry_html=ui_index,
        js_api=api,
        width=820,
        height=780,
        min_size=(680, 600),
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
