import pytest
import sys
from pathlib import Path

shared_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(shared_root))

from shared.theme_utils import THEME, enable_high_dpi

def test_theme_tokens_present():
    required_keys = [
        "bg_base", "bg_surface", "bg_input", "bg_hover",
        "border", "border_focus", "fg_primary", "fg_secondary",
        "fg_muted", "accent", "accent_hover", "success", "warning", "danger"
    ]
    for key in required_keys:
        assert key in THEME
        assert THEME[key].startswith("#")

def test_enable_high_dpi_does_not_crash():
    # Deve rodar sem levantar exceções mesmo em ambientes headless/CI
    enable_high_dpi()

def test_theme_colors_contrast_ratio():
    # Assegura que fg_primary e bg_input nao sejam identicos
    assert THEME["fg_primary"] != THEME["bg_input"]
    assert THEME["fg_primary"] != THEME["bg_base"]
    assert THEME["fg_primary"] != THEME["bg_surface"]
