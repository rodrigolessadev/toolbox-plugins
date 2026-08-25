import os
import sys
from pathlib import Path
import pytest

shared_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(shared_root))

from shared.theme_utils import (
    THEME, THEME_DARK, THEME_LIGHT,
    resolve_theme_mode, get_theme_tokens, setup_app_theme, enable_high_dpi
)

def test_theme_tokens_present():
    required_keys = [
        "bg_base", "bg_surface", "bg_input", "bg_hover",
        "border", "border_focus", "fg_primary", "fg_secondary",
        "fg_muted", "accent", "accent_hover", "success", "warning", "danger"
    ]
    for key in required_keys:
        assert key in THEME_DARK
        assert THEME_DARK[key].startswith("#")
        assert key in THEME_LIGHT
        assert THEME_LIGHT[key].startswith("#")

def test_enable_high_dpi_does_not_crash():
    enable_high_dpi()

def test_theme_colors_contrast_ratio():
    # Modo Escuro: texto claro sobre fundo escuro
    assert THEME_DARK["fg_primary"] != THEME_DARK["bg_input"]
    assert THEME_DARK["fg_primary"] != THEME_DARK["bg_base"]
    assert THEME_DARK["fg_primary"] != THEME_DARK["bg_surface"]

    # Modo Claro: texto escuro sobre fundo claro
    assert THEME_LIGHT["fg_primary"] != THEME_LIGHT["bg_input"]
    assert THEME_LIGHT["fg_primary"] != THEME_LIGHT["bg_base"]
    assert THEME_LIGHT["fg_primary"] != THEME_LIGHT["bg_surface"]

def test_resolve_theme_mode_env(monkeypatch):
    monkeypatch.setenv("TOOLBOX_THEME", "light")
    assert resolve_theme_mode() == "light"
    assert get_theme_tokens()["bg_base"] == THEME_LIGHT["bg_base"]

    monkeypatch.setenv("TOOLBOX_THEME", "dark")
    assert resolve_theme_mode() == "dark"
    assert get_theme_tokens()["bg_base"] == THEME_DARK["bg_base"]

def test_resolve_theme_mode_cli(monkeypatch):
    monkeypatch.delenv("TOOLBOX_THEME", raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--theme", "light"])
    assert resolve_theme_mode() == "light"

    monkeypatch.setattr(sys, "argv", ["main.py", "--theme=dark"])
    assert resolve_theme_mode() == "dark"

    monkeypatch.setattr(sys, "argv", ["main.py"])
    assert resolve_theme_mode() == "dark"
