import datetime
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PLUGINS_ROOT = Path(__file__).parent.parent


def _import_plugin_domain(plugin_name: str, domain_file: str = "domain.py"):
    path = PLUGINS_ROOT / plugin_name / domain_file
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"{plugin_name.replace('-', '_')}_domain_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def run_orchestration(analysis_dir_str: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    analysis_dir = Path(analysis_dir_str).resolve()
    if not analysis_dir.exists() or not analysis_dir.is_dir():
        raise ValueError(f"Diretorio de analise inexistente ou invalido: {analysis_dir_str}")

    results_dir = get_unique_results_dir(analysis_dir, options.get("output_directory_name"))
    results_dir.mkdir(parents=True, exist_ok=True)

    # Subdiretorios padrao
    subdirs = [
        "sanitized", "filtered", "optimized", "clusters",
        "timelines", "source-extracts", "evidence", "reports", "logs"
    ]
    for s in subdirs:
        (results_dir / s).mkdir(parents=True, exist_ok=True)

    execution_steps = []
    warnings = []
    start_time = datetime.datetime.now(datetime.timezone.utc)

    # 1. Descoberta de arquivos originais
    raw_logs = []
    har_files = []
    source_dirs = []
    metadata_files = []

    for item in analysis_dir.iterdir():
        if item == results_dir or item.name.startswith("analysis-results-") or item.name.startswith("."):
            continue

        if item.is_file():
            if item.suffix.lower() in (".log", ".txt", ".jsonl"):
                raw_logs.append(item)
            elif item.suffix.lower() == ".har":
                har_files.append(item)
            elif item.name in ("incident.json", "metadata.json") or item.suffix.lower() == ".json":
                metadata_files.append(item)
        elif item.is_dir():
            if item.name.lower() in ("logs", "log"):
                for sub_f in item.rglob("*"):
                    if sub_f.is_file() and sub_f.suffix.lower() in (".log", ".txt", ".jsonl"):
                        raw_logs.append(sub_f)
            elif item.name.lower() == "har":
                for sub_f in item.rglob("*.har"):
                    if sub_f.is_file():
                        har_files.append(sub_f)
            elif item.name.lower() in ("source", "src"):
                source_dirs.append(item)
            elif item.name.lower() == "metadata":
                for sub_f in item.rglob("*.json"):
                    if sub_f.is_file():
                        metadata_files.append(sub_f)

    # Ler metadata se existente
    incident_metadata = {}
    for mf in metadata_files:
        try:
            parsed = json.loads(mf.read_text(encoding="utf-8-sig", errors="replace"))
            if isinstance(parsed, dict):
                incident_metadata.update(parsed)
        except Exception:
            pass

    # Unificar conteudo de logs
    combined_log_text = ""
    for lf in raw_logs:
        try:
            combined_log_text += lf.read_text(encoding="utf-8-sig", errors="replace") + "\n"
        except Exception as e:
            warnings.append(f"Erro ao ler log {lf.name}: {e}")

    # =========================================================================
    # ETAPA 1: log-sanitizer
    # =========================================================================
    sanitized_text = combined_log_text
    sanitizer_mod = _import_plugin_domain("log-sanitizer")
    if sanitizer_mod and hasattr(sanitizer_mod, "sanitize_content"):
        try:
            san_res = sanitizer_mod.sanitize_content(combined_log_text)
            sanitized_text = san_res.get("sanitized_content") or san_res.get("sanitized_text") or combined_log_text
            (results_dir / "sanitized" / "sanitized_logs.txt").write_text(sanitized_text, encoding="utf-8")
            (results_dir / "sanitized" / "summary.json").write_text(json.dumps(san_res.get("summary", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "log-sanitizer", "status": "success", "files_produced": ["sanitized/sanitized_logs.txt", "sanitized/summary.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-sanitizer", "status": "error", "error": str(e)})
            warnings.append(f"Falha na sanitizacao: {e}")
    else:
        execution_steps.append({"step": "log-sanitizer", "status": "skipped", "reason": "plugin indisponivel"})

    # =========================================================================
    # ETAPA 2: incident-filter
    # =========================================================================
    filtered_res = {}
    filter_mod = _import_plugin_domain("incident-filter")
    if filter_mod and hasattr(filter_mod, "filter_incident_logs"):
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
            filtered_res = filter_mod.filter_incident_logs(sanitized_text, filter_opts)
            (results_dir / "filtered" / "filtered_logs.json").write_text(json.dumps(filtered_res, indent=2, ensure_ascii=False), encoding="utf-8")
            if "formatted_output" in filtered_res:
                (results_dir / "filtered" / "filtered_compact.txt").write_text(filtered_res["formatted_output"], encoding="utf-8")
            execution_steps.append({"step": "incident-filter", "status": "success", "files_produced": ["filtered/filtered_logs.json"]})
        except Exception as e:
            execution_steps.append({"step": "incident-filter", "status": "error", "error": str(e)})
            warnings.append(f"Falha no filtro de incidente: {e}")
    else:
        execution_steps.append({"step": "incident-filter", "status": "skipped"})

    # =========================================================================
    # ETAPA 3: log-optimizer
    # =========================================================================
    log_opt_res = {}
    opt_mod = _import_plugin_domain("log-optimizer")
    if opt_mod and hasattr(opt_mod, "optimize_logs"):
        try:
            opt_input_text = sanitized_text
            log_opt_res = opt_mod.optimize_logs(opt_input_text)
            (results_dir / "optimized" / "log_summary.json").write_text(json.dumps(log_opt_res, indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "log-optimizer", "status": "success", "files_produced": ["optimized/log_summary.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-optimizer", "status": "error", "error": str(e)})
            warnings.append(f"Falha no log-optimizer: {e}")
    else:
        execution_steps.append({"step": "log-optimizer", "status": "skipped"})

    # =========================================================================
    # ETAPA 4: log-cluster
    # =========================================================================
    cluster_res = {}
    cluster_mod = _import_plugin_domain("log-cluster")
    if cluster_mod and hasattr(cluster_mod, "cluster_logs"):
        try:
            cluster_res = cluster_mod.cluster_logs(sanitized_text)
            (results_dir / "clusters" / "clusters.json").write_text(json.dumps(cluster_res, indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "log-cluster", "status": "success", "files_produced": ["clusters/clusters.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-cluster", "status": "error", "error": str(e)})
            warnings.append(f"Falha no cluster de logs: {e}")
    else:
        execution_steps.append({"step": "log-cluster", "status": "skipped"})

    # =========================================================================
    # ETAPA 5: log-timeline
    # =========================================================================
    timeline_res = {}
    timeline_mod = _import_plugin_domain("log-timeline")
    if timeline_mod and hasattr(timeline_mod, "generate_log_timeline"):
        try:
            timeline_res = timeline_mod.generate_log_timeline(sanitized_text, {"output_format": "markdown"})
            (results_dir / "timelines" / "timeline.json").write_text(json.dumps(timeline_res, indent=2, ensure_ascii=False), encoding="utf-8")
            if "formatted_output" in timeline_res:
                (results_dir / "timelines" / "timeline.md").write_text(timeline_res["formatted_output"], encoding="utf-8")
            execution_steps.append({"step": "log-timeline", "status": "success", "files_produced": ["timelines/timeline.json"]})
        except Exception as e:
            execution_steps.append({"step": "log-timeline", "status": "error", "error": str(e)})
            warnings.append(f"Falha na timeline: {e}")
    else:
        execution_steps.append({"step": "log-timeline", "status": "skipped"})

    # =========================================================================
    # ETAPA 6: har-optimizer
    # =========================================================================
    har_res = {}
    har_mod = _import_plugin_domain("har-optimizer")
    if har_files and har_mod and hasattr(har_mod, "optimize_har"):
        try:
            har_content = har_files[0].read_text(encoding="utf-8-sig", errors="replace")
            har_res = har_mod.optimize_har(har_content)
            (results_dir / "optimized" / "har_optimized.json").write_text(json.dumps(har_res, indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "har-optimizer", "status": "success", "files_produced": ["optimized/har_optimized.json"]})
        except Exception as e:
            execution_steps.append({"step": "har-optimizer", "status": "error", "error": str(e)})
            warnings.append(f"Falha no har-optimizer: {e}")
    else:
        execution_steps.append({"step": "har-optimizer", "status": "skipped", "reason": "Nenhum arquivo HAR fornecido" if not har_files else "plugin indisponivel"})

    # =========================================================================
    # ETAPA 7: source-extractor
    # =========================================================================
    source_res = {}
    src_mod = _import_plugin_domain("source-extractor")
    if source_dirs and src_mod and hasattr(src_mod, "extract_sources"):
        try:
            terms = incident_metadata.get("keywords", []) or ["Exception", "Error", "500"]
            source_res = src_mod.extract_sources({"project_path": str(source_dirs[0]), "terms": terms})
            (results_dir / "source-extracts" / "extracts.json").write_text(json.dumps(source_res, indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "source-extractor", "status": "success", "files_produced": ["source-extracts/extracts.json"]})
        except Exception as e:
            execution_steps.append({"step": "source-extractor", "status": "error", "error": str(e)})
            warnings.append(f"Falha no source-extractor: {e}")
    else:
        execution_steps.append({"step": "source-extractor", "status": "skipped", "reason": "Nenhum diretorio de codigo encontrado" if not source_dirs else "plugin indisponivel"})

    # =========================================================================
    # ETAPA 8: evidence-package
    # =========================================================================
    evidence_res = {}
    evidence_mod = _import_plugin_domain("evidence-package")
    if evidence_mod and hasattr(evidence_mod, "build_evidence_package"):
        try:
            ev_payload = {
                "incident_info": incident_metadata,
                "summary_logs": log_opt_res.get("summary", {}),
                "clusters": cluster_res.get("clusters", []),
                "timeline": timeline_res.get("timeline", []),
                "har": har_res.get("optimized_har") if har_res else None,
                "time_range": incident_metadata.get("time_range")
            }
            evidence_res = evidence_mod.build_evidence_package(ev_payload)
            (results_dir / "evidence" / "manifest.json").write_text(json.dumps(evidence_res.get("manifest", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "incident-summary.json").write_text(json.dumps(evidence_res.get("incident_summary", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "evidence.json").write_text(json.dumps(evidence_res.get("evidence", []), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "timeline.json").write_text(json.dumps(evidence_res.get("timeline", []), indent=2, ensure_ascii=False), encoding="utf-8")
            (results_dir / "evidence" / "references.json").write_text(json.dumps(evidence_res.get("references", {}), indent=2, ensure_ascii=False), encoding="utf-8")
            execution_steps.append({"step": "evidence-package", "status": "success", "files_produced": ["evidence/evidence.json", "evidence/incident-summary.json"]})
        except Exception as e:
            execution_steps.append({"step": "evidence-package", "status": "error", "error": str(e)})
            warnings.append(f"Falha no evidence-package: {e}")
    else:
        execution_steps.append({"step": "evidence-package", "status": "skipped"})

    # =========================================================================
    # MANIFESTO E RESUMO DE EXECUCAO
    # =========================================================================
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

    # Relatorio executivo markdown
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
