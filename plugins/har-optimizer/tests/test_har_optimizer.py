import json
import importlib.util
import sys
from pathlib import Path
import pytest

# Carregamento seguro e isolado dos módulos
plugin_root = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_root))

def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, plugin_root / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

domain_mod = load_module("har_domain", "domain.py")
main_mod = load_module("har_main", "main.py")

optimize_har = domain_mod.optimize_har
mask_sensitive_text = domain_mod.mask_sensitive_text
handle_ipc = main_mod.handle_ipc


def create_sample_har(entries: list) -> str:
    return json.dumps({
        "log": {
            "version": "1.2",
            "creator": {"name": "Toolbox", "version": "1.0"},
            "entries": entries
        }
    })


def test_1_empty_har():
    res = optimize_har("")
    assert res["summary"]["total_requests"] == 0
    assert "vazio" in res["warnings"][0]


def test_2_invalid_har():
    with pytest.raises(ValueError):
        optimize_har("{ invalid json")


def test_3_normal_200_request():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 45.2,
            "request": {"method": "GET", "url": "https://api.senior.com.br/users/123", "headers": []},
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/json"}},
            "timings": {"send": 2, "wait": 40, "receive": 3}
        }
    ])
    res = optimize_har(har)
    assert res["summary"]["total_requests"] == 1
    assert res["summary"]["api_requests"] == 1
    assert res["summary"]["failed_requests"] == 0


def test_4_request_500_failure():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 120.0,
            "request": {"method": "POST", "url": "https://api.senior.com.br/orders", "headers": []},
            "response": {"status": 500, "statusText": "Internal Server Error", "content": {"mimeType": "application/json", "text": "{\"error\": \"Database deadlock\"}"}},
            "timings": {"wait": 115}
        }
    ])
    res = optimize_har(har)
    assert res["summary"]["failed_requests"] == 1
    assert len(res["failures"]) == 1
    assert res["failures"][0]["status"] == 500


def test_5_slow_request():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 2500.0,
            "request": {"method": "GET", "url": "https://api.senior.com.br/reports", "headers": []},
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/json"}},
            "timings": {"wait": 2400}
        }
    ])
    res = optimize_har(har, {"slow_threshold_ms": 1000})
    assert res["summary"]["slow_requests"] == 1
    assert len(res["slow_requests"]) == 1
    assert res["slow_requests"][0]["duration_ms"] == 2500.0


def test_6_redirect():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 50.0,
            "request": {"method": "GET", "url": "https://senior.com.br/login", "headers": []},
            "response": {"status": 302, "statusText": "Found", "redirectURL": "https://auth.senior.com.br/login", "content": {"mimeType": "text/html"}},
            "timings": {}
        }
    ])
    res = optimize_har(har)
    assert res["summary"]["redirects"] == 1


def test_7_retry_detection():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 100.0,
            "request": {"method": "POST", "url": "https://api.senior.com.br/webhook", "headers": []},
            "response": {"status": 503, "statusText": "Service Unavailable", "content": {}},
            "timings": {}
        },
        {
            "startedDateTime": "2026-08-14T10:00:01.000Z",
            "time": 80.0,
            "request": {"method": "POST", "url": "https://api.senior.com.br/webhook", "headers": []},
            "response": {"status": 200, "statusText": "OK", "content": {}},
            "timings": {}
        }
    ])
    res = optimize_har(har)
    assert res["summary"]["retries"] == 1


def test_8_static_resource_handling():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 15.0,
            "request": {"method": "GET", "url": "https://senior.com.br/assets/bundle.js", "headers": []},
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/javascript", "text": "console.log(1);"}},
            "timings": {}
        }
    ])
    res = optimize_har(har, {"preserve_static_resources": False})
    assert res["summary"]["static_requests"] == 1


def test_9_base64_payload_handling():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 20.0,
            "request": {"method": "GET", "url": "https://senior.com.br/img/logo.png", "headers": []},
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "image/png", "text": "iVBORw0KGgoAAAANSUhEUgAAAAE...", "encoding": "base64"}},
            "timings": {}
        }
    ])
    res = optimize_har(har)
    assert res["summary"]["static_requests"] == 1


def test_10_authorization_header_masking():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 50.0,
            "request": {
                "method": "GET",
                "url": "https://api.senior.com.br/secret",
                "headers": [{"name": "Authorization", "value": "Bearer eyJhbGciOiJIUzI1NiJ9.superSecretToken"}]
            },
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/json"}},
            "timings": {}
        }
    ])
    res = optimize_har(har, {"mask_sensitive_data": True})
    assert "superSecretToken" not in json.dumps(res)


def test_11_cookie_set_cookie_masking():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 50.0,
            "request": {
                "method": "GET",
                "url": "https://senior.com.br/dashboard",
                "headers": [{"name": "Cookie", "value": "sessionId=secret12345; auth=abc"}]
            },
            "response": {
                "status": 200,
                "statusText": "OK",
                "headers": [{"name": "Set-Cookie", "value": "sessionId=newsecret; Secure; HttpOnly"}],
                "content": {"mimeType": "text/html"}
            },
            "timings": {}
        }
    ])
    res = optimize_har(har, {"mask_sensitive_data": True})
    res_str = json.dumps(res)
    assert "secret12345" not in res_str
    assert "[COOKIE_MASKED]" in res_str


def test_12_sensitive_query_parameters_masking():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 50.0,
            "request": {
                "method": "GET",
                "url": "https://api.senior.com.br/data?token=TopSecretToken123&cpf=12345678900",
                "headers": []
            },
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/json"}},
            "timings": {}
        }
    ])
    res = optimize_har(har, {"mask_sensitive_data": True})
    res_str = json.dumps(res)
    assert "TopSecretToken123" not in res_str
    assert "token=[MASKED]" in res_str


def test_13_sensitive_json_body_masking():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 50.0,
            "request": {
                "method": "POST",
                "url": "https://api.senior.com.br/auth",
                "headers": [],
                "postData": {"text": "{\"username\": \"admin\", \"password\": \"SuperSecretPwd123\", \"cpf\": \"123.456.789-00\"}"}
            },
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/json"}},
            "timings": {}
        }
    ])
    res = optimize_har(har, {"mask_sensitive_data": True})
    res_str = json.dumps(res)
    assert "SuperSecretPwd123" not in res_str
    assert "123.456.789-00" not in res_str
    assert "[MASKED]" in res_str


def test_14_duplicate_requests_clusters():
    har = create_sample_har([
        {
            "startedDateTime": "2026-08-14T10:00:00.000Z",
            "time": 30.0,
            "request": {"method": "GET", "url": "https://api.senior.com.br/items/101", "headers": []},
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/json"}},
            "timings": {}
        },
        {
            "startedDateTime": "2026-08-14T10:00:01.000Z",
            "time": 35.0,
            "request": {"method": "GET", "url": "https://api.senior.com.br/items/102", "headers": []},
            "response": {"status": 200, "statusText": "OK", "content": {"mimeType": "application/json"}},
            "timings": {}
        }
    ])
    res = optimize_har(har)
    assert len(res["clusters"]) == 1
    assert res["clusters"][0]["count"] == 2
    assert "<NUM>" in res["clusters"][0]["path_template"]


def test_15_context_window_around_failure():
    entries = []
    for i in range(10):
        status = 500 if i == 5 else 200
        entries.append({
            "startedDateTime": f"2026-08-14T10:00:0{i}.000Z",
            "time": 20.0,
            "request": {"method": "GET", "url": f"https://api.senior.com.br/step/{i}", "headers": []},
            "response": {"status": status, "statusText": "OK" if status == 200 else "Error", "content": {"mimeType": "application/json"}},
            "timings": {}
        })
    har = create_sample_har(entries)
    res = optimize_har(har, {"context_before": 2, "context_after": 2})
    assert len(res["contexts"]) == 1
    assert res["contexts"][0]["failure_index"] == 5
    assert len(res["contexts"][0]["window"]) == 5  # 2 antes, 1 erro, 2 depois
