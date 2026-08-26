"""Ponto de entrada do plugin Logon AWS & Port Forwarding.
Inicializa a janela do aplicativo baseada em pywebview e registra a API de ponte JavaScript.
"""
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

try:
    import webview
except ImportError:
    webview = None

import importlib.util
from shared.web_utils import BasePluginApi, create_plugin_window

domain_path = PLUGIN_DIR / "domain.py"
spec = importlib.util.spec_from_file_location("logon_aws_domain", domain_path)
domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain)


class LogonAwsApi(BasePluginApi):
    """API JS exposta para a interface webview do plugin."""

    def get_initial_data(self) -> dict:
        config = domain.load_config()
        status = domain.tunnel_manager.get_status(config.get("local_port", 42586))
        return {
            "config": config,
            "status": status,
            "logs": domain.tunnel_manager.get_logs(),
        }

    def check_sts(self, data: dict) -> dict:
        profile = data.get("profile", "").strip()
        ok, msg = domain.check_sts_session(profile)
        return {"active": ok, "message": msg}

    def one_click_connect(self, data: dict) -> dict:
        profile = data.get("profile", "").strip()
        local_port = data.get("local_port", "")
        region = data.get("region", "sa-east-1")
        return domain.tunnel_manager.one_click_connect(
            profile=profile,
            local_port=local_port,
            region=region,
        )

    def sso_login(self, data: dict) -> dict:
        profile = data.get("profile", "").strip()
        return domain.tunnel_manager.run_sso_login(
            profile=profile,
        )

    def cancel_sso(self, data: Optional[dict] = None) -> dict:
        return domain.tunnel_manager.cancel_sso_login()

    def connect_tunnel(self, data: dict) -> dict:
        profile = data.get("profile", "").strip()
        local_port = data.get("local_port", "")
        region = data.get("region", "sa-east-1")
        return domain.tunnel_manager.start_tunnel(
            profile=profile,
            local_port=local_port,
            region=region,
        )

    def disconnect_tunnel(self) -> dict:
        return domain.tunnel_manager.stop_tunnel()

    def check_status(self, data: dict) -> dict:
        port = data.get("local_port", "")
        return domain.tunnel_manager.get_status(port)

    def get_logs(self) -> list:
        return domain.tunnel_manager.get_logs()

    def save_preferences(self, data: dict) -> dict:
        profile = data.get("profile", "").strip()
        local_port = int(data.get("local_port", 42586)) if data.get("local_port") else 42586
        ok = domain.save_config({"profile": profile, "local_port": local_port})
        return {"success": ok}

    def clear_logs(self) -> dict:
        domain.tunnel_manager.clear_logs()
        return {"success": True}


if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.logonaws")
    except Exception:
        pass


import atexit
import signal


def _setup_lifecycle_cleanup() -> None:
    """Registra rotinas de limpeza para encerramento de processos em atexit e sinais."""
    atexit.register(domain.tunnel_manager.stop_all)

    def _sig_handler(sig: int, frame: Any) -> None:
        domain.tunnel_manager.stop_all()
        sys.exit(0)

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, sig_name):
            try:
                signal.signal(getattr(signal, sig_name), _sig_handler)
            except Exception:
                pass


def main() -> None:
    _setup_lifecycle_cleanup()

    api = LogonAwsApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Logon AWS & Port Forwarding",
        entry_html=ui_index,
        js_api=api,
        width=740,
        height=720,
        min_size=(680, 600),
    )
    if webview and window:
        # Define ícone inicial desconectado assim que a janela estiver pronta
        def on_shown():
            domain.set_window_taskbar_icon(False)
            import threading
            threading.Timer(0.6, lambda: domain.set_window_taskbar_icon(False)).start()

        def on_closing():
            domain.tunnel_manager.stop_all()
            return True

        def on_closed():
            domain.tunnel_manager.stop_all()

        window.events.shown += on_shown
        window.events.closing += on_closing
        window.events.closed += on_closed
        webview.start(debug=False)


if __name__ == "__main__":
    main()
