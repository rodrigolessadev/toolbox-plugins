import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
PLUGIN_DIR = ROOT / "plugins" / "stract-json"
DOMAIN_PATH = PLUGIN_DIR / "domain.py"
MAIN_PATH = PLUGIN_DIR / "main.py"
PLUGIN_JSON_PATH = PLUGIN_DIR / "plugin.json"

spec_dom = importlib.util.spec_from_file_location("test_stract_json_domain", DOMAIN_PATH)
stract_domain = importlib.util.module_from_spec(spec_dom)
spec_dom.loader.exec_module(stract_domain)

spec_main = importlib.util.spec_from_file_location("test_stract_json_main", MAIN_PATH)
stract_main = importlib.util.module_from_spec(spec_main)
spec_main.loader.exec_module(stract_main)


def test_manifest_m3():
    assert PLUGIN_JSON_PATH.exists()
    data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
    assert data.get("theme_version") == "material-3"
    assert data.get("icon") == "scan-search"
    assert data.get("version") == "1.2.0"


def test_scan_search_icon_and_taskbar_helper():
    icon_path = stract_domain.SCAN_SEARCH_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = stract_domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)


def test_extract_json_from_raw_text():
    log_line = '2026-08-26 10:00:00 INFO [Service] Response: {"user_id": 12345, "status": "active", "roles": ["admin", "editor"]}'
    res = stract_domain.extract_json_from_text(log_line)
    assert res["success"] is True
    assert res["count"] == 1
    assert len(res["items"]) == 1
    parsed = json.loads(res["items"][0])
    assert parsed["user_id"] == 12345


def test_extract_specific_field():
    log_lines = """
    Log 1: {"order": {"id": "ORD-1", "total": 100}}
    Log 2: {"order": {"id": "ORD-2", "total": 250}}
    """
    res = stract_domain.extract_json_from_text(log_lines, target_field="id")
    assert res["success"] is True
    assert res["count"] == 2
    assert "ORD-1" in res["items"]
    assert "ORD-2" in res["items"]


def test_extract_empty_or_invalid():
    res_empty = stract_domain.extract_json_from_text("")
    assert res_empty["success"] is False
    assert res_empty["count"] == 0

    res_invalid = stract_domain.extract_json_from_text("isto é apenas texto puro sem chaves")
    assert res_invalid["success"] is False
    assert res_invalid["count"] == 0


def test_stract_json_api():
    api = stract_main.StractJsonApi()
    res = api.extract_json('{"key": "value"}')
    assert res["success"] is True

    res_ver = api.get_plugin_version()
    assert res_ver["success"] is True
    assert res_ver["version"] == "1.2.0"

    res_copy = api.copy_text("teste de copia")
    assert res_copy["success"] is True


def test_handle_ipc():
    payload = {
        "protocol_version": "1.0",
        "request_id": "req_123",
        "content": '{"service": "auth", "healthy": true}'
    }
    ipc_res = stract_main.handle_ipc(payload)
    assert ipc_res["status"] == "success"
    assert ipc_res["request_id"] == "req_123"
    assert ipc_res["result"]["count"] == 1
