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
        status = domain.tunnel_manager.get_status(config.get("local_port", 5432))
        return {
            "config": config,
            "status": status,
            "logs": domain.tunnel_manager.get_logs(),
        }

    def sso_login(self, data: dict) -> dict:
        profile = data.get("profile", "default")
        auto_open = data.get("auto_open_browser", True)
        return domain.tunnel_manager.run_sso_login(profile, auto_open)

    def connect_tunnel(self, data: dict) -> dict:
        profile = data.get("profile", "default")
        local_port = data.get("local_port", 5432)
        remote_port = data.get("remote_port", local_port)
        target = data.get("target", "")
        return domain.tunnel_manager.start_tunnel(
            profile=profile,
            local_port=int(local_port),
            remote_port=int(remote_port),
            target=target,
        )

    def disconnect_tunnel(self) -> dict:
        return domain.tunnel_manager.stop_tunnel()

    def check_status(self, data: dict) -> dict:
        port = int(data.get("local_port", 5432)) if data.get("local_port") else 5432
        return domain.tunnel_manager.get_status(port)

    def get_logs(self) -> list:
        return domain.tunnel_manager.get_logs()

    def clear_logs(self) -> dict:
        domain.tunnel_manager.clear_logs()
        return {"success": True}


def main() -> None:
    api = LogonAwsApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    create_plugin_window(
        title="Logon AWS & Port Forwarding",
        entry_html=ui_index,
        js_api=api,
        width=740,
        height=720,
        min_size=(680, 600),
    )
    if webview:
        webview.start(debug=False)


if __name__ == "__main__":
    main()
