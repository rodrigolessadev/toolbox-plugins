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

class GeradorMarcacoesApi(BasePluginApi):
    def gerar_inserts(self, params: dict) -> dict:
        return domain.gerar_sql_marcacoes(
            tabela=params.get("tabela", "R070ACC"),
            banco=params.get("banco", "ORACLE"),
            campos_fixos=params.get("campos_fixos", {}),
            start_date=params.get("start_date", ""),
            end_date=params.get("end_date", ""),
            horarios=params.get("horarios", ["08:00", "12:00", "13:00", "18:00"]),
            variacao_minutos=int(params.get("variacao_minutos", 2)),
            pular_fins_de_semana=bool(params.get("pular_fins_de_semana", True)),
        )

def main():
    api = GeradorMarcacoesApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="Gerador de Marcações SQL",
        entry_html=ui_index,
        js_api=api,
        width=780,
        height=760,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
