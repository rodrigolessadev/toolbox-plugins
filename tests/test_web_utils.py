import sys
from pathlib import Path
import pytest

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

try:
    from shared.web_utils import (
        TOOLBOX_THEME,
        BasePluginApi,
        create_plugin_window,
        open_in_explorer,
        copy_to_clipboard,
        sanitize_file_types,
    )
except ImportError:
    from plugins.shared.web_utils import (
        TOOLBOX_THEME,
        BasePluginApi,
        create_plugin_window,
        open_in_explorer,
        copy_to_clipboard,
        sanitize_file_types,
    )


def test_toolbox_theme_tokens():
    assert TOOLBOX_THEME["bg"] == "#0e1014"
    assert TOOLBOX_THEME["bg_card"] == "#161a21"
    assert TOOLBOX_THEME["accent"] == "#3b82f6"
    assert TOOLBOX_THEME["fg"] == "#e8eaed"


from unittest.mock import MagicMock, patch


def test_base_plugin_api():
    api = BasePluginApi()
    theme = api.get_theme()
    assert theme == TOOLBOX_THEME

    with patch("shared.web_utils.copy_to_clipboard", return_value=True):
        res_copy = api.copy_text("teste de copia")
        assert isinstance(res_copy, dict)
        assert "success" in res_copy
        assert res_copy["success"] is True

    res_none = api.copy_text(None)
    assert res_none["success"] is False

    assert hasattr(api, "select_file")
    assert callable(api.select_file)
    assert hasattr(api, "select_folder")
    assert callable(api.select_folder)
    assert hasattr(api, "open_path")
    assert callable(api.open_path)


def test_copy_to_clipboard_functionality():
    assert copy_to_clipboard(None) is False
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        assert copy_to_clipboard("") is True
        assert copy_to_clipboard("console.log('Hello World!');\nconst x = 42;") is True
        assert copy_to_clipboard("Caractéres acentuados e emojis 🚀✨") is True


def test_create_plugin_window_validations(tmp_path: Path):
    dummy_html = tmp_path / "index.html"
    dummy_html.write_text("<!DOCTYPE html><html><body>Test</body></html>", encoding="utf-8")

    # Testa criação de janela com caminho HTML existente
    win = create_plugin_window(
        title="Plugin Teste",
        entry_html=dummy_html,
        width=700,
        height=600,
    )
    assert win is not None
    assert win.title == "Plugin Teste — Toolbox"

    # Testa erro quando o arquivo HTML não existe
    with pytest.raises(FileNotFoundError):
        create_plugin_window(
            title="Plugin Inexistente",
            entry_html=tmp_path / "nao_existe.html",
        )


def test_theme_css_exists():
    css_path = Path(__file__).parent.parent / "plugins" / "shared" / "ui" / "toolbox-theme.css"
    assert css_path.exists()
    content = css_path.read_text(encoding="utf-8")
    assert "--bg: #0e1014;" in content
    assert "--accent: #3b82f6;" in content


def test_create_plugin_window_with_plugin_dir_and_version(tmp_path: Path):
    """Valida formatação automática do título oficial com versão '{Nome} v{X.Y.Z} — Toolbox'."""
    pdir = tmp_path / "meu-plugin"
    pdir.mkdir(parents=True)
    ui_dir = pdir / "ui"
    ui_dir.mkdir(parents=True)
    assets_dir = ui_dir / "assets"
    assets_dir.mkdir(parents=True)

    dummy_html = ui_dir / "index.html"
    dummy_html.write_text("<!DOCTYPE html><html><body>Test</body></html>", encoding="utf-8")

    manifest = pdir / "plugin.json"
    manifest.write_text('{"id": "meu-plugin", "name": "Meu Plugin", "version": "2.4.1", "icon": "my-icon"}', encoding="utf-8")

    ico_file = assets_dir / "my-icon.ico"
    ico_file.write_bytes(b"\x00\x00\x01\x00\x01\x00")

    # 1. Título gerado com versão extraída automaticamente do plugin.json
    win = create_plugin_window(
        title="Meu Plugin",
        entry_html=dummy_html,
        plugin_dir=pdir,
    )
    assert win is not None
    assert win.title == "Meu Plugin v2.4.1 — Toolbox"

    # 2. Título sem duplicar versão se já estiver no título original
    win2 = create_plugin_window(
        title="Meu Plugin v2.4.1",
        entry_html=dummy_html,
        plugin_dir=pdir,
    )
    assert win2.title == "Meu Plugin v2.4.1 — Toolbox"

    # 3. Versão passada explicitamente sobrescreve ou define versão
    win3 = create_plugin_window(
        title="Meu Plugin Custom",
        entry_html=dummy_html,
        version="3.0.0-beta",
    )
    assert win3.title == "Meu Plugin Custom v3.0.0-beta — Toolbox"


def test_set_window_taskbar_icon_defensive_execution(tmp_path: Path):
    """Valida execução defensiva de set_window_taskbar_icon para arquivos ausentes e plataformas."""
    from shared.web_utils import set_window_taskbar_icon

    # Arquivo None ou inexistente deve retornar False
    assert set_window_taskbar_icon(None) is False
    assert set_window_taskbar_icon(tmp_path / "nao_existe.ico") is False

    # Em ambiente não-Windows deve retornar False seguramente sem exceção
    real_ico = tmp_path / "test.ico"
    real_ico.write_bytes(b"dummy ico")
    if sys.platform != "win32":
        assert set_window_taskbar_icon(real_ico) is False

