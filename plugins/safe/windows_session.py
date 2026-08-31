"""
Módulo de Monitoramento de Sessão do Windows para o Cofre Seguro.
Intercepta eventos de bloqueio do sistema operacional (Win + L / Suspensão)
via WTSRegisterSessionNotification na mensagem WM_WTSSESSION_CHANGE.
"""

from __future__ import annotations

import sys
import threading
from typing import Callable, Optional

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    WM_WTSSESSION_CHANGE = 0x02B1
    WTS_SESSION_LOCK = 0x7
    WTS_SESSION_UNLOCK = 0x8
    NOTIFY_FOR_THIS_SESSION = 0

    LPARAM = ctypes.c_ssize_t
    WPARAM = ctypes.c_size_t
    LRESULT = ctypes.c_ssize_t

    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)

    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HICON),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]


try:
    from logger import get_logger
except ImportError:
    try:
        from .logger import get_logger
    except ImportError:
        import logging
        def get_logger(name="safe"):
            return logging.getLogger(name)

logger = get_logger("safe.windows_session")

_listener_thread: Optional[threading.Thread] = None
_registered_callback: Optional[Callable[[], None]] = None
_global_proc_ref: Any = None
_listener_hwnd: Optional[int] = None


def _cleanup_session_listener() -> None:
    """Envia WM_QUIT para o listener thread no desligamento do processo."""
    global _listener_hwnd
    if _listener_hwnd and sys.platform == "win32":
        try:
            ctypes.windll.user32.PostMessageW(_listener_hwnd, 0x0012, 0, 0)  # WM_QUIT = 0x0012
            logger.debug("Session listener finalizado com sucesso via WM_QUIT.")
        except Exception as e:
            logger.debug(f"Erro ao enviar WM_QUIT para session listener: {e}")


import atexit
atexit.register(_cleanup_session_listener)


def start_session_lock_listener(on_lock_callback: Callable[[], None]) -> bool:
    """
    Inicia um message loop em thread daemon para capturar eventos de bloqueio do Windows.
    Retorna True se o listener foi inicializado com sucesso.
    """
    global _listener_thread, _registered_callback, _global_proc_ref, _listener_hwnd

    if sys.platform != "win32":
        return False

    _registered_callback = on_lock_callback

    if _listener_thread and _listener_thread.is_alive():
        return True

    def listener_loop():
        global _global_proc_ref, _listener_hwnd
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            wtsapi32 = ctypes.windll.wtsapi32

            user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
            user32.DefWindowProcW.restype = LRESULT

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == WM_WTSSESSION_CHANGE:
                    if wparam == WTS_SESSION_LOCK:
                        if _registered_callback:
                            try:
                                _registered_callback()
                            except Exception as e:
                                print(f"[SafeSessionListener] Erro no callback de lock: {e}", file=sys.stderr)
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            _global_proc_ref = WNDPROC(wnd_proc)

            hinst = kernel32.GetModuleHandleW(None)
            cls_name = f"SafeSessionListenerWindow_{id(_global_proc_ref)}"

            wc = WNDCLASS()
            wc.hInstance = hinst
            wc.lpszClassName = cls_name
            wc.lpfnWndProc = _global_proc_ref

            atom = user32.RegisterClassW(ctypes.byref(wc))
            if not atom:
                return

            hwnd = user32.CreateWindowExW(0, cls_name, "SafeSessionListener", 0, 0, 0, 0, 0, 0, 0, hinst, 0)
            if not hwnd:
                return

            _listener_hwnd = hwnd

            try:
                wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)
            except Exception:
                pass

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass

    _listener_thread = threading.Thread(target=listener_loop, daemon=True, name="SafeOSLockListener")
    _listener_thread.start()
    return True
