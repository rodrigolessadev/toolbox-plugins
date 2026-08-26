import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
PLUGIN_DIR = ROOT / "plugins" / "stract-log"
DOMAIN_PATH = PLUGIN_DIR / "domain.py"
MAIN_PATH = PLUGIN_DIR / "main.py"
PLUGIN_JSON_PATH = PLUGIN_DIR / "plugin.json"

spec_dom = importlib.util.spec_from_file_location("test_stract_log_domain", DOMAIN_PATH)
stract_domain = importlib.util.module_from_spec(spec_dom)
spec_dom.loader.exec_module(stract_domain)

spec_main = importlib.util.spec_from_file_location("test_stract_log_main", MAIN_PATH)
stract_main = importlib.util.module_from_spec(spec_main)
spec_main.loader.exec_module(stract_main)


def test_manifest_m3():
    assert PLUGIN_JSON_PATH.exists()
    data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
    assert data.get("theme_version") == "material-3"
    assert data.get("icon") == "file-search"
    assert data.get("version") == "1.2.0"


def test_file_search_icon_and_taskbar_helper():
    icon_path = stract_domain.FILE_SEARCH_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = stract_domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)


def test_filter_logs_by_level():
    sample_log = """
2026-08-26 10:00:00.123 [main] INFO Application initialized
2026-08-26 10:00:01.456 [worker] ERROR Failed to connect database
    at db.connect()
    at app.run()
2026-08-26 10:00:02.789 [worker] WARN Retry attempt 1
2026-08-26 10:00:03.000 [worker] ERROR Timeout during query execution
"""
    res_error = stract_domain.filter_log_text(sample_log, level="ERROR")
    assert res_error["success"] is True
    assert res_error["total_blocks"] == 4
    assert res_error["filtered_blocks"] == 2
    assert "Failed to connect database" in res_error["result_text"]
    assert "Timeout during query execution" in res_error["result_text"]
    assert "Application initialized" not in res_error["result_text"]


def test_filter_logs_by_regex():
    sample_log = """
2026-08-26 10:00:01 INFO User user_123 logged in
2026-08-26 10:00:02 INFO User user_456 logged out
2026-08-26 10:00:03 ERROR User user_123 session expired
"""
    res = stract_domain.filter_log_text(sample_log, regex_term="user_123")
    assert res["success"] is True
    assert res["filtered_blocks"] == 2
    assert "user_456" not in res["result_text"]


def test_filter_logs_deduplication():
    sample_log = """
2026-08-26 10:00:01 ERROR Connection refused
2026-08-26 10:00:01 ERROR Connection refused
2026-08-26 10:00:02 ERROR Out of memory
"""
    res = stract_domain.filter_log_text(sample_log, deduplicate=True)
    assert res["success"] is True
    assert res["total_blocks"] == 3
    assert res["filtered_blocks"] == 2


def test_filter_empty_log():
    res = stract_domain.filter_log_text("")
    assert res["success"] is False
    assert res["total_blocks"] == 0
    assert res["filtered_blocks"] == 0


def test_filter_invalid_regex():
    sample_log = "2026-08-26 10:00:01 INFO Test"
    res = stract_domain.filter_log_text(sample_log, regex_term="[invalid(")
    assert res["success"] is False
    assert "Expressão Regular inválida" in res["message"]


def test_stract_log_api():
    api = stract_main.StractLogApi()
    res = api.filter_logs("2026-08-26 10:00:01 INFO Test", "", "INFO", False)
    assert res["success"] is True
    assert res["filtered_blocks"] == 1

    res_ver = api.get_plugin_version()
    assert res_ver["success"] is True
    assert res_ver["version"] == "1.2.0"

    res_copy = api.copy_text("copiar log")
    assert res_copy["success"] is True


def test_handle_ipc():
    payload = {
        "protocol_version": "1.0",
        "request_id": "req_log_456",
        "content": "2026-08-26 10:00:00 ERROR DB Crash",
        "level": "ERROR"
    }
    res_ipc = stract_main.handle_ipc(payload)
    assert res_ipc["status"] == "success"
    assert res_ipc["request_id"] == "req_log_456"
    assert res_ipc["result"]["filtered_blocks"] == 1
