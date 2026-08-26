import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.web_utils import (
    TOOLBOX_THEME,
    BasePluginApi,
    create_plugin_window,
    open_in_explorer,
    copy_to_clipboard,
)


def test_toolbox_theme_tokens():
    assert TOOLBOX_THEME["bg"] == "#0e1014"
    assert TOOLBOX_THEME["bg_card"] == "#161a21"
    assert TOOLBOX_THEME["accent"] == "#3b82f6"
    assert TOOLBOX_THEME["fg"] == "#e8eaed"


def test_base_plugin_api():
    api = BasePluginApi()
    theme = api.get_theme()
    assert theme == TOOLBOX_THEME

    res_copy = api.copy_text("teste de copia")
    assert isinstance(res_copy, dict)
    assert "success" in res_copy
    assert res_copy["success"] is True

    res_none = api.copy_text(None)
    assert res_none["success"] is False


def test_copy_to_clipboard_functionality():
    assert copy_to_clipboard(None) is False
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
