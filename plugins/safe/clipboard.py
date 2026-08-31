"""
Módulo de Área de Transferência Segura (Secure Clipboard) - Plugin Safe (Cofre Seguro).

Fornece gravação nativa direta no clipboard com proteção contra monitoramento e histórico
do Windows 10/11 (ExcludeClipboardContentFromMonitorProcessing, CanIncludeInClipboardHistory),
além de temporizador de higienização automática (auto-clear).
"""

from __future__ import annotations

import hashlib
import sys
import threading
import time
from typing import Optional

try:
    from .logger import get_logger
except ImportError:
    try:
        from logger import get_logger
    except ImportError:
        import logging
        def get_logger(name="safe"):
            return logging.getLogger(name)

logger = get_logger("safe.clipboard")

_last_copied_hash: Optional[str] = None
_clear_timer: Optional[threading.Timer] = None
_timer_lock = threading.Lock()


def _is_windows() -> bool:
    return sys.platform == "win32"


if _is_windows():
    import ctypes
    from ctypes import wintypes

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL


def get_clipboard_text() -> Optional[str]:
    """Recupera o texto atual da área de transferência."""
    if _is_windows():
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Tenta abrir o clipboard com retentativas para evitar colisões
        opened = False
        for _ in range(5):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)

        if not opened:
            return None

        try:
            h_mem = user32.GetClipboardData(13)  # CF_UNICODETEXT = 13
            if not h_mem:
                return None
            ptr = kernel32.GlobalLock(h_mem)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(h_mem)
        finally:
            user32.CloseClipboard()
    else:
        import subprocess
        try:
            if sys.platform == "darwin":
                res = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
                return res.stdout if res.returncode == 0 else None
            else:
                res = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, check=False)
                return res.stdout if res.returncode == 0 else None
        except Exception:
            return None


def clear_clipboard() -> bool:
    """Limpa a área de transferência do sistema operacional."""
    if _is_windows():
        user32 = ctypes.windll.user32
        opened = False
        for _ in range(5):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)

        if not opened:
            return False

        try:
            return bool(user32.EmptyClipboard())
        finally:
            user32.CloseClipboard()
    else:
        import subprocess
        try:
            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input="", text=True, check=False)
                return True
            else:
                subprocess.run(["xclip", "-selection", "clipboard"], input="", text=True, check=False)
                return True
        except Exception:
            return False


def _set_clipboard_data_dword(format_name: str, value: int = 0) -> None:
    """Define um formato customizado do Windows com valor DWORD (ex.: desabilitar histórico)."""
    fmt = user32.RegisterClipboardFormatW(format_name)
    if fmt:
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, 4)
        if h_mem:
            ptr = kernel32.GlobalLock(h_mem)
            if ptr:
                ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(value)), 4)
                kernel32.GlobalUnlock(h_mem)
                user32.SetClipboardData(fmt, h_mem)


def _auto_clear_worker(expected_hash: str) -> None:
    """Callback disparado pelo timer para higienizar o clipboard caso a senha ainda resida nele."""
    try:
        current_text = get_clipboard_text()
        if current_text is not None:
            current_hash = hashlib.sha256(current_text.encode("utf-8")).hexdigest()
            if current_hash == expected_hash:
                clear_clipboard()
                logger.info("Área de transferência higienizada automaticamente por segurança (timeout atingido).")
            else:
                logger.debug("Higienização cancelada: usuário copiou outro conteúdo para a área de transferência.")
    except Exception as e:
        logger.debug(f"Aviso na execução do auto-clear do clipboard: {e}")


def copy_to_clipboard_secure(text: str, auto_clear_seconds: int = 30) -> bool:
    """
    Copia texto para a área de transferência com formatos de segurança do Windows
    e agenda a higienização automática após auto_clear_seconds.
    """
    if text is None:
        return False

    global _last_copied_hash, _clear_timer

    success = False

    if _is_windows():
        opened = False
        for _ in range(5):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)

        if not opened:
            logger.warning("Falha ao abrir a área de transferência do Windows.")
            return False

        try:
            user32.EmptyClipboard()

            # 1. Aloca e copia o texto Unicode
            text_bytes = (text + "\0").encode("utf-16le")
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
            if h_mem:
                ptr = kernel32.GlobalLock(h_mem)
                if ptr:
                    ctypes.memmove(ptr, text_bytes, len(text_bytes))
                    kernel32.GlobalUnlock(h_mem)
                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)

            # 2. Formato do Windows 10/11: Excluir de processamento de monitores de clipboard
            fmt_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
            if fmt_exclude:
                h_dummy = kernel32.GlobalAlloc(GMEM_MOVEABLE, 1)
                if h_dummy:
                    user32.SetClipboardData(fmt_exclude, h_dummy)

            # 3. Formato do Windows 10/11: Excluir do Histórico de Clipboard (Win + V)
            _set_clipboard_data_dword("CanIncludeInClipboardHistory", 0)

            # 4. Formato do Windows 10/11: Excluir de Sincronização em Nuvem (Cloud Clipboard)
            _set_clipboard_data_dword("CanUploadToCloudStore", 0)

            success = True
        except Exception as e:
            logger.error(f"Erro ao gravar na área de transferência segura: {e}")
            success = False
        finally:
            user32.CloseClipboard()
    else:
        # Fallback para macOS / Linux
        import subprocess
        try:
            if sys.platform == "darwin":
                res = subprocess.run(["pbcopy"], input=text, text=True, encoding="utf-8", check=False)
                success = (res.returncode == 0)
            else:
                res = subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, encoding="utf-8", check=False)
                success = (res.returncode == 0)
        except Exception as e:
            logger.error(f"Erro no fallback de clipboard: {e}")
            success = False

    if success and auto_clear_seconds > 0:
        with _timer_lock:
            if _clear_timer and _clear_timer.is_alive():
                _clear_timer.cancel()

            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            _last_copied_hash = text_hash

            _clear_timer = threading.Timer(auto_clear_seconds, _auto_clear_worker, args=[text_hash])
            _clear_timer.daemon = True
            _clear_timer.start()

    return success
