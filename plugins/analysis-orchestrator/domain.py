import datetime
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from .analysis import (
        clustering,
        discovery,
        evidence,
        filtering,
        har_processing,
        log_optimization,
        sanitization,
        security,
        source_extraction,
        timeline,
    )
except ImportError:
    from analysis import (
        clustering,
        discovery,
        evidence,
        filtering,
        har_processing,
        log_optimization,
        sanitization,
        security,
        source_extraction,
        timeline,
    )

ORDERED_PIPELINE = [
    "log-sanitizer",
    "incident-filter",
    "log-optimizer",
    "log-cluster",
    "log-timeline",
    "har-optimizer",
    "source-extractor",
    "evidence-package"
]


def get_unique_results_dir(analysis_dir: Path, custom_name: Optional[str] = None) -> Path:
    if custom_name:
        base_name = custom_name
    else:
        now_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base_name = f"analysis-results-{now_str}"

    target = analysis_dir / base_name
    if not target.exists():
        return target

    suffix = 1
    while (analysis_dir / f"{base_name}-{suffix}").exists():
        suffix += 1
    return analysis_dir / f"{base_name}-{suffix}"


def discover_analysis_directory(analysis_dir_str: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Acao 'discover': cataloga arquivos do diretorio sem executar o pipeline."""
    analysis_dir = Path(analysis_dir_str).resolve()
    if not analysis_dir.exists() or not analysis_dir.is_dir():
        raise ValueError(f"Diretorio de analise inexistente ou invalido: {analysis_dir_str}")

    assets = discovery.scan_directory_assets(analysis_dir)

    planned_steps = ["log-sanitizer", "incident-filter", "log-optimizer", "log-cluster", "log-timeline"]
    if assets["har_files"]:
        planned_steps.append("har-optimizer")
    if assets["source_dirs"]:
        planned_steps.append("source-extractor")
    planned_steps.append("evidence-package")

    return {
        "analysis_directory": str(analysis_dir).replace("\\", "/"),
        "files_found": {
            "logs": [str(f.relative_to(analysis_dir)).replace("\\", "/") for f in assets["raw_logs"]],
            "har_files": [str(f.relative_to(analysis_dir)).replace("\\", "/") for f in assets["har_files"]],
            "source_dirs": [str(d.relative_to(analysis_dir)).replace("\\", "/") for d in assets["source_dirs"]],
            "metadata_files": [str(f.relative_to(analysis_dir)).replace("\\", "/") for f in assets["metadata_files"]],
        },
        "incident_metadata": assets["incident_metadata"],
        "planned_pipeline": planned_steps,
        "estimated_output_directory": f"analysis-results-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    }


def run_orchestration(analysis_dir_str: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Acao 'run_analysis': executa pipeline completo ou simula (dry_run)."""
    options = options or {}
    dry_run = bool(options.get("dry_run", False))
    disabled_plugins = set(options.get("disabled_plugins", []))

    analysis_dir = Path(analysis_dir_str).resolve()
    if not analysis_dir.exists() or not analysis_dir.is_dir():
        raise ValueError(f"Diretorio de analise inexistente ou invalido: {analysis_dir_str}")

    if dry_run:
        disc = discover_analysis_directory(analysis_dir_str, options)
        return {
            "dry_run": True,
            "analysis_directory": disc["analysis_directory"],
            "planned_pipeline": [p for p in disc["planned_pipeline"] if p not in disabled_plugins],
            "disabled_plugins": list(disabled_plugins),
            "estimated_output_directory": disc["estimated_output_directory"],
            "files_found": disc["files_found"],
            "warnings": ["Simulacao concluida (dry_run ativo). Nenhum arquivo foi modificado ou gravado."]
        }

    results_dir = get_unique_results_dir(analysis_dir, options.get("output_directory_name"))
    results_dir.mkdir(parents=True, exist_ok=True)

    subdirs = [
        "sanitized", "filtered", "optimized", "clusters",
        "timelines", "source-extracts", "evidence", "reports", "logs"
    ]
    for s in subdirs:
        (results_dir / s).mkdir(parents=True, exist_ok=True)

    execution_steps = []
    warnings = []
    start_time = datetime.datetime.now(datetime.timezone.utc)

    assets = discovery.scan_directory_assets(analysis_dir, exclude_dir=results_dir)
    incident_metadata = assets["incident_metadata"]

    combined_log_text = ""
    for lf in assets["raw_logs"]:
        try:
            combined_log_text += lf.read_text(encoding="utf-8-sig", errors="replace") + "\n"
        except Exception as e:
            warnings.append(f"Erro ao ler log {lf.name}: {e}")

    # Step 1: sanitization (log-sanitizer)
    sanitized_text = combined_log_text
    if "log-sanitizer" in disabled_plugins:
        execution_steps.append({"step": "log-sanitizer", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        try:
            san_res = sanitization.sanitize_content(combined_log_text)
            sanitized_text = san_res.get("sanitized_content") or san_res.get("sanitized_text") or combined_log_text
            (results_dir / "sanitized" / "sanitized_logs.txt").write_text(sanitized_text, encoding="utf-8")
            (results_dir / "sanitized" / "summary.json").write_text(json.dumps(san_res.get("summary", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "log-sanitizer", "status": "success", "files_produced": ["sanitized/sanitized_logs.txt", "sanitized/summary.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-sanitizer", "status": "error", "error": str(e)})
            warnings.append(f"Falha na sanitizacao: {e}")

    # Step 2: filtering (incident-filter)
    filtered_res = {}
    if "incident-filter" in disabled_plugins:
        execution_steps.append({"step": "incident-filter", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        try:
            filter_opts = {
                "time_range": incident_metadata.get("time_range"),
                "services": incident_metadata.get("services", []),
                "levels": incident_metadata.get("levels", []),
                "keywords": incident_metadata.get("keywords", []),
                "correlation_ids": incident_metadata.get("correlation_ids", {}),
                "context_lines": options.get("context_lines", 3),
                "output_format": "compact_text"
            }
            filtered_res = filtering.filter_incident_logs(sanitized_text, filter_opts)
            (results_dir / "filtered" / "filtered_logs.json").write_text(json.dumps(filtered_res, indent=2, ensure_ascii=False), encoding="utf-8")
            if "formatted_output" in filtered_res:
                (results_dir / "filtered" / "filtered_compact.txt").write_text(filtered_res["formatted_output"], encoding="utf-8")
            execution_steps.append({"step": "incident-filter", "status": "success", "files_produced": ["filtered/filtered_logs.json"]})
        except Exception as e:
            execution_steps.append({"step": "incident-filter", "status": "error", "error": str(e)})
            warnings.append(f"Falha no filtro de incidente: {e}")

    # Step 3: log_optimization (log-optimizer)
    log_opt_res = {}
    if "log-optimizer" in disabled_plugins:
        execution_steps.append({"step": "log-optimizer", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        try:
            log_opt_res = log_optimization.optimize_logs(sanitized_text)
            (results_dir / "optimized" / "log_summary.json").write_text(json.dumps(log_opt_res, indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "log-optimizer", "status": "success", "files_produced": ["optimized/log_summary.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-optimizer", "status": "error", "error": str(e)})
            warnings.append(f"Falha no log-optimizer: {e}")

    # Step 4: clustering (log-cluster)
    cluster_res = {}
    if "log-cluster" in disabled_plugins:
        execution_steps.append({"step": "log-cluster", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        try:
            cluster_res = clustering.cluster_logs(sanitized_text)
            (results_dir / "clusters" / "clusters.json").write_text(json.dumps(cluster_res, indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "log-cluster", "status": "success", "files_produced": ["clusters/clusters.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-cluster", "status": "error", "error": str(e)})
            warnings.append(f"Falha no cluster de logs: {e}")

    # Step 5: timeline (log-timeline)
    timeline_res = {}
    if "log-timeline" in disabled_plugins:
        execution_steps.append({"step": "log-timeline", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        try:
            timeline_res = timeline.generate_log_timeline(sanitized_text, {"output_format": "markdown"})
            (results_dir / "timelines" / "timeline.json").write_text(json.dumps(timeline_res, indent=2, ensure_ascii=False), encoding="utf-8")
            if "formatted_output" in timeline_res:
                (results_dir / "timelines" / "timeline.md").write_text(timeline_res["formatted_output"], encoding="utf-8")
            execution_steps.append({"step": "log-timeline", "status": "success", "files_produced": ["timelines/timeline.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-timeline", "status": "error", "error": str(e)})
            warnings.append(f"Falha na timeline: {e}")

    # Step 6: har_processing (har-optimizer)
    har_res = {}
    if "har-optimizer" in disabled_plugins:
        execution_steps.append({"step": "har-optimizer", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        if assets["har_files"]:
            try:
                har_content = assets["har_files"][0].read_text(encoding="utf-8-sig", errors="replace")
                har_res = har_processing.optimize_har(har_content)
                (results_dir / "optimized" / "har_optimized.json").write_text(json.dumps(har_res, indent=2, ensure_ascii=False), encoding="utf-8")
                execution_steps.append({"step": "har-optimizer", "status": "success", "files_produced": ["optimized/har_optimized.json"]})
            except Exception as e:
                execution_steps.append({"step": "har-optimizer", "status": "error", "error": str(e)})
                warnings.append(f"Falha no har-optimizer: {e}")
        else:
            execution_steps.append({"step": "har-optimizer", "status": "skipped", "reason": "Nenhum arquivo HAR fornecido"})

    # Step 7: source_extraction (source-extractor)
    source_res = {}
    if "source-extractor" in disabled_plugins:
        execution_steps.append({"step": "source-extractor", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        if assets["source_dirs"]:
            try:
                terms = incident_metadata.get("keywords", []) or ["Exception", "Error", "500"]
                source_res = source_extraction.extract_sources({"project_path": str(assets["source_dirs"][0]), "terms": terms})
                (results_dir / "source-extracts" / "extracts.json").write_text(json.dumps(source_res, indent=2, ensure_ascii=False), encoding="utf-8")
                execution_steps.append({"step": "source-extractor", "status": "success", "files_produced": ["source-extracts/extracts.json"]})
            except Exception as e:
                execution_steps.append({"step": "source-extractor", "status": "error", "error": str(e)})
                warnings.append(f"Falha no source-extractor: {e}")
        else:
            execution_steps.append({"step": "source-extractor", "status": "skipped", "reason": "Nenhum diretorio de codigo encontrado"})

    # Step 8: evidence (evidence-package)
    if "evidence-package" in disabled_plugins:
        execution_steps.append({"step": "evidence-package", "status": "skipped", "reason": "desabilitado por configuracao"})
    else:
        try:
            ev_payload = {
                "incident_info": incident_metadata,
                "summary_logs": log_opt_res.get("summary", {}),
                "clusters": cluster_res.get("clusters", []),
                "timeline": timeline_res.get("timeline", []),
                "har": har_res.get("optimized_har") if har_res else None,
                "time_range": incident_metadata.get("time_range")
            }
            evidence_res = evidence.build_evidence_package(ev_payload)
            (results_dir / "evidence" / "manifest.json").write_text(json.dumps(evidence_res.get("manifest", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "incident-summary.json").write_text(json.dumps(evidence_res.get("incident_summary", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "evidence.json").write_text(json.dumps(evidence_res.get("evidence", []), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "timeline.json").write_text(json.dumps(evidence_res.get("timeline", []), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "references.json").write_text(json.dumps(evidence_res.get("references", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "evidence-package", "status": "success", "files_produced": ["evidence/evidence.json", "evidence/incident-summary.json"]})
        except Exception as e:
            execution_steps.append({"step": "evidence-package", "status": "error", "error": str(e)})
            warnings.append(f"Falha no evidence-package: {e}")

    end_time = datetime.datetime.now(datetime.timezone.utc)
    rel_results_dir = str(results_dir.relative_to(analysis_dir)).replace("\\", "/")

    all_produced_files = []
    for f in results_dir.rglob("*"):
        if f.is_file():
            all_produced_files.append(str(f.relative_to(results_dir)).replace("\\", "/"))

    exec_summary = {
        "analysis_directory": str(analysis_dir).replace("\\", "/"),
        "results_directory": rel_results_dir,
        "started_at": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished_at": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "execution_steps": execution_steps,
        "total_files_produced": len(all_produced_files),
        "warnings": warnings
    }

    manifest = {
        "orchestrator_version": "1.0.0",
        "generated_at": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "analysis_directory": str(analysis_dir).replace("\\", "/"),
        "results_directory": rel_results_dir,
        "files": sorted(all_produced_files)
    }

    (results_dir / "execution-summary.json").write_text(json.dumps(exec_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (results_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    rep_lines = [
        f"# 📋 Relatório de Execução da Análise — {rel_results_dir}",
        "",
        f"- **Diretório de Análise**: `{analysis_dir}`",
        f"- **Diretório de Resultados**: `{rel_results_dir}`",
        f"- **Início**: `{start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}`",
        f"- **Fim**: `{end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}`",
        "",
        "## Etapas Executadas",
        "| Etapa | Status | Detalhes |",
        "|---|---|---|"
    ]
    for st in execution_steps:
        detail = ", ".join(st.get("files_produced", [])) if st["status"] == "success" else st.get("error") or st.get("reason", "-")
        rep_lines.append(f"| `{st['step']}` | **{st['status']}** | {detail} |")

    (results_dir / "reports" / "summary.md").write_text("\n".join(rep_lines), encoding="utf-8")

    return {
        "results_directory": rel_results_dir,
        "absolute_results_path": str(results_dir).replace("\\", "/"),
        "execution_summary": exec_summary,
        "manifest": manifest,
        "warnings": warnings
    }


def run_single_plugin(analysis_dir_str: str, plugin_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Acao 'run_plugin': executa uma unica etapa isolada sobre o diretorio de analise."""
    options = options or {}
    analysis_dir = Path(analysis_dir_str).resolve()
    if not analysis_dir.exists() or not analysis_dir.is_dir():
        raise ValueError(f"Diretorio de analise inexistente: {analysis_dir_str}")

    assets = discovery.scan_directory_assets(analysis_dir)

    if plugin_name == "log-sanitizer":
        log_text = "\n".join(f.read_text(encoding="utf-8-sig", errors="replace") for f in assets["raw_logs"])
        return sanitization.sanitize_content(log_text, options)
    elif plugin_name == "incident-filter":
        log_text = "\n".join(f.read_text(encoding="utf-8-sig", errors="replace") for f in assets["raw_logs"])
        return filtering.filter_incident_logs(log_text, options)
    elif plugin_name == "log-optimizer":
        log_text = "\n".join(f.read_text(encoding="utf-8-sig", errors="replace") for f in assets["raw_logs"])
        return log_optimization.optimize_logs(log_text)
    elif plugin_name == "log-cluster":
        log_text = "\n".join(f.read_text(encoding="utf-8-sig", errors="replace") for f in assets["raw_logs"])
        return clustering.cluster_logs(log_text, options)
    elif plugin_name == "log-timeline":
        log_text = "\n".join(f.read_text(encoding="utf-8-sig", errors="replace") for f in assets["raw_logs"])
        return timeline.generate_log_timeline(log_text, options)
    elif plugin_name == "har-optimizer":
        if not assets["har_files"]:
            raise ValueError("Nenhum arquivo HAR encontrado para executar har-optimizer.")
        har_str = assets["har_files"][0].read_text(encoding="utf-8-sig", errors="replace")
        return har_processing.optimize_har(har_str, options)
    elif plugin_name == "source-extractor":
        src_path = str(assets["source_dirs"][0]) if assets["source_dirs"] else str(analysis_dir)
        opts = dict(options)
        opts["project_path"] = src_path
        return source_extraction.extract_sources(opts)
    elif plugin_name == "evidence-package":
        return evidence.build_evidence_package(options)
    else:
        raise ValueError(f"Plugin '{plugin_name}' desconhecido ou nao suportado.")


def validate_results_directory(results_dir_str: str) -> Dict[str, Any]:
    """Acao 'validate_results': valida integridade dos artefatos em uma pasta de resultados."""
    target_dir = Path(results_dir_str).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        sub_res = list(target_dir.glob("analysis-results-*"))
        if sub_res:
            target_dir = sub_res[0]
        else:
            raise ValueError(f"Diretorio de resultados inexistente: {results_dir_str}")

    manifest_file = target_dir / "manifest.json"
    summary_file = target_dir / "execution-summary.json"

    is_valid = True
    missing_files = []

    if not manifest_file.exists():
        is_valid = False
        missing_files.append("manifest.json")
    if not summary_file.exists():
        is_valid = False
        missing_files.append("execution-summary.json")

    manifest_data = {}
    if manifest_file.exists():
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            for f_rel in manifest_data.get("files", []):
                if not (target_dir / f_rel).exists():
                    is_valid = False
                    missing_files.append(f_rel)
        except Exception:
            is_valid = False

    return {
        "results_directory": str(target_dir).replace("\\", "/"),
        "is_valid": is_valid,
        "missing_files": missing_files,
        "manifest_version": manifest_data.get("orchestrator_version", "unknown")
    }


def resume_orchestration(analysis_or_results_dir_str: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Acao 'resume': retoma execucao a partir de resultados anteriores."""
    target_dir = Path(analysis_or_results_dir_str).resolve()
    if not target_dir.exists():
        raise ValueError(f"Diretorio inexistente para retoma: {analysis_or_results_dir_str}")

    val = validate_results_directory(str(target_dir))
    if val["is_valid"]:
        return {
            "status": "already_completed",
            "message": "Diretorio de resultados já validado e completo.",
            "results_directory": val["results_directory"]
        }

    parent_analysis_dir = target_dir.parent if target_dir.name.startswith("analysis-results-") else target_dir
    return run_orchestration(str(parent_analysis_dir), options)


WORKFLOW_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "workflow.ico"


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone de workflow."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else WORKFLOW_ICON_PATH
    if not target_icon.exists():
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        h_icon_big = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            32,
            32,
            LR_LOADFROMFILE,
        )
        h_icon_small = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            16,
            16,
            LR_LOADFROMFILE,
        )

        if not h_icon_big and not h_icon_small:
            return False

        if hwnd:
            target_hwnds = [hwnd]
        else:
            current_pid = os.getpid()
            target_hwnds = []

            def _enum_windows_cb(handle: int, _: Any) -> bool:
                lpdw_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(handle, ctypes.byref(lpdw_pid))
                if lpdw_pid.value == current_pid:
                    if user32.IsWindowVisible(handle):
                        target_hwnds.append(handle)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(_enum_windows_cb), 0)

        success = False
        for target in target_hwnds:
            if h_icon_big:
                user32.SendMessageW(target, WM_SETICON, ICON_BIG, h_icon_big)
            if h_icon_small:
                user32.SendMessageW(target, WM_SETICON, ICON_SMALL, h_icon_small)
            success = True
        return success
    except Exception:
        pass
    return False

