import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "cpf" / "domain.py"

spec = importlib.util.spec_from_file_location("cpf_domain", DOMAIN_PATH)
cpf_domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpf_domain)


def test_only_digits():
    assert cpf_domain.only_digits("123.456.789-00") == "12345678900"
    assert cpf_domain.only_digits("abc") == ""
    assert cpf_domain.only_digits(None) == ""


def test_is_valid_cpf():
    # Gerar um CPF válido e validar
    generated = cpf_domain.generate_cpf(formatted=False)
    assert cpf_domain.is_valid_cpf(generated) is True

    # Invalid cases
    assert cpf_domain.is_valid_cpf("111.111.111-11") is False
    assert cpf_domain.is_valid_cpf("00000000000") is False
    assert cpf_domain.is_valid_cpf("123456789") is False
    assert cpf_domain.is_valid_cpf("123.456.789-01") is False


def test_format_cpf():
    assert cpf_domain.format_cpf("12345678900") == "123.456.789-00"
    assert cpf_domain.format_cpf("123") == "123"


def test_generate_cpf():
    gen_fmt = cpf_domain.generate_cpf(formatted=True)
    assert len(gen_fmt) == 14
    assert gen_fmt[3] == "." and gen_fmt[7] == "." and gen_fmt[11] == "-"
    assert cpf_domain.is_valid_cpf(gen_fmt) is True

    gen_raw = cpf_domain.generate_cpf(formatted=False)
    assert len(gen_raw) == 11
    assert gen_raw.isdigit()
    assert cpf_domain.is_valid_cpf(gen_raw) is True


def test_badge_check_icon_and_taskbar_helper():
    icon_path = cpf_domain.BADGE_CHECK_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = cpf_domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)
