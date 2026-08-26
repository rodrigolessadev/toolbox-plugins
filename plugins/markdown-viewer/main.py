import os
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


class MarkdownViewerApi(BasePluginApi):
    """API exposta para a interface WebView do visualizador de Markdown."""

    def open_file_dialog(self) -> dict:
        """Abre caixa de diálogo para seleção de arquivo Markdown."""
        try:
            if not webview.windows:
                return {"success": False, "error": "Janela principal não encontrada."}
            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Markdown (*.md;*.markdown;*.mdown;*.mkd)", "Todos os arquivos (*.*)")
            )
            if not result:
                return {"success": False, "cancelled": True}

            selected_path = result[0] if isinstance(result, (list, tuple)) else result
            return domain.read_markdown_file(selected_path)
        except Exception as exc:
            return {"success": False, "error": f"Erro ao abrir arquivo: {str(exc)}"}

    def save_file_dialog(self, content: str, current_path: str = "") -> dict:
        """Salva o arquivo atual ou solicita local para salvar novo arquivo."""
        try:
            if current_path and Path(current_path).exists():
                return domain.save_markdown_file(current_path, content)

            if not webview.windows:
                return {"success": False, "error": "Janela principal não encontrada."}

            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="documento.md",
                file_types=("Markdown (*.md)", "Todos os arquivos (*.*)")
            )
            if not result:
                return {"success": False, "cancelled": True}

            save_path = result[0] if isinstance(result, (list, tuple)) else result
            return domain.save_markdown_file(save_path, content)
        except Exception as exc:
            return {"success": False, "error": f"Erro ao salvar arquivo: {str(exc)}"}

    def read_file(self, path: str) -> dict:
        """Lê um arquivo do disco a partir do caminho recebido."""
        return domain.read_markdown_file(path)

    def save_file(self, path: str, content: str) -> dict:
        """Salva o conteúdo em um caminho explícito."""
        return domain.save_markdown_file(path, content)

    def analyze_text(self, content: str) -> dict:
        """Retorna estatísticas do texto Markdown."""
        return {"success": True, "stats": domain.analyze_markdown(content)}

    def export_html_dialog(self, title: str, html_body: str) -> dict:
        """Exporta o HTML gerado para um arquivo .html standalone."""
        try:
            if not webview.windows:
                return {"success": False, "error": "Janela principal não encontrada."}
            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="documento.html",
                file_types=("HTML Document (*.html)", "Todos os arquivos (*.*)")
            )
            if not result:
                return {"success": False, "cancelled": True}

            save_path = result[0] if isinstance(result, (list, tuple)) else result
            doc = domain.export_html_document(title, html_body)
            Path(save_path).write_text(doc, encoding="utf-8")
            return {"success": True, "path": save_path}
        except Exception as exc:
            return {"success": False, "error": f"Erro ao exportar HTML: {str(exc)}"}


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.markdownviewer")
        except Exception:
            pass

    api = MarkdownViewerApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Visualizador de Markdown",
        entry_html=ui_index,
        js_api=api,
        width=1000,
        height=720,
        min_size=(720, 520),
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
