"""Ponto de entrada do plugin Logon AWS & Port Forwarding.
Inicializa a janela do aplicativo baseada em pywebview e registra a API de ponte JavaScript.
"""
from __future__ import annotations

import sys
from pathlib import Path

PLUGINS_ROOT = Path(__file__).parent.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

try:
    import webview
except ImportError:
    webview = None

from shared.web_utils import BasePluginApi, create_plugin_window
import domain


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
        profile = data.get("profile", "rodrigo.lessa")
        ok, msg = domain.check_sts_session(profile)
        return {"active": ok, "message": msg}

    def one_click_connect(self, data: dict) -> dict:
        profile = data.get("profile", "rodrigo.lessa")
        local_port = data.get("local_port", 42586)
        region = data.get("region", "sa-east-1")
        return domain.tunnel_manager.one_click_connect(
            profile=profile,
            local_port=int(local_port),
            region=region,
        )

    def sso_login(self, data: dict) -> dict:
        profile = data.get("profile", "rodrigo.lessa")
        return domain.tunnel_manager.run_sso_login(
            profile=profile,
        )

    def cancel_sso(self, data: Optional[dict] = None) -> dict:
        return domain.tunnel_manager.cancel_sso_login()

    def connect_tunnel(self, data: dict) -> dict:
        profile = data.get("profile", "rodrigo.lessa")
        local_port = data.get("local_port", 42586)
        region = data.get("region", "sa-east-1")
        return domain.tunnel_manager.start_tunnel(
            profile=profile,
            local_port=int(local_port),
            region=region,
        )

    def disconnect_tunnel(self) -> dict:
        return domain.tunnel_manager.stop_tunnel()

    def check_status(self, data: dict) -> dict:
        port = int(data.get("local_port", 42586)) if data.get("local_port") else 42586
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


def main() -> None:
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
    if webview:
        # Define ícone inicial desconectado assim que a janela estiver pronta
        def on_shown():
            domain.set_window_taskbar_icon(False)
            import threading
            threading.Timer(0.6, lambda: domain.set_window_taskbar_icon(False)).start()

        if window:
            window.events.shown += on_shown
        webview.start(debug=False)



if __name__ == "__main__":
    main()
