"""
Módulo de utilitários e infraestrutura para plugins baseados em pywebview.
Padroniza inicialização de janelas, comunicação com JS (bridge),
diálogos nativos do sistema operacional e tokens do Toolbox.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import webview
except ImportError:
    webview = None


# Tokens CSS Oficiais do Toolbox
TOOLBOX_THEME = {
    "bg": "#0e1014",
    "bg_card": "#161a21",
    "bg_input": "#12151c",
    "bg_hover": "#1e232d",
    "fg": "#e8eaed",
    "fg_muted": "#8b94a3",
    "border": "#2b3240",
    "border_focus": "#6aa3ff",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_fg": "#ffffff",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
}


def open_in_explorer(path: Path | str) -> bool:
    """Abre um diretório ou seleciona arquivo no explorador de arquivos nativo."""
    try:
        p = Path(path).resolve()
        if sys.platform == "win32":
            if p.is_file():
                subprocess.run(["explorer", f"/select,{str(p)}"], check=False)
            else:
                os.startfile(str(p))
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=False)
            return True
        else:
            subprocess.run(["xdg-open", str(p)], check=False)
            return True
    except Exception:
        return False


def copy_to_clipboard(text: str) -> bool:
    """Copia texto para a área de transferência do sistema operacional."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $args[0]"],
                input=text,
                text=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return True
        return False
    except Exception:
        return False


class BasePluginApi:
    """
    Classe base com utilitários para APIs expostas ao JavaScript (window.pywebview.api).
    Os métodos públicos podem ser invocados diretamente pelo frontend JS.
    """

    def get_theme(self) -> Dict[str, str]:
        """Retorna o dicionário de tokens de cores do tema Toolbox."""
        return TOOLBOX_THEME

    def open_path(self, path_str: str) -> Dict[str, Any]:
        """Abre caminho no explorador de arquivos."""
        success = open_in_explorer(path_str)
        return {"success": success}

    def copy_text(self, text: str) -> Dict[str, Any]:
        """Copia texto para o clipboard."""
        success = copy_to_clipboard(text)
        return {"success": success}

    def select_folder(self, initial_dir: Optional[str] = None) -> str:
        """Abre diálogo nativo para seleção de pastas."""
        if webview and webview.windows:
            win = webview.windows[0]
            directory = initial_dir if initial_dir and Path(initial_dir).exists() else ""
            res = win.create_file_dialog(webview.FOLDER_DIALOG, directory=directory)
            if res and len(res) > 0:
                return str(Path(res[0]).resolve())
        return ""

    def select_file(
        self,
        file_types: Optional[List[str]] = None,
        initial_dir: Optional[str] = None
    ) -> str:
        """Abre diálogo nativo para seleção de arquivo."""
        if webview and webview.windows:
            win = webview.windows[0]
            types = tuple(file_types) if file_types else ("Todos os Arquivos (*.*)",)
            directory = initial_dir if initial_dir and Path(initial_dir).exists() else ""
            res = win.create_file_dialog(webview.OPEN_DIALOG, directory=directory, file_types=types)
            if res and len(res) > 0:
                return str(Path(res[0]).resolve())
        return ""


def create_plugin_window(
    title: str,
    entry_html: Path | str,
    js_api: Optional[Any] = None,
    width: int = 720,
    height: int = 740,
    min_size: Tuple[int, int] = (640, 600),
    background_color: str = "#0e1014",
    debug: bool = False,
) -> Any:
    """
    Cria e configura a janela do plugin com parâmetros oficiais do Toolbox.
    """
    if webview is None:
        raise RuntimeError(
            "pywebview não está instalado. Execute: pip install pywebview>=5.0.0"
        )

    if sys.platform == "win32":
        try:
            import ctypes
            app_id = f"toolbox.plugin.{title.lower().replace(' ', '').replace('&', '').replace('—', '')}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    html_path = Path(entry_html).resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"Arquivo HTML de entrada não encontrado: {html_path}")

    url = str(html_path)

    window = webview.create_window(
        title=f"{title} — Toolbox",
        url=url,
        js_api=js_api or BasePluginApi(),
        width=width,
        height=height,
        min_size=min_size,
        background_color=background_color,
    )
    return window
