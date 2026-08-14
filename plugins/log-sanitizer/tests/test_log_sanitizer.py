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


domain_mod = load_module("log_sanitizer_domain", "domain.py")
main_mod = load_module("log_sanitizer_main", "main.py")

sanitize_content = domain_mod.sanitize_content
handle_ipc = main_mod.handle_ipc


def test_1_text_with_credentials_and_tokens():
    text = """2026-08-14 [INFO] Auth Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.superSecretToken
2026-08-14 [DEBUG] Basic dXNlcjpwYXNzd29yZA== and password=SecretPassword123"""
    res = sanitize_content(text)
    san = res["sanitized_content"]
    assert "superSecretToken" not in san
    assert "SecretPassword123" not in san
    assert "[REDACTED]" in san
    assert res["total_substitutions"] >= 2


def test_2_personal_documents_cpf_cnpj():
    text = "Client CPF: 123.456.789-00 and Company CNPJ: 12.345.678/0001-90"
    res = sanitize_content(text)
    san = res["sanitized_content"]
    assert "123.456.789-00" not in san
    assert "12.345.678/0001-90" not in san
    assert res["substitutions_by_type"].get("cpf") == 1
    assert res["substitutions_by_type"].get("cnpj") == 1


def test_3_contacts_email_and_phone():
    text = "Contact me at rodrigo.lessa@senior.com.br or phone (47) 99876-5432"
    res = sanitize_content(text)
    san = res["sanitized_content"]
    assert "rodrigo.lessa@senior.com.br" not in san
    assert "99876-5432" not in san
    assert res["substitutions_by_type"].get("email") == 1


def test_4_credit_cards():
    text = "Payment card: 4111-2222-3333-4444 approved"
    res = sanitize_content(text)
    assert "4111-2222-3333-4444" not in res["sanitized_content"]
    assert res["substitutions_by_type"].get("credit_card") == 1


def test_5_private_keys():
    text = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Y+0...fakeKeyContent...
-----END RSA PRIVATE KEY-----
Some other log line"""
    res = sanitize_content(text)
    assert "fakeKeyContent" not in res["sanitized_content"]
    assert res["substitutions_by_type"].get("private_key") == 1


def test_6_connection_strings_and_urls_with_credentials():
    text = """Database connection: Server=db.prod.internal;Database=HCM;User Id=sa;Password=SuperDbPass123!;
Redis: redis://default:SuperRedisPass@redis.cache.windows.net:6379/0"""
    res = sanitize_content(text)
    san = res["sanitized_content"]
    assert "SuperDbPass123!" not in san
    assert "SuperRedisPass" not in san


def test_7_structured_json_preservation():
    json_input = json.dumps({
        "status": "success",
        "user": {
            "name": "Rodrigo",
            "password": "MySecretPassword",
            "cpf": "123.456.789-00",
            "email": "test@senior.com.br"
        }
    })
    res = sanitize_content(json_input)
    assert res["detected_format"] == "json"
    parsed = json.loads(res["sanitized_content"])
    assert parsed["user"]["name"] == "Rodrigo"
    assert parsed["user"]["password"] == "[REDACTED]"
    assert parsed["user"]["cpf"] == "[REDACTED]"
    assert parsed["user"]["email"] == "[REDACTED]"


def test_8_json_lines_ndjson():
    ndjson = """{"time": "2026-08-14", "msg": "Login", "password": "pass1"}
{"time": "2026-08-14", "msg": "Payment", "card_number": "4111-2222-3333-4444"}"""
    res = sanitize_content(ndjson)
    assert res["detected_format"] == "json_lines"
    lines = res["sanitized_content"].splitlines()
    assert len(lines) == 2
    p1 = json.loads(lines[0])
    p2 = json.loads(lines[1])
    assert p1["password"] == "[REDACTED]"
    assert p2["card_number"] == "[REDACTED]"


def test_9_har_archive():
    har_obj = {
        "log": {
            "version": "1.2",
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://api.senior.com.br/login?token=TopSecretToken",
                        "headers": [{"name": "Authorization", "value": "Bearer eyJhbGciOiJIUzI1NiJ9.abc.def"}],
                        "postData": {"text": "{\"senha\": \"123456\"}"}
                    },
                    "response": {
                        "status": 200,
                        "headers": [{"name": "Set-Cookie", "value": "session=secretSession123"}],
                        "content": {"mimeType": "application/json", "text": "{\"cpf\": \"123.456.789-00\"}"}
                    }
                }
            ]
        }
    }
    res = sanitize_content(json.dumps(har_obj))
    assert res["detected_format"] == "har"
    parsed = json.loads(res["sanitized_content"])
    req = parsed["log"]["entries"][0]["request"]
    resp = parsed["log"]["entries"][0]["response"]
    assert "TopSecretToken" not in req["url"]
    assert req["headers"][0]["value"] == "[REDACTED]"
    assert "123456" not in req["postData"]["text"]
    assert resp["headers"][0]["value"] == "[REDACTED]"
    assert "123.456.789-00" not in resp["content"]["text"]


def test_10_custom_patterns():
    text = "Secret code: PROJ_SECRET_ALPHA_999 happened"
    res = sanitize_content(text, {"custom_patterns": [r"PROJ_SECRET_[A-Z0-9_]+"]})
    assert "PROJ_SECRET_ALPHA_999" not in res["sanitized_content"]
    assert "[REDACTED]" in res["sanitized_content"]


def test_11_dry_run_mode():
    text = "Sensitive password: MySecretPassword"
    res = sanitize_content(text, {"dry_run": True})
    assert res["dry_run"] is True
    assert res["was_modified"] is True


def test_12_prevention_of_false_positives():
    # Versões de pacote, portas, IDs comuns e datas não devem ser destruídos
    text = "Release v1.16.2 on port 8080 at 2026-08-14 10:00:00 ID=1054"
    res = sanitize_content(text)
    assert res["sanitized_content"] == text
    assert res["total_substitutions"] == 0
