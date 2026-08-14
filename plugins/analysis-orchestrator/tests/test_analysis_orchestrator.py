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

domain_mod = load_module("analysis_orchestrator_domain", "domain.py")
main_mod = load_module("analysis_orchestrator_main", "main.py")

run_orchestration = domain_mod.run_orchestration
handle_ipc = main_mod.handle_ipc

def test_1_execucao_completa_pipeline(tmp_path):
    # Setup de diretorio de analise completo
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "app.log").write_text(
        "2026-08-14T10:00:00Z [auth-service] [ERROR] NullPointerException password: '123'\n"
        "2026-08-14T10:01:00Z [auth-service] [INFO] Request completed request_id: req-123\n",
        encoding="utf-8"
    )

    meta_file = tmp_path / "incident.json"
    meta_file.write_text(json.dumps({
        "id": "INC-888",
        "service": "auth-service",
        "keywords": ["NullPointerException"]
    }), encoding="utf-8")

    src_dir = tmp_path / "source"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def authenticate():\n    raise NullPointerException()\n", encoding="utf-8")

    res = run_orchestration(str(tmp_path))
    assert "results_directory" in res
    assert res["execution_summary"]["total_files_produced"] > 5

    res_dir = tmp_path / res["results_directory"]
    assert (res_dir / "manifest.json").exists()
    assert (res_dir / "execution-summary.json").exists()
    assert (res_dir / "sanitized" / "sanitized_logs.txt").exists()
    assert (res_dir / "filtered" / "filtered_logs.json").exists()
    assert (res_dir / "optimized" / "log_summary.json").exists()
    assert (res_dir / "clusters" / "clusters.json").exists()
    assert (res_dir / "timelines" / "timeline.json").exists()
    assert (res_dir / "evidence" / "manifest.json").exists()
    assert (res_dir / "source-extracts" / "extracts.json").exists()

def test_2_tolerancia_a_har_e_fontes_ausentes(tmp_path):
    # Diretorio apenas com logs
    (tmp_path / "test.log").write_text("2026-08-14T10:00:00Z [INFO] Single log line", encoding="utf-8")

    res = run_orchestration(str(tmp_path))
    steps_map = {s["step"]: s["status"] for s in res["execution_summary"]["execution_steps"]}
    assert steps_map["log-sanitizer"] == "success"
    assert steps_map["har-optimizer"] == "skipped"
    assert steps_map["source-extractor"] == "skipped"

def test_3_diretorio_inexistente():
    with pytest.raises(ValueError):
        run_orchestration("C:/diretorio_inexistente_99999")

def test_4_nome_customizado_e_sufixo_incremental(tmp_path):
    (tmp_path / "sample.log").write_text("2026-08-14T10:00:00Z [INFO] Line", encoding="utf-8")

    res1 = run_orchestration(str(tmp_path), {"output_directory_name": "meu-resultado"})
    assert res1["results_directory"] == "meu-resultado"

    res2 = run_orchestration(str(tmp_path), {"output_directory_name": "meu-resultado"})
    assert res2["results_directory"] == "meu-resultado-1"

def test_5_protocolo_ipc_v1(tmp_path):
    (tmp_path / "sample.log").write_text("2026-08-14T10:00:00Z [INFO] Line", encoding="utf-8")

    payload = {
        "protocol_version": "1.0",
        "request_id": "req_orch_01",
        "action": "run_analysis",
        "input": {
            "analysis_directory": str(tmp_path)
        }
    }
    resp = handle_ipc(payload)
    assert resp["status"] == "success"
    assert resp["protocol_version"] == "1.0"
    assert resp["request_id"] == "req_orch_01"
    assert "results_directory" in resp["result"]
