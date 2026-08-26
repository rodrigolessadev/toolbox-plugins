import importlib.util
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "gerador-json" / "domain.py"
MAIN_PATH = ROOT / "plugins" / "gerador-json" / "main.py"

orig_domain = sys.modules.get("domain")
try:
    spec_domain = importlib.util.spec_from_file_location("gerador_json_domain", DOMAIN_PATH)
    json_domain = importlib.util.module_from_spec(spec_domain)
    spec_domain.loader.exec_module(json_domain)

    spec_main = importlib.util.spec_from_file_location("gerador_json_main", MAIN_PATH)
    json_main = importlib.util.module_from_spec(spec_main)
    spec_main.loader.exec_module(json_main)
finally:
    if orig_domain is not None:
        sys.modules["domain"] = orig_domain
    else:
        sys.modules.pop("domain", None)


def test_format_json_valid():
    raw = '{"nome":"Rodrigo","idade":30,"ativo":true}'
    res = json_domain.format_json(raw, indent=2)
    assert res["success"] is True
    assert "  \"nome\": \"Rodrigo\"" in res["result"]
    assert res["stats"]["type"] == "Objeto (dict)"


def test_format_json_invalid():
    raw = '{"nome": "incompleto"'
    res = json_domain.format_json(raw)
    assert res["success"] is False
    assert "Erro de sintaxe JSON" in res["message"]


def test_minify_json():
    raw = """
    {
        "a": 1,
        "b": 2
    }
    """
    res = json_domain.minify_json(raw)
    assert res["success"] is True
    assert res["result"] == '{"a":1,"b":2}'


def test_validate_json():
    valid_raw = '{"teste": [1, 2, 3]}'
    res_valid = json_domain.validate_json(valid_raw)
    assert res_valid["success"] is True
    assert res_valid["valid"] is True

    invalid_raw = '{chave: sem_aspas}'
    res_invalid = json_domain.validate_json(invalid_raw)
    assert res_invalid["success"] is True
    assert res_invalid["valid"] is False


def test_generate_mock_json():
    res = json_domain.generate_mock_json("usuario")
    assert res["success"] is True
    data = json.loads(res["result"])
    assert "nome" in data
    assert data["id"] == 1024


def test_file_json_icon_and_taskbar_helper():
    icon_path = json_domain.FILE_JSON_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = json_domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)


def test_gerador_json_api():
    api = json_main.GeradorJsonApi()
    res_fmt = api.format_json('{"a": 1}', indent=4)
    assert res_fmt["success"] is True

    res_mock = api.generate_mock("config")
    assert res_mock["success"] is True

    res_ver = api.get_plugin_version()
    assert res_ver["success"] is True
    assert res_ver["version"] == "1.2.0"
