import datetime
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

RE_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b")
RE_LEVEL_ERROR = re.compile(r"\b(ERROR|FATAL|CRITICAL|SEVERE)\b", re.IGNORECASE)
RE_TIMEOUT = re.compile(r"(?i)\b(?:timeout|timed out|gateway timeout)\b")
RE_RETRY = re.compile(r"(?i)\b(?:retry|retrying)\b")

DISCLAIMER_TEXT = "DISCLAIMER: Este pacote de evidencias contem exclusivamente dados, registros e correlacoes deterministicas consolidadas. Nao contem inferencias, conclusoes ou afirmacoes de causa raiz."


def parse_timestamp(text: str) -> Optional[datetime.datetime]:
    if not text:
        return None
    m = RE_ISO.search(str(text))
    if m:
        raw = m.group(1).replace(",", ".").replace("Z", "+00:00")
        try:
            return datetime.datetime.fromisoformat(raw)
        except Exception:
            pass
    return None


def format_iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_evidence_package(payload: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Consolida logs, HAR, timeline e dados de incidentes em um pacote de evidências estruturado."""
    options = options or {}
    max_items = int(options.get("max_evidence_items", 500))

    incident_info = payload.get("incident_info") or payload.get("incident") or {}
    service = incident_info.get("service") or payload.get("service") or "unknown"
    environment = incident_info.get("environment") or payload.get("environment") or "production"
    incident_id = incident_info.get("id") or payload.get("incident_id") or "INC-0000"
    incident_title = incident_info.get("title") or payload.get("title") or "Incidente sob investigacao"

    time_range = payload.get("time_range") or incident_info.get("time_range") or {}
    dt_from = parse_timestamp(time_range.get("from")) if isinstance(time_range, dict) and time_range.get("from") else None
    dt_to = parse_timestamp(time_range.get("to")) if isinstance(time_range, dict) and time_range.get("to") else None

    # Coletar IDs de correlação informados
    correlation_ids_in = payload.get("correlation_ids") or []
    target_ids: Set[str] = set()
    if isinstance(correlation_ids_in, dict):
        for k, v in correlation_ids_in.items():
            if isinstance(v, list):
                for val in v:
                    if str(val).strip():
                        target_ids.add(str(val).strip().lower())
            elif isinstance(v, (str, int)):
                if str(v).strip():
                    target_ids.add(str(v).strip().lower())
    elif isinstance(correlation_ids_in, list):
        for val in correlation_ids_in:
            if str(val).strip():
                target_ids.add(str(val).strip().lower())

    evidence_list: List[Dict[str, Any]] = []
    timeline_list: List[Dict[str, Any]] = []
    references_dict: Dict[str, Any] = {
        "files": [],
        "lines": [],
        "har_requests": [],
        "clusters": []
    }

    seen_signatures: Set[str] = set()
    warnings: List[str] = []
    first_error_dt = None
    first_error_item = None
    errors_count = 0

    # 1. Ingerir HAR otimizado se presente
    har_data = payload.get("har") or payload.get("har_optimized") or {}
    if isinstance(har_data, dict) and "log" in har_data:
        entries = har_data["log"].get("entries", [])
        for idx, entry in enumerate(entries, start=1):
            req = entry.get("request", {})
            resp = entry.get("response", {})
            started = entry.get("startedDateTime", "")
            dt = parse_timestamp(started)
            status = int(resp.get("status", 0))
            url = req.get("url", "")
            method = req.get("method", "GET")

            # Filtro de tempo se fornecido
            if dt:
                if dt_from and dt < dt_from:
                    continue
                if dt_to and dt > dt_to:
                    continue

            is_error = status >= 400
            if is_error:
                errors_count += 1
                if not first_error_dt or (dt and dt < first_error_dt):
                    first_error_dt = dt
                    first_error_item = f"HTTP {status} {method} {url}"

            ev_id = f"ev_http_{idx}"
            sig = f"http:{method}:{url}:{started}:{status}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            references_dict["har_requests"].append({"id": ev_id, "index": idx, "url": url, "status": status})

            ev_item = {
                "id": ev_id,
                "type": "http_request",
                "timestamp": format_iso(dt) if dt else started,
                "service": service,
                "environment": environment,
                "is_priority": is_error or status in (408, 429, 500, 502, 503, 504),
                "is_error": is_error,
                "source_ref": {"har_index": idx, "url": url},
                "data": {
                    "method": method,
                    "url": url,
                    "status": status,
                    "duration_ms": entry.get("time", 0.0),
                }
            }
            evidence_list.append(ev_item)
            timeline_list.append({
                "timestamp": format_iso(dt) if dt else started,
                "dt": dt,
                "source": "har",
                "summary": f"HTTP {status} {method} {url}",
                "is_error": is_error
            })

    # 2. Ingerir timeline.json ou timeline events se presente
    timeline_input = payload.get("timeline") or payload.get("timeline_events") or []
    if isinstance(timeline_input, dict) and "timeline" in timeline_input:
        timeline_input = timeline_input["timeline"]

    if isinstance(timeline_input, list):
        for idx, item in enumerate(timeline_input, start=1):
            ts = item.get("timestamp")
            dt = parse_timestamp(ts)
            msg = item.get("message") or item.get("summary") or str(item)
            is_err = bool(item.get("is_error", False)) or bool(RE_LEVEL_ERROR.search(msg))
            line_ref = item.get("line")

            if dt:
                if dt_from and dt < dt_from:
                    continue
                if dt_to and dt > dt_to:
                    continue

            if is_err:
                errors_count += 1
                if not first_error_dt or (dt and dt < first_error_dt):
                    first_error_dt = dt
                    first_error_item = msg[:100]

            sig = f"timeline:{line_ref}:{ts}:{msg[:50]}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            ev_id = f"ev_tl_{idx}"
            if line_ref:
                references_dict["lines"].append({"id": ev_id, "line": line_ref})

            ev_item = {
                "id": ev_id,
                "type": "timeline_event",
                "timestamp": format_iso(dt) if dt else ts,
                "service": service,
                "environment": environment,
                "is_priority": is_err or bool(item.get("is_priority", False)),
                "is_error": is_err,
                "source_ref": {"line": line_ref},
                "data": {"message": msg, "tags": item.get("tags", [])}
            }
            evidence_list.append(ev_item)
            timeline_list.append({
                "timestamp": format_iso(dt) if dt else ts,
                "dt": dt,
                "source": "timeline",
                "summary": msg[:120],
                "is_error": is_err
            })

    # 3. Ingerir clusters de log se presente
    clusters_input = payload.get("clusters") or payload.get("clusters_data") or []
    if isinstance(clusters_input, dict) and "clusters" in clusters_input:
        clusters_input = clusters_input["clusters"]

    if isinstance(clusters_input, list):
        for idx, cl in enumerate(clusters_input, start=1):
            tmpl = cl.get("template", "")
            count = cl.get("count", 1)
            first_seen = cl.get("first_seen", {})
            fs_msg = first_seen.get("message", tmpl)
            fs_line = first_seen.get("line")
            dt = parse_timestamp(fs_msg)
            is_err = bool(RE_LEVEL_ERROR.search(tmpl))

            sig = f"cluster:{tmpl[:50]}:{fs_line}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            ev_id = f"ev_cluster_{idx}"
            references_dict["clusters"].append({"id": ev_id, "template": tmpl, "count": count, "line": fs_line})

            ev_item = {
                "id": ev_id,
                "type": "log",
                "timestamp": format_iso(dt) if dt else None,
                "service": cl.get("service") or service,
                "environment": environment,
                "is_priority": is_err or count > 5,
                "is_error": is_err,
                "source_ref": {"cluster_group": idx, "first_line": fs_line},
                "data": {
                    "template": tmpl,
                    "frequency": count,
                    "samples": cl.get("samples", [])[:2]
                }
            }
            evidence_list.append(ev_item)

    # 4. Ingerir logs brutos ou summary.json
    logs_summary = payload.get("summary_logs") or payload.get("logs") or []
    if isinstance(logs_summary, list):
        for idx, l in enumerate(logs_summary, start=1):
            l_str = str(l)
            dt = parse_timestamp(l_str)
            is_err = bool(RE_LEVEL_ERROR.search(l_str))
            sig = f"log_item:{l_str[:60]}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            ev_id = f"ev_log_{idx}"
            evidence_list.append({
                "id": ev_id,
                "type": "log",
                "timestamp": format_iso(dt) if dt else None,
                "service": service,
                "environment": environment,
                "is_priority": is_err,
                "is_error": is_err,
                "source_ref": {"index": idx},
                "data": {"message": l_str}
            })

    # Ordenar linha do tempo unificada
    timeline_with_dt = [t for t in timeline_list if t["dt"] is not None]
    timeline_without_dt = [t for t in timeline_list if t["dt"] is None]
    timeline_with_dt.sort(key=lambda x: x["dt"])
    final_timeline = [
        {"timestamp": t["timestamp"], "source": t["source"], "summary": t["summary"], "is_error": t["is_error"]}
        for t in (timeline_with_dt + timeline_without_dt)
    ]

    # Priorizar e limitar evidências
    priority_evidence = [e for e in evidence_list if e["is_priority"]]
    other_evidence = [e for e in evidence_list if not e["is_priority"]]
    all_evidence = priority_evidence + other_evidence

    is_truncated = len(all_evidence) > max_items
    if is_truncated:
        warnings.append(f"Lista de evidencias limitada a {max_items} itens configurados.")
    final_evidence = all_evidence[:max_items]

    now_iso = format_iso(datetime.datetime.now(datetime.timezone.utc))

    manifest = {
        "package_version": "1.0.0",
        "generated_at": now_iso,
        "incident_id": incident_id,
        "environment": environment,
        "service": service,
        "disclaimer": DISCLAIMER_TEXT,
        "bundled_files": [
            "manifest.json",
            "incident-summary.json",
            "evidence.json",
            "timeline.json",
            "references.json"
        ]
    }

    incident_summary = {
        "incident_id": incident_id,
        "title": incident_title,
        "environment": environment,
        "service": service,
        "time_range": {
            "from": format_iso(dt_from) if dt_from else time_range.get("from"),
            "to": format_iso(dt_to) if dt_to else time_range.get("to")
        },
        "stats": {
            "total_evidence_items": len(final_evidence),
            "total_timeline_events": len(final_timeline),
            "errors_observed": errors_count,
            "first_error": {
                "timestamp": format_iso(first_error_dt) if first_error_dt else None,
                "summary": first_error_item
            } if first_error_item else None,
            "is_truncated": is_truncated
        },
        "disclaimer": DISCLAIMER_TEXT
    }

    return {
        "manifest": manifest,
        "incident_summary": incident_summary,
        "evidence": final_evidence,
        "timeline": final_timeline[:200],
        "references": references_dict,
        "warnings": warnings,
        "disclaimer": DISCLAIMER_TEXT
    }
