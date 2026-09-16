"""
Módulo de utilitários e infraestrutura para plugins baseados em pywebview.
Padroniza inicialização de janelas, comunicação com JS (bridge),
diálogos nativos do sistema operacional e tokens do Toolbox.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    if text is None:
        return False
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
                input=text,
                text=True,
                encoding="utf-8",
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return res.returncode == 0
        elif sys.platform == "darwin":
            res = subprocess.run(
                ["pbcopy"],
                input=text,
                text=True,
                encoding="utf-8",
                check=False,
            )
            return res.returncode == 0
        else:
            # Linux: tenta xclip e depois wl-copy
            try:
                res = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                if res.returncode == 0:
                    return True
            except FileNotFoundError:
                pass
            res = subprocess.run(
                ["wl-copy"],
                input=text,
                text=True,
                encoding="utf-8",
                check=False,
            )
            return res.returncode == 0
    except Exception:
        return False


def sanitize_file_types(file_types: Sequence[str]) -> Tuple[str, ...]:
    """Sanitiza strings de filtros para garantir compatibilidade estrita com a regex do pywebview."""
    sanitized = []
    for ft in file_types:
        ft_str = str(ft).strip()
        m = re.match(r"^(.*?)\s*(\(\*.*?\))$", ft_str)
        if m:
            desc, ext = m.group(1), m.group(2)
            clean_desc = desc.replace("/", " ou ")
            clean_desc = re.sub(r"[^\w\s]", "", clean_desc)
            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
            sanitized.append(f"{clean_desc} {ext}")
        else:
            sanitized.append(ft_str)
    return tuple(sanitized)


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
            types = sanitize_file_types(file_types) if file_types else ("Todos os Arquivos (*.*)",)
            directory = initial_dir if initial_dir and Path(initial_dir).exists() else ""
            res = win.create_file_dialog(webview.OPEN_DIALOG, directory=directory, file_types=types)
            if res and len(res) > 0:
                return str(Path(res[0]).resolve())
        return ""


def set_window_taskbar_icon(icon_path: Optional[Path | str] = None, hwnd: Optional[int] = None) -> bool:
    """
    Atualiza o ícone da janela e da barra de tarefas no Windows (WM_SETICON).
    Executado de forma segura e idempotente em sistemas Win32.
    """
    if sys.platform != "win32":
        return False

    if not icon_path:
        return False

    target_icon = Path(icon_path).resolve()
    if not target_icon.is_file():
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        SWP_FLAGS = SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED

        h_icon_big = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            32,
            32,
            LR_LOADFROMFILE,
        )
        h_icon_small = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            16,
            16,
            LR_LOADFROMFILE,
        )

        if not h_icon_big and not h_icon_small:
            return False

        if hwnd:
            target_hwnds = [hwnd]
        else:
            current_pid = os.getpid()
            target_hwnds = []

            def _enum_windows_cb(handle: int, _: Any) -> bool:
                lpdw_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(handle, ctypes.byref(lpdw_pid))
                if lpdw_pid.value == current_pid:
                    if user32.IsWindowVisible(handle):
                        target_hwnds.append(handle)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(_enum_windows_cb), 0)

        success = False
        for target in target_hwnds:
            if h_icon_big:
                user32.SendMessageW(target, WM_SETICON, ICON_BIG, h_icon_big)
            if h_icon_small:
                user32.SendMessageW(target, WM_SETICON, ICON_SMALL, h_icon_small)
            user32.SetWindowPos(target, 0, 0, 0, 0, 0, SWP_FLAGS)
            success = True
        return success
    except Exception:
        pass
    return False


def resolve_plugin_metadata(
    plugin_dir: Optional[Path | str] = None,
    entry_html: Optional[Path | str] = None
) -> Dict[str, Any]:
    """Extrai metadados essenciais de plugin.json a partir de plugin_dir ou entry_html."""
    pdir: Optional[Path] = None
    if plugin_dir:
        pdir = Path(plugin_dir).resolve()
    elif entry_html:
        cand = Path(entry_html).resolve().parent.parent
        if (cand / "plugin.json").is_file():
            pdir = cand

    if pdir and (pdir / "plugin.json").is_file():
        try:
            import json
            meta = json.loads((pdir / "plugin.json").read_text(encoding="utf-8"))
            meta["plugin_dir"] = pdir
            return meta
        except Exception:
            pass
    return {"plugin_dir": pdir} if pdir else {}


def resolve_plugin_icon(plugin_dir: Optional[Path], icon_name: Optional[str] = None) -> Optional[Path]:
    """Localiza o arquivo de ícone .ico oficial do plugin em ui/assets/."""
    if not plugin_dir or not (plugin_dir / "ui" / "assets").is_dir():
        return None

    assets_dir = plugin_dir / "ui" / "assets"

    # 1. Ícone específico pelo nome no manifesto
    if icon_name:
        specific = assets_dir / f"{icon_name}.ico"
        if specific.is_file() and specific.stat().st_size > 0:
            return specific

    # 2. Fallback: qualquer .ico na pasta assets
    any_icos = sorted(assets_dir.glob("*.ico"))
    if any_icos and any_icos[0].is_file() and any_icos[0].stat().st_size > 0:
        return any_icos[0]

    return None


def create_plugin_window(
    title: str,
    entry_html: Path | str,
    js_api: Optional[Any] = None,
    plugin_dir: Optional[Path | str] = None,
    version: Optional[str] = None,
    icon_path: Optional[Path | str] = None,
    width: int = 720,
    height: int = 740,
    min_size: Tuple[int, int] = (640, 600),
    background_color: str = "#0e1014",
    debug: bool = False,
) -> Any:
    """
    Cria e configura a janela do plugin com parâmetros oficiais do Toolbox.
    Formata o título oficial com versão '{Nome} v{X.Y.Z} — Toolbox', registra o AppUserModelID
    e configura automaticamente o ícone na barra de tarefas no Windows.
    """
    if webview is None:
        raise RuntimeError(
            "pywebview não está instalado. Execute: pip install pywebview>=5.0.0"
        )

    html_path = Path(entry_html).resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"Arquivo HTML de entrada não encontrado: {html_path}")

    url = str(html_path)

    # Resolução de metadados do plugin
    meta = resolve_plugin_metadata(plugin_dir=plugin_dir, entry_html=entry_html)
    p_dir = meta.get("plugin_dir") or (Path(plugin_dir).resolve() if plugin_dir else None)

    # Resolução de versão
    effective_version = version or meta.get("version")

    # Formatação do Título Oficial: "{Nome} v{version} — Toolbox"
    base_title = re.sub(r"\s+[—\-]\s+Toolbox\s*$", "", title).strip()
    if effective_version and not re.search(rf"\bv?{re.escape(str(effective_version))}\b", base_title):
        final_title = f"{base_title} v{effective_version} — Toolbox"
    else:
        final_title = f"{base_title} — Toolbox"

    # Resolução do ícone da barra de tarefas
    effective_icon: Optional[Path] = None
    if icon_path:
        cand_icon = Path(icon_path).resolve()
        if cand_icon.is_file():
            effective_icon = cand_icon
    if not effective_icon:
        effective_icon = resolve_plugin_icon(p_dir, meta.get("icon"))

    # Configuração de AppUserModelID no Windows
    if sys.platform == "win32":
        try:
            import ctypes
            plugin_id = meta.get("id") or (p_dir.name if p_dir else None) or re.sub(r"[^\w]", "", base_title).lower()
            app_id = f"toolbox.plugin.{plugin_id}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    window = webview.create_window(
        title=final_title,
        url=url,
        js_api=js_api or BasePluginApi(),
        width=width,
        height=height,
        min_size=min_size,
        background_color=background_color,
    )

    # Bind automático do ícone da barra de tarefas no Windows
    if sys.platform == "win32" and effective_icon:
        try:
            if hasattr(window, "events") and hasattr(window.events, "shown"):
                def _auto_taskbar_icon() -> None:
                    set_window_taskbar_icon(effective_icon)
                    import threading
                    threading.Timer(0.5, lambda: set_window_taskbar_icon(effective_icon)).start()

                window.events.shown += _auto_taskbar_icon
        except Exception:
            pass

    return window

