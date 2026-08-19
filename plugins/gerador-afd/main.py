from domain import calcular_crc16, limpar_numero, format_dh, gerar_afd
import sys
from pathlib import Path
PLUGINS_ROOT = Path(__file__).parent.parent
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

def main():
    api = GeradorAfdApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="Gerador de AFD",
        entry_html=ui_index,
        js_api=api,
        width=780,
        height=760,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
