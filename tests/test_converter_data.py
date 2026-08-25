import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "converter-data" / "domain.py"

spec = importlib.util.spec_from_file_location("converter_data_domain", DOMAIN_PATH)
converter_domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter_domain)


def test_to_excel_serial():
    serial = converter_domain.to_excel_serial("2026-08-19", "14:00:00")
    assert isinstance(serial, float)
    assert round(serial) > 40000

    assert converter_domain.to_excel_serial("invalid", "") == 0.0


def test_convert_timestamp_epoch_sec():
    res = converter_domain.convert_timestamp("1771500000")
    assert res["success"] is True
    assert res["epoch_sec"] == 1771500000
    assert "iso_utc" in res
    assert "br_local" in res
    assert "excel" in res


def test_convert_timestamp_epoch_ms():
    res = converter_domain.convert_timestamp("1771500000000")
    assert res["success"] is True
    assert res["epoch_sec"] == 1771500000
    assert res["epoch_ms"] == 1771500000000


def test_convert_timestamp_date_strings():
    res_iso = converter_domain.convert_timestamp("2026-08-19 14:00:00")
    assert res_iso["success"] is True
    assert res_iso["epoch_sec"] > 0

    res_br = converter_domain.convert_timestamp("19/08/2026 14:00:00")
    assert res_br["success"] is True
    assert res_br["epoch_sec"] > 0


def test_convert_timestamp_invalid():
    res_empty = converter_domain.convert_timestamp("")
    assert res_empty["success"] is False

    res_inv = converter_domain.convert_timestamp("not-a-valid-date")
    assert res_inv["success"] is False


def test_calendar_sync_icon_and_taskbar_helper():
    icon_path = converter_domain.CALENDAR_SYNC_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = converter_domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)
