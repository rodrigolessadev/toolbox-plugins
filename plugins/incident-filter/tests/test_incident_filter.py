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

domain_mod = load_module("incident_filter_domain", "domain.py")
main_mod = load_module("incident_filter_main", "main.py")

filter_incident_logs = domain_mod.filter_incident_logs
handle_ipc = main_mod.handle_ipc

def test_1_filtro_por_time_range():
    text = """2026-08-14T09:00:00Z [ERROR] Before\n2026-08-14T10:10:00Z [ERROR] Inside\n2026-08-14T11:00:00Z [ERROR] After"""
    opts = {"time_range": {"from": "2026-08-14T10:00:00Z", "to": "2026-08-14T10:30:00Z"}}
    res = filter_incident_logs(text, opts)
    assert res["summary"]["matched_events_count"] == 1
    assert "Inside" in res["events"][0]["message"]

def test_2_filtro_por_niveis():
    text = """2026-08-14T10:00:00Z [INFO] Normal\n2026-08-14T10:01:00Z [WARN] Warning alert\n2026-08-14T10:02:00Z [ERROR] Critical error"""
    res = filter_incident_logs(text, {"levels": ["ERROR", "WARN"]})
    assert res["summary"]["matched_events_count"] == 2
    levels_matched = {e["level"] for e in res["events"]}
    assert "INFO" not in levels_matched

def test_3_filtro_por_servico():
    text = """2026-08-14T10:00:00Z [auth-service] [ERROR] Invalid login\n2026-08-14T10:01:00Z [payment-api] [ERROR] Gateway down"""
    res = filter_incident_logs(text, {"services": ["payment-api"]})
    assert res["summary"]["matched_events_count"] == 1
    assert "payment-api" in res["events"][0]["message"]

def test_4_filtro_por_palavras_chave():
    text = """2026-08-14T10:00:00Z [ERROR] NullPointerException\n2026-08-14T10:01:00Z [ERROR] Database timeout connecting to pool"""
    res = filter_incident_logs(text, {"keywords": ["timeout"]})
    assert res["summary"]["matched_events_count"] == 1
    assert "Database timeout" in res["events"][0]["message"]

def test_5_filtro_por_correlation_ids_bypass_level():
    text = """2026-08-14T10:00:00Z [INFO] Processing request_id: req-abc-123\n2026-08-14T10:01:00Z [ERROR] Unrelated error\n2026-08-14T10:02:00Z [DEBUG] Processing order_id: ORD-9988"""
    opts = {
        "levels": ["ERROR"],
        "correlation_ids": {"request_id": ["req-abc-123"]},
        "include_correlated_regardless_of_level": True
    }
    res = filter_incident_logs(text, opts)
    # Deve trazer o ERROR (passou no filtro de level) e o INFO (passou pelo bypass do request_id)
    assert res["summary"]["matched_events_count"] == 2
    msgs = [e["message"] for e in res["events"]]
    assert any("req-abc-123" in m for m in msgs)
    assert any("Unrelated error" in m for m in msgs)

def test_6_preservacao_de_contexto_antes_e_depois():
    text = """2026-08-14T10:00:00Z [INFO] Line 1\n2026-08-14T10:01:00Z [INFO] Line 2\n2026-08-14T10:02:00Z [ERROR] Line 3 target\n2026-08-14T10:03:00Z [INFO] Line 4\n2026-08-14T10:04:00Z [INFO] Line 5"""
    res = filter_incident_logs(text, {"levels": ["ERROR"], "context_lines": 1})
    assert res["summary"]["matched_events_count"] == 1
    assert len(res["events"]) == 3  # Line 2 (ctx), Line 3 (match), Line 4 (ctx)
    assert res["events"][0]["is_context"] is True
    assert res["events"][1]["is_match"] is True
    assert res["events"][2]["is_context"] is True

def test_7_mascaramento_dados_sensiveis():
    text = """2026-08-14T10:00:00Z [ERROR] Auth failed with Bearer secretToken123456"""
    res = filter_incident_logs(text, {"sanitize_sensitive_data": True})
    assert "secretToken123456" not in res["events"][0]["message"]
    assert "Bearer [REDACTED]" in res["events"][0]["message"]

def test_8_limite_max_events():
    lines = [f"2026-08-14T10:{i:02d}:00Z [ERROR] Error {i}" for i in range(20)]
    res = filter_incident_logs("\n".join(lines), {"max_events": 5})
    assert res["summary"]["is_truncated"] is True
    assert len(res["events"]) == 5

def test_9_formatacao_compact_text():
    text = """2026-08-14T10:00:00Z [auth-service] [ERROR] Invalid password"""
    res = filter_incident_logs(text, {"output_format": "compact_text"})
    assert "formatted_output" in res
    assert "[MATCH]" in res["formatted_output"]
    assert "[auth-service]" in res["formatted_output"]

def test_10_protocolo_ipc_v1():
    payload = {
        "protocol_version": "1.0",
        "request_id": "req_filter_01",
        "content": "2026-08-14T10:00:00Z [ERROR] Boom",
        "levels": ["ERROR"]
    }
    resp = handle_ipc(payload)
    assert resp["status"] == "success"
    assert resp["protocol_version"] == "1.0"
    assert resp["request_id"] == "req_filter_01"
    assert resp["result"]["summary"]["matched_events_count"] == 1
