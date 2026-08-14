import sys
from pathlib import Path
plugin_root = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_root))
import sys
import json
import importlib.util
from pathlib import Path
import pytest

# Carregamento seguro e isolado dos modulos domain e main do log-optimizer
plugin_root = Path(__file__).parent.parent

def load_plugin_module(name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(name, plugin_root / file_name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

domain_mod = load_plugin_module("log_optimizer_domain", "domain.py")
main_mod = load_plugin_module("log_optimizer_main", "main.py")

optimize_logs = domain_mod.optimize_logs
mask_sensitive_data = domain_mod.mask_sensitive_data
parse_log_content = domain_mod.parse_log_content
handle_ipc = main_mod.handle_ipc


def test_1_empty_log():
    res = optimize_logs("")
    assert res["summary"]["total_lines"] == 0
    assert res["summary"]["total_events"] == 0
    assert res["clusters"] == []
    assert res["timeline"] == []


def test_2_single_line_log():
    log = "2026-08-14 10:00:00 [INFO] [auth-service] User login successful user_id: usr_123"
    res = optimize_logs(log)
    assert res["summary"]["total_events"] == 1
    assert len(res["clusters"]) == 1
    assert res["clusters"][0]["count"] == 1
    assert "<TIMESTAMP>" in res["clusters"][0]["template"]


def test_3_json_lines_ndjson():
    ndjson = """{"timestamp": "2026-08-14T10:00:00Z", "level": "INFO", "service": "payment", "message": "Starting payment", "request_id": "req_1"}
{"timestamp": "2026-08-14T10:00:01Z", "level": "ERROR", "service": "payment", "message": "Payment gateway timeout", "request_id": "req_1"}"""
    res = optimize_logs(ndjson)
    assert res["summary"]["total_events"] == 2
    assert res["summary"]["errors_count"] == 1
    assert len(res["timeline"]) == 1
    assert res["timeline"][0]["level"] == "ERROR"
    assert res["timeline"][0]["request_id"] == "req_1"


def test_4_multiline_stack_trace():
    log = """2026-08-14 10:15:00 [ERROR] Database connection failed
    at com.senior.db.Pool.connect(Pool.java:42)
    at com.senior.app.Main.run(Main.java:10)
2026-08-14 10:15:01 [INFO] Service stopped"""
    events = parse_log_content(log)
    assert len(events) == 2
    assert events[0].is_error is True
    assert events[0].stack_trace is not None
    assert "Pool.java:42" in events[0].stack_trace


def test_5_repeated_events_clustering():
    log = """2026-08-14 10:00:01 [INFO] Processed item ID 1001 in 15ms
2026-08-14 10:00:02 [INFO] Processed item ID 1002 in 22ms
2026-08-14 10:00:03 [INFO] Processed item ID 1003 in 18ms"""
    res = optimize_logs(log)
    assert res["summary"]["total_events"] == 3
    assert len(res["clusters"]) == 1
    assert res["clusters"][0]["count"] == 3
    assert "Processed item ID <NUM> in <DURATION>" in res["clusters"][0]["template"]


def test_6_multiple_timestamp_formats():
    log = """2026-08-14T10:00:00.123Z [INFO] ISO timestamp
14/08/2026 10:00:01 [WARN] BR timestamp
[14/Aug/2026:10:00:02 +0000] [ERROR] Apache timestamp
Aug 14 10:00:03 [DEBUG] Syslog timestamp"""
    events = parse_log_content(log)
    assert len(events) == 4
    assert events[0].timestamp is not None
    assert events[1].timestamp is not None
    assert events[2].timestamp is not None
    assert events[3].timestamp is not None


def test_7_sensitive_data_masking():
    log = """2026-08-14 10:00:00 [INFO] Auth Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisToken
2026-08-14 10:00:01 [INFO] User CPF 123.456.789-00 email test.user@senior.com.br and senha=MySecretPassword123
2026-08-14 10:00:02 [INFO] Paid with card 4111-2222-3333-4444"""
    masked = mask_sensitive_data(log)
    assert "MySecretPassword123" not in masked
    assert "[PASSWORD_MASKED]" in masked
    assert "123.456.789-00" not in masked
    assert "[CPF_MASKED]" in masked
    assert "4111-2222-3333-4444" not in masked
    assert "[CARD_MASKED]" in masked
    assert "test.user@senior.com.br" not in masked
    assert "[EMAIL_MASKED]" in masked


def test_8_non_existent_file_handling():
    res = handle_ipc({"input_file": "C:/non/existent/path/log.txt"})
    assert res["status"] == "error"
    assert res["error"]["code"] == "FILE_NOT_FOUND"


def test_9_invalid_content_handling():
    # Deve processar graciosamente sem estourar excecao nao tratada
    res = optimize_logs("corrupted\x00\x01\x02 binary bytes in log line")
    assert res["summary"]["total_events"] == 1


def test_10_output_char_limit_truncation():
    # Gera log grande repetitivo
    lines = [f"2026-08-14 10:00:{i%60:02d} [ERROR] Error number {i} occurred" for i in range(5000)]
    big_log = "\n".join(lines)
    res = optimize_logs(big_log, {"max_output_chars": 5000})
    assert res.get("truncated") is True
    assert "original_clusters_count" in res


def test_11_request_id_correlation_preservation():
    log = """2026-08-14 10:00:01 [INFO] request_id=req_abc Starting operation
2026-08-14 10:00:02 [INFO] request_id=req_xyz Other unrelated operation
2026-08-14 10:00:03 [ERROR] request_id=req_abc Operation failed with DB error"""
    res = optimize_logs(log, {"correlation_ids": ["req_abc"]})
    # Deve filtrar mantendo req_abc e o erro
    matched_msgs = [cl["samples"][0]["message"] for cl in res["clusters"]]
    assert any("req_abc" in m for m in matched_msgs)
