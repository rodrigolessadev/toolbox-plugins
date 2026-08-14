import importlib.util
import json
import os
import sys
import tempfile
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

domain_mod = load_module("source_extractor_domain", "domain.py")
main_mod = load_module("source_extractor_main", "main.py")

extract_sources = domain_mod.extract_sources
handle_ipc = main_mod.handle_ipc

def test_1_busca_literal_multiplos_arquivos(tmp_path):
    f1 = tmp_path / "service.py"
    f1.write_text("def authenticate():\n    print('token verification')\n", encoding="utf-8")

    f2 = tmp_path / "controller.ts"
    f2.write_text("export class AuthController {\n    login() { authenticate(); }\n}\n", encoding="utf-8")

    res = extract_sources({"project_path": str(tmp_path), "terms": ["authenticate"]})
    assert res["summary"]["total_matches"] == 2
    assert len(res["results"]) == 2
    files = {r["file"] for r in res["results"]}
    assert "service.py" in files
    assert "controller.ts" in files

def test_2_regex_invalida_fallback(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("def process_data():\n    return [1, 2, 3]\n", encoding="utf-8")

    # Regex invalida (parenteses desbalanceados)
    res = extract_sources({"project_path": str(tmp_path), "terms": ["def (process_data"], "search_type": "regex"})
    assert any("Regex invalida" in w for w in res["warnings"])
    assert res["summary"]["total_matches"] == 0

def test_3_deteccao_arquivo_binario(tmp_path):
    f_bin = tmp_path / "sample.bin"
    f_bin.write_bytes(b"\x00\x01\x02\x03\x00\xff")

    f_txt = tmp_path / "valid.py"
    f_txt.write_text("target_token = 1234\n", encoding="utf-8")

    res = extract_sources({"project_path": str(tmp_path), "terms": ["target_token"]})
    assert res["summary"]["total_matches"] == 1
    assert res["results"][0]["file"] == "valid.py"

def test_4_diretorio_inexistente():
    res = extract_sources({"project_path": "C:/non_existent_dir_12345", "terms": ["test"]})
    assert res["summary"]["total_matches"] == 0
    assert any("Diretorio nao encontrado" in w for w in res["warnings"])

def test_5_limite_max_results(tmp_path):
    f = tmp_path / "many.py"
    lines = [f"item_{i} = {i}" for i in range(30)]
    f.write_text("\n".join(lines), encoding="utf-8")

    res = extract_sources({"project_path": str(tmp_path), "terms": ["item_"], "max_results": 5})
    assert res["summary"]["is_truncated"] is True
    assert len(res["results"]) == 5

def test_6_exclusao_diretorios_padrao(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config.txt").write_text("secret_keyword = 1", encoding="utf-8")

    node_dir = tmp_path / "node_modules"
    node_dir.mkdir()
    (node_dir / "dep.js").write_text("secret_keyword = 2", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("secret_keyword = 3", encoding="utf-8")

    res = extract_sources({"project_path": str(tmp_path), "terms": ["secret_keyword"]})
    assert res["summary"]["total_matches"] == 1
    assert "src/app.py" in res["results"][0]["file"]

def test_7_mascaramento_de_secrets(tmp_path):
    f = tmp_path / "config.py"
    f.write_text("password: 'supersecret'\ntoken = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig'\n", encoding="utf-8")

    res = extract_sources({"project_path": str(tmp_path), "terms": ["password"]})
    assert "supersecret" not in res["results"][0]["snippet"]
    assert "[REDACTED]" in res["results"][0]["snippet"]

def test_8_busca_por_funcao_e_classe(tmp_path):
    f = tmp_path / "models.py"
    f.write_text("class OrderModel:\n    pass\n\ndef process_order():\n    pass\n", encoding="utf-8")

    res_c = extract_sources({"project_path": str(tmp_path), "terms": ["OrderModel"], "search_type": "class"})
    assert res_c["summary"]["total_matches"] == 1
    assert res_c["results"][0]["match_type"] == "class"

    res_f = extract_sources({"project_path": str(tmp_path), "terms": ["process_order"], "search_type": "function"})
    assert res_f["summary"]["total_matches"] == 1
    assert res_f["results"][0]["match_type"] == "function"

def test_9_protocolo_ipc_v1(tmp_path):
    f = tmp_path / "hello.py"
    f.write_text("print('Hello World')\n", encoding="utf-8")

    payload = {
        "protocol_version": "1.0",
        "request_id": "req_src_01",
        "project_path": str(tmp_path),
        "terms": ["Hello"]
    }
    resp = handle_ipc(payload)
    assert resp["status"] == "success"
    assert resp["protocol_version"] == "1.0"
    assert resp["request_id"] == "req_src_01"
    assert resp["result"]["summary"]["total_matches"] == 1
