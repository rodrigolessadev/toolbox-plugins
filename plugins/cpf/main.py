import sys
from pathlib import Path
PLUGINS_ROOT = Path(__file__).parent.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import domain
import webview

class CpfApi(BasePluginApi):
    def validate(self, cpf: str) -> dict:
        valid = domain.is_valid_cpf(cpf)
        formatted = domain.format_cpf(cpf) if valid else cpf
        return {"valid": valid, "formatted": formatted, "digits": domain.only_digits(cpf)}

    def generate(self, formatted: bool) -> str:
        return domain.generate_cpf(formatted)

def main():
    api = CpfApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="Validador & Gerador de CPF",
        entry_html=ui_index,
        js_api=api,
        width=640,
        height=580,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
