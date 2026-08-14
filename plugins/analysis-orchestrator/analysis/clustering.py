import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

# Padroes Regex de Normalizacao
RE_TIMESTAMP = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b")
RE_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b")
RE_TIME = re.compile(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b")
RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
RE_HASH = re.compile(r"\b[0-9a-fA-F]{32,64}\b")
RE_URL = re.compile(r"https?://[^\s<>]+")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_DURATION = re.compile(r"(?i)\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|s|seconds?|min|minutes?|h|hours?|µs|ns)\b")
RE_SIZE = re.compile(r"(?i)\b\d+(?:\.\d+)?\s*(?:bytes?|B|KB|MB|GB|TB|KiB|MiB|GiB)\b")
RE_IP_PORT = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?\b")
RE_BRACKETED = re.compile(r"\[[^\]\r\n]{2,}\]")
RE_DECIMAL = re.compile(r"\b\d+\.\d+\b")
RE_INTEGER = re.compile(r"\b\d+\b")

# Extrator de Nivel e Servico
RE_LEVEL = re.compile(r"\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|TRACE)\b", re.IGNORECASE)
RE_SERVICE_BRACKET = re.compile(r"\[([a-zA-Z0-9_.-]{3,30})\]")


def normalize_message(msg: str) -> str:
    """Normaliza variaveis dinamicas de uma mensagem transformando-as em placeholders."""
    if not msg:
        return msg

    text = msg
    text = RE_TIMESTAMP.sub("<TIMESTAMP>", text)
    text = RE_DATE.sub("<DATE>", text)
    text = RE_TIME.sub("<TIME>", text)
    text = RE_UUID.sub("<UUID>", text)
    text = RE_HASH.sub("<HASH>", text)
    text = RE_URL.sub("<URL>", text)
    text = RE_EMAIL.sub("<EMAIL>", text)
    text = RE_DURATION.sub("<DURATION>", text)
    text = RE_SIZE.sub("<SIZE>", text)
    text = RE_IP_PORT.sub("<IP>", text)
    text = RE_BRACKETED.sub("<BRACKETED>", text)
    text = RE_DECIMAL.sub("<DECIMAL>", text)
    text = RE_INTEGER.sub("<INT>", text)
    return text


def parse_log_events(content: str) -> List[Dict[str, Any]]:
    """Agrupa linhas continuas de stack trace em eventos de log unicos."""
    lines = content.splitlines()
    events = []
    curr_event: Optional[Dict[str, Any]] = None

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        is_continuation = False
        if curr_event is not None:
            if raw_line.startswith((" ", "\t", "at ", "Caused by:", "...")):
                is_continuation = True
            elif line.startswith(("at ", "Caused by:", "...")):
                is_continuation = True

        if is_continuation and curr_event is not None:
            curr_event["lines"].append(raw_line)
            curr_event["line_numbers"].append(idx)
            continue

        if curr_event is not None:
            events.append(curr_event)

        level_match = RE_LEVEL.search(line)
        level = level_match.group(1).upper() if level_match else None

        srv_match = RE_SERVICE_BRACKET.search(line)
        service = srv_match.group(1) if srv_match else None

        curr_event = {
            "first_line_num": idx,
            "line_numbers": [idx],
            "lines": [raw_line],
            "level": level,
            "service": service
        }

    if curr_event is not None:
        events.append(curr_event)

    return events


def cluster_logs(content: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Clusteriza mensagens de log em templates estruturados com metricas."""
    options = options or {}
    group_by_service = bool(options.get("group_by_service", False))
    group_by_level = bool(options.get("group_by_level", False))
    max_samples = int(options.get("max_samples", 5))
    include_line_numbers = bool(options.get("include_line_numbers", True))

    events = parse_log_events(content)
    total_lines = len(content.splitlines())
    total_events = len(events)

    clusters_map = {}

    for ev in events:
        full_msg = "\n".join(ev["lines"])
        first_line = ev["lines"][0]
        template = normalize_message(first_line)

        srv_key = ev["service"] if group_by_service else None
        lvl_key = ev["level"] if group_by_level else None
        key = (template, srv_key, lvl_key)

        if key not in clusters_map:
            clusters_map[key] = {
                "template": template,
                "service": ev["service"],
                "level": ev["level"],
                "count": 0,
                "first_seen": {"line": ev["first_line_num"], "message": full_msg},
                "last_seen": {"line": ev["first_line_num"], "message": full_msg},
                "line_numbers": [],
                "samples": []
            }

        c = clusters_map[key]
        c["count"] += 1
        c["last_seen"] = {"line": ev["first_line_num"], "message": full_msg}
        if include_line_numbers:
            c["line_numbers"].extend(ev["line_numbers"])
        if full_msg not in c["samples"] and len(c["samples"]) < max_samples:
            c["samples"].append(full_msg)

    cluster_list = sorted(clusters_map.values(), key=lambda x: x["count"], reverse=True)
    total_clusters = len(cluster_list)

    for c in cluster_list:
        c["percentage"] = round((c["count"] / total_events * 100), 2) if total_events > 0 else 0.0

    reduction_percentage = round((1.0 - (total_clusters / total_events)) * 100, 2) if total_events > 0 else 0.0
    unclustered_count = sum(1 for c in cluster_list if c["count"] == 1)

    return {
        "summary": {
            "total_lines": total_lines,
            "total_events": total_events,
            "total_clusters": total_clusters,
            "unclustered_count": unclustered_count,
            "reduction_percentage": reduction_percentage
        },
        "clusters": cluster_list
    }
