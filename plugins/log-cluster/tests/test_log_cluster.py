import importlib.util
import json
import sys
from pathlib import Path
import pytest

plugin_root = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_root))

def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, plugin_root / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

domain_mod = load_module("log_cluster_domain", "domain.py")
main_mod = load_module("log_cluster_main", "main.py")

cluster_logs = domain_mod.cluster_logs
handle_ipc = main_mod.handle_ipc

def test_1_identical_messages():
    text = """Timeout connecting to database after 3000 ms\nTimeout connecting to database after 5000 ms\nTimeout connecting to database after 3000 ms"""
    res = cluster_logs(text)
    assert res["summary"]["total_events"] == 3
    assert res["summary"]["total_clusters"] == 1
    assert res["summary"]["reduction_percentage"] == 66.67
    c = res["clusters"][0]
    assert "<DURATION>" in c["template"]
    assert c["count"] == 3
    assert len(c["samples"]) == 2

def test_2_uuid_and_numbers():
    text = """User a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d logged in at 2026-08-14 10:00:00 with ID 1054\nUser 11223344-5566-7788-99aa-bbccddeeff00 logged in at 2026-08-14 11:30:00 with ID 2048"""
    res = cluster_logs(text)
    assert res["summary"]["total_clusters"] == 1
    c = res["clusters"][0]
    assert "<UUID>" in c["template"]
    assert "<INT>" in c["template"]
    assert c["count"] == 2

def test_3_distinct_services_grouping():
    text = """[auth-service] [ERROR] Invalid credentials\n[payment-service] [ERROR] Invalid credentials"""
    res1 = cluster_logs(text, {"group_by_service": False})
    assert res1["summary"]["total_clusters"] == 1

    res2 = cluster_logs(text, {"group_by_service": True})
    assert res2["summary"]["total_clusters"] == 2
    services = {c["service"] for c in res2["clusters"]}
    assert "auth-service" in services
    assert "payment-service" in services

def test_4_distinct_levels_grouping():
    text = """2026-08-14 [INFO] User action completed\n2026-08-14 [WARN] User action completed"""
    res1 = cluster_logs(text, {"group_by_level": False})
    assert res1["summary"]["total_clusters"] == 1

    res2 = cluster_logs(text, {"group_by_level": True})
    assert res2["summary"]["total_clusters"] == 2

def test_5_multiline_stack_traces():
    text = """2026-08-14 ERROR NullPointerException\n\tat com.senior.Service.run(Service.java:42)\n\tat com.senior.App.main(App.java:10)\n2026-08-14 ERROR NullPointerException\n\tat com.senior.Service.run(Service.java:42)\n\tat com.senior.App.main(App.java:10)"""
    res = cluster_logs(text)
    assert res["summary"]["total_events"] == 2
    assert res["summary"]["total_clusters"] == 1
    assert res["clusters"][0]["count"] == 2

def test_6_max_samples_limit():
    lines = [f"Error code {i} happened" for i in range(10)]
    res = cluster_logs("\n".join(lines), {"max_samples": 3})
    assert res["summary"]["total_clusters"] == 1
    assert len(res["clusters"][0]["samples"]) == 3

def test_7_line_numbers_tracking():
    text = """Line 1 event\nLine 2 event\nLine 3 event"""
    res = cluster_logs(text)
    assert res["clusters"][0]["line_numbers"] == [1, 2, 3]
    assert res["clusters"][0]["first_seen"]["line"] == 1
    assert res["clusters"][0]["last_seen"]["line"] == 3

def test_8_ipc_protocol_handling():
    payload = {
        "protocol_version": "1.0",
        "request_id": "req_cluster_01",
        "content": "Timeout after 3000 ms\nTimeout after 5000 ms",
        "options": {"max_samples": 2}
    }
    resp = handle_ipc(payload)
    assert resp["status"] == "success"
    assert resp["protocol_version"] == "1.0"
    assert resp["request_id"] == "req_cluster_01"
    assert resp["result"]["summary"]["total_clusters"] == 1
