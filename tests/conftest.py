"""
Configuração global do Pytest para a suíte de testes de toolbox-plugins.

Define auto-skips para testes plataforma-específicos (ex: windows_only em Linux/macOS)
e padronização de sys.path para os plugins.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

# Adiciona a pasta plugins e a raiz do projeto ao sys.path para importações uniformes
ROOT_DIR = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT_DIR / "plugins"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

# Mock defensivo para pywebview se não estiver instalado no ambiente de teste
try:
    import webview
except ImportError:
    import types
    import re
    from unittest.mock import MagicMock

    mock_webview = MagicMock()
    mock_util = types.ModuleType("webview.util")

    def _parse_file_type(file_type: str):
        pattern = r"^([^;()]+)\s*\(([^()]+)\)$"
        match = re.match(pattern, file_type)
        if not match:
            raise ValueError(f"Invalid file type: {file_type}")
        return match.group(1).strip(), match.group(2).strip()

    mock_util.parse_file_type = _parse_file_type
    mock_webview.util = mock_util

    def _mock_create_window(**kwargs):
        win = MagicMock()
        win.title = kwargs.get("title")
        win.width = kwargs.get("width")
        win.height = kwargs.get("height")
        win.events = MagicMock()
        return win

    mock_webview.create_window.side_effect = _mock_create_window

    sys.modules["webview"] = mock_webview
    sys.modules["webview.util"] = mock_util





def pytest_runtest_setup(item: pytest.Item) -> None:
    """Auto-skip de testes marcados como windows_only quando executados fora do Windows."""
    if "windows_only" in item.keywords and sys.platform != "win32":
        pytest.skip("Teste requer ambiente nativo Windows (DPAPI / Windows Hello / Win32)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Registra markers dinâmicos com o nome do plugin para permitir filtragem via -m <plugin>."""
    registered: set[str] = set()
    for item in items:
        for marker in item.iter_markers("plugin"):
            if marker.args:
                plugin_name = str(marker.args[0])
                clean_name = plugin_name.replace("-", "_")
                for name in (plugin_name, clean_name):
                    if name not in registered:
                        config.addinivalue_line("markers", f"{name}: Marcador para o plugin {name}")
                        registered.add(name)
                    item.add_marker(name)
