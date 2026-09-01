import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

import importlib.util
from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
import webview

domain_path = PLUGIN_DIR / "domain.py"
spec = importlib.util.spec_from_file_location("markdown_viewer_domain", domain_path)
domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain)


class MarkdownViewerApi(BasePluginApi):
    """API exposta para a interface WebView do visualizador de Markdown."""

    def __init__(self, initial_file: Optional[str] = None):
        super().__init__()
        self.initial_file = initial_file

    def get_initial_file(self) -> dict:
        """Retorna o arquivo passado como argumento inicial na inicialização, se houver."""
        if self.initial_file and Path(self.initial_file).exists():
            return domain.read_markdown_file(self.initial_file)
        return {"success": False}

    def open_file_dialog(self) -> dict:
        """Abre caixa de diálogo para seleção de um ou múltiplos arquivos Markdown."""
        try:
            if not webview.windows:
                return {"success": False, "error": "Janela principal não encontrada."}
            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=("Markdown (*.md;*.markdown;*.mdown;*.mkd)", "Todos os arquivos (*.*)")
            )
            if not result:
                return {"success": False, "cancelled": True}

            file_paths = result if isinstance(result, (list, tuple)) else [result]
            docs = []
            for p in file_paths:
                res = domain.read_markdown_file(p)
                if res.get("success"):
                    docs.append(res)

            if not docs:
                return {"success": False, "error": "Nenhum arquivo válido pôde ser lido."}

            return {
                "success": True,
                "files": docs,
                "data": docs[0],
                "path": docs[0].get("path", ""),
                "filename": docs[0].get("filename", ""),
                "content": docs[0].get("content", ""),
                "mtime": docs[0].get("mtime", 0),
            }
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

    def get_file_info(self, path: str) -> dict:
        """Retorna informações de modificação do arquivo para Hot-Reload."""
        return domain.get_file_info(path)

    def get_plugin_version(self) -> dict:
        """Retorna a versão do plugin declarada no plugin.json."""
        try:
            pj = PLUGIN_DIR / "plugin.json"
            if pj.exists():
                import json
                data = json.loads(pj.read_text(encoding="utf-8"))
                return {"success": True, "version": data.get("version", "1.0.0")}
        except Exception:
            pass
        return {"success": True, "version": "1.0.0"}

    def save_session(self, session_data: dict, snapshots: Optional[dict] = None) -> dict:
        """Persiste o estado da sessão e os snapshots temporários das abas."""
        return domain.save_session(session_data, snapshots)

    def load_session(self) -> dict:
        """Carrega a sessão prévia e os conteúdos salvos nos snapshots."""
        return domain.load_session()

    def delete_tab_snapshot(self, tab_id: str) -> dict:
        """Remove o snapshot de uma aba fechada ou descartada."""
        return domain.delete_tab_snapshot(tab_id)

    def clear_session(self) -> dict:
        """Limpa todos os snapshots e histórico da sessão."""
        return domain.clear_all_session()



def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.markdownviewer")
        except Exception:
            pass

    initial_file = sys.argv[1] if len(sys.argv) > 1 and Path(sys.argv[1]).exists() else None
    api = MarkdownViewerApi(initial_file=initial_file)
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
