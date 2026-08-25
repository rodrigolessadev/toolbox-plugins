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

discover_analysis_directory = domain_mod.discover_analysis_directory
run_orchestration = domain_mod.run_orchestration
run_single_plugin = domain_mod.run_single_plugin
validate_results_directory = domain_mod.validate_results_directory
resume_orchestration = domain_mod.resume_orchestration
handle_ipc = main_mod.handle_ipc

def test_1_acao_discover(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "app.log").write_text("2026-08-14T10:00:00Z [INFO] Hello\n", encoding="utf-8")

    res = discover_analysis_directory(str(tmp_path))
    assert len(res["files_found"]["logs"]) == 1
    assert "logs/app.log" in res["files_found"]["logs"][0]
    assert "log-sanitizer" in res["planned_pipeline"]

def test_2_acao_dry_run(tmp_path):
    (tmp_path / "sample.log").write_text("2026-08-14T10:00:00Z [INFO] Line\n", encoding="utf-8")

    res = run_orchestration(str(tmp_path), {"dry_run": True})
    assert res["dry_run"] is True
    # Nao deve criar pasta de resultados no dry_run
    created_dirs = list(tmp_path.glob("analysis-results-*"))
    assert len(created_dirs) == 0

def test_3_execucao_completa_e_validacao(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "app.log").write_text("2026-08-14T10:00:00Z [ERROR] Boom\n", encoding="utf-8")

    src_dir = tmp_path / "source"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('test')\n", encoding="utf-8")

    res = run_orchestration(str(tmp_path))
    assert res["execution_summary"]["total_files_produced"] > 0

    val = validate_results_directory(str(tmp_path / res["results_directory"]))
    assert val["is_valid"] is True
    assert len(val["missing_files"]) == 0

def test_4_acao_run_plugin_isolado(tmp_path):
    (tmp_path / "app.log").write_text("2026-08-14T10:00:00Z [ERROR] password: 'secret123'\n", encoding="utf-8")

    res = run_single_plugin(str(tmp_path), "log-sanitizer")
    assert "sanitized_content" in res or "sanitized_text" in res

def test_5_desabilitar_plugins(tmp_path):
    (tmp_path / "app.log").write_text("2026-08-14T10:00:00Z [INFO] Ok\n", encoding="utf-8")

    res = run_orchestration(str(tmp_path), {"disabled_plugins": ["log-cluster", "log-timeline"]})
    steps_map = {s["step"]: s["status"] for s in res["execution_summary"]["execution_steps"]}
    assert steps_map["log-cluster"] == "skipped"
    assert steps_map["log-timeline"] == "skipped"

def test_6_diretorio_inexistente():
    with pytest.raises(ValueError):
        discover_analysis_directory("C:/diretorio_falso_123456")

def test_7_protocolo_ipc_v1_todas_acoes(tmp_path):
    (tmp_path / "app.log").write_text("2026-08-14T10:00:00Z [INFO] Line\n", encoding="utf-8")

    # 1. Discover
    resp1 = handle_ipc({"action": "discover", "input": {"analysis_directory": str(tmp_path)}})
    assert resp1["status"] == "success"
    assert "files_found" in resp1["result"]

    # 2. Run analysis
    resp2 = handle_ipc({"action": "run_analysis", "input": {"analysis_directory": str(tmp_path)}})
    assert resp2["status"] == "success"
    res_dir_rel = resp2["result"]["results_directory"]

    # 3. Validate results
    resp3 = handle_ipc({"action": "validate_results", "input": {"results_directory": str(tmp_path / res_dir_rel)}})
    assert resp3["status"] == "success"
    assert resp3["result"]["is_valid"] is True


def test_8_workflow_icon_and_taskbar_helper():
    icon_path = domain_mod.WORKFLOW_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = domain_mod.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)

