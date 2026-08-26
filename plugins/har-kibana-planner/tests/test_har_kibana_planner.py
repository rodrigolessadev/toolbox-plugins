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

domain_mod = load_module("har_kibana_planner_domain", "domain.py")
main_mod = load_module("har_kibana_planner_main", "main.py")

plan_har_kibana_queries = domain_mod.plan_har_kibana_queries
handle_ipc = main_mod.handle_ipc

def make_har(entries):
    return json.dumps({"log": {"version": "1.2", "entries": entries}})

def test_1_har_vazio():
    har = make_har([])
    res = plan_har_kibana_queries(har)
    assert res["har_summary"]["total_entries"] == 0
    assert len(res["warnings"]) > 0

def test_2_har_invalido():
    with pytest.raises(ValueError):
        plan_har_kibana_queries("{invalid_json")
def test_3_requisicao_com_trace_id():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 50,
        "request": {"method": "GET", "url": "https://api.senior.com.br/users", "headers": [{"name": "traceparent", "value": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}, {"name": "trace_id", "value": "4bf92f3577b34da6a3ce929d0e0e4736"}]},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    assert len(res["query_plan"]) > 0
    q = res["query_plan"][0]
    assert q["strategy"] == "trace_id"
    assert "4bf92f3577b34da6a3ce929d0e0e4736" in q["identifiers"]

def test_4_requisicao_com_request_id():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 30,
        "request": {"method": "GET", "url": "https://api.senior.com.br/users", "headers": [{"name": "X-Request-Id", "value": "req-98765-abcd"}]},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    q = [p for p in res["query_plan"] if p["strategy"] == "request_id"][0]
    assert "req-98765-abcd" in q["identifiers"]

def test_5_ids_no_corpo_json_request():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 40,
        "request": {"method": "POST", "url": "https://api.senior.com.br/orders", "headers": [], "postData": {"text": json.dumps({"order_id": "ORD-123456"})}},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    assert "ORD-123456" in res["signals"]["identifiers"].get("order_id", [])

def test_6_ids_na_resposta_json():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 40,
        "request": {"method": "GET", "url": "https://api.senior.com.br/orders/1", "headers": []},
        "response": {"status": 200, "headers": [], "content": {"text": json.dumps({"transaction_id": "TXN-998877"})}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    assert "TXN-998877" in res["signals"]["identifiers"].get("transaction_id", [])

def test_7_falha_http():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 100,
        "request": {"method": "GET", "url": "https://api.senior.com.br/checkout", "headers": []},
        "response": {"status": 500, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    assert res["har_summary"]["failed_entries"] == 1
    q_fail = [q for q in res["query_plan"] if q["strategy"] == "failure_endpoint"]
    assert len(q_fail) > 0

def test_8_requisicao_lenta():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 2500,
        "request": {"method": "GET", "url": "https://api.senior.com.br/report", "headers": []},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries), {"slow_threshold_ms": 1000})
    assert res["har_summary"]["slow_entries"] == 1

def test_9_retry():
    entries = [
        {"startedDateTime": "2026-08-14T10:00:00.000Z", "time": 50, "request": {"method": "GET", "url": "https://api.senior.com.br/test", "headers": []}, "response": {"status": 500, "headers": [], "content": {}}},
        {"startedDateTime": "2026-08-14T10:00:01.000Z", "time": 50, "request": {"method": "GET", "url": "https://api.senior.com.br/test", "headers": []}, "response": {"status": 500, "headers": [], "content": {}}}
    ]
    res = plan_har_kibana_queries(make_har(entries))
    assert res["har_summary"]["retry_entries"] >= 1

def test_10_redirect():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 20,
        "request": {"method": "GET", "url": "https://senior.com.br/login", "headers": []},
        "response": {"status": 302, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    assert res["har_summary"]["redirect_entries"] == 1

def test_11_ajuste_de_clock_skew():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 1000,
        "request": {"method": "GET", "url": "https://api.senior.com.br/time", "headers": []},
        "response": {"status": 500, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries), {"clock_skew_ms": 5000, "context_before_ms": 0, "context_after_ms": 0})
    tw = res["requests"][0]["time_window"]
    assert "09:59:55" in tw["from"]
    assert "10:00:06" in tw["to"]

def test_12_janela_antes_e_depois():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 0,
        "request": {"method": "GET", "url": "https://api.senior.com.br/test", "headers": []},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries), {"clock_skew_ms": 0, "context_before_ms": 10000, "context_after_ms": 10000})
    tw = res["requests"][0]["time_window"]
    assert "09:59:50" in tw["from"]
    assert "10:00:10" in tw["to"]

def test_13_ausencia_de_identificadores():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 10,
        "request": {"method": "GET", "url": "https://api.senior.com.br/static", "headers": []},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    assert any("Ausencia de identificadores" in w for w in res["warnings"])

def test_14_mapeamento_de_campos_customizado():
    custom_map = {"trace_id": ["custom.traceId", "trace.id"]}
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 10,
        "request": {"method": "GET", "url": "https://api.senior.com.br/test", "headers": [{"name": "trace_id", "value": "tr-123"}]},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries), {"field_mapping": custom_map})
    assert "custom.traceId" in res["query_plan"][0]["kql"]

def test_15_campos_nao_mapeados():
    custom_map = {}
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 10,
        "request": {"method": "GET", "url": "https://api.senior.com.br/test", "headers": [{"name": "trace_id", "value": "tr-999"}]},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries), {"field_mapping": custom_map})
    assert "trace_id" in res["query_plan"][0]["kql"]

def test_16_deduplicacao_de_consultas():
    entries = [
        {"startedDateTime": "2026-08-14T10:00:00.000Z", "time": 10, "request": {"method": "GET", "url": "https://api.senior.com.br/a", "headers": [{"name": "trace_id", "value": "tr-1"}]}, "response": {"status": 200, "headers": [], "content": {}}},
        {"startedDateTime": "2026-08-14T10:00:01.000Z", "time": 10, "request": {"method": "GET", "url": "https://api.senior.com.br/b", "headers": [{"name": "trace_id", "value": "tr-1"}]}, "response": {"status": 200, "headers": [], "content": {}}}
    ]
    res = plan_har_kibana_queries(make_har(entries))
    trace_queries = [q for q in res["query_plan"] if q["strategy"] == "trace_id"]
    assert len(trace_queries) == 1

def test_17_mascaramento_authorization_e_cookie():
    entries = [{
        "startedDateTime": "2026-08-14T10:00:00.000Z",
        "time": 10,
        "request": {"method": "GET", "url": "https://api.senior.com.br/user", "headers": [{"name": "Authorization", "value": "Bearer mySecretToken123"}, {"name": "Cookie", "value": "session=abc456"}]},
        "response": {"status": 200, "headers": [], "content": {}}
    }]
    res = plan_har_kibana_queries(make_har(entries))
    raw_out = json.dumps(res)
    assert "mySecretToken123" not in raw_out
    assert "session=abc456" not in raw_out

def test_18_limite_maximo_de_consultas():
    entries = [
        {"startedDateTime": "2026-08-14T10:00:00.000Z", "time": 10, "request": {"method": "GET", "url": f"https://api.senior.com.br/err{i}", "headers": []}, "response": {"status": 500, "headers": [], "content": {}}}
        for i in range(20)
    ]
    res = plan_har_kibana_queries(make_har(entries), {"max_queries": 3})
    assert len(res["query_plan"]) <= 3

def test_19_conteudo_truncado():
    entries = [
        {"startedDateTime": "2026-08-14T10:00:00.000Z", "time": 10, "request": {"method": "GET", "url": f"https://api.senior.com.br/{i}", "headers": []}, "response": {"status": 200, "headers": [], "content": {}}}
        for i in range(60)
    ]
    res = plan_har_kibana_queries(make_har(entries))
    assert res["truncated"] is True
    assert len(res["requests"]) <= 50

def test_20_protocolo_toolbox_v1():
    payload = {
        "protocol_version": "1.0",
        "request_id": "req_test_kibana",
        "content": make_har([])
    }
    resp = handle_ipc(payload)
    assert resp["status"] == "success"
    assert resp["protocol_version"] == "1.0"
    assert resp["request_id"] == "req_test_kibana"


def test_21_manifest_theme_and_icon():
    manifest_path = plugin_root / "plugin.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data.get("theme_version") == "material-3"
    assert data.get("icon") == "search-code"
    assert data.get("version") == "1.2.0"


def test_22_search_code_ico_exists():
    ico_path = plugin_root / "ui" / "assets" / "search-code.ico"
    assert ico_path.exists()
    assert ico_path.stat().st_size > 0


def test_23_set_window_taskbar_icon():
    res = domain_mod.set_window_taskbar_icon(hwnd=99999999)
    assert isinstance(res, bool)


def test_24_api_version_and_copy():
    api = main_mod.HarKibanaApi()
    v = api.get_plugin_version()
    assert v["success"] is True
    assert v["version"] == "1.2.0"
    c = api.copy_text("test_kql_query")
    assert c["success"] is True

