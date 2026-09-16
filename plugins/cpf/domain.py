import os
import random
import re
import sys
from pathlib import Path
from typing import Optional, Any


def only_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def is_valid_cpf(cpf: str) -> bool:
    digits = only_digits(cpf)
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    def calc_digit(s, factor):
        total = sum(int(ch) * (factor - i) for i, ch in enumerate(s))
        rem = (total * 10) % 11
        return 0 if rem == 10 else rem

    d1 = calc_digit(digits[:9], 10)
    d2 = calc_digit(digits[:9] + str(d1), 11)
    return digits[-2:] == f"{d1}{d2}"


def format_cpf(digits: str) -> str:
    d = only_digits(digits)
    if len(d) != 11:
        return digits
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def generate_cpf(formatted: bool = True) -> str:
    base = [random.randint(0, 9) for _ in range(9)]
    d1 = sum(v * (10 - i) for i, v in enumerate(base)) * 10 % 11
    d1 = 0 if d1 == 10 else d1
    base.append(d1)
    d2 = sum(v * (11 - i) for i, v in enumerate(base)) * 10 % 11
    d2 = 0 if d2 == 10 else d2
    base.append(d2)
    digits = "".join(str(x) for x in base)
    return format_cpf(digits) if formatted else digits


BADGE_CHECK_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "badge-check.ico"


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows (delega para shared.web_utils)."""
    try:
        from shared.web_utils import set_window_taskbar_icon as _set_icon
    except ImportError:
        from plugins.shared.web_utils import set_window_taskbar_icon as _set_icon
    return _set_icon(icon_path=icon_path or BADGE_CHECK_ICON_PATH, hwnd=hwnd)
