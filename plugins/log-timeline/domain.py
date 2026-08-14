import datetime
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Regex de Timestamps
RE_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b")
RE_BR = re.compile(r"\b(\d{2}/\d{2}/\d{4}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\b")
RE_SYSLOG = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\b", re.IGNORECASE)
RE_EPOCH_MS = re.compile(r"\b(1\d{12})\b")
RE_EPOCH_S = re.compile(r"\b(1\d{9}(?:\.\d+)?)\b")

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

# Regex de Niveis
RE_LEVEL_ERROR = re.compile(r"\b(ERROR|FATAL|CRITICAL|SEVERE|EMERGENCY)\b", re.IGNORECASE)
RE_LEVEL_WARN = re.compile(r"\b(WARN|WARNING)\b", re.IGNORECASE)
RE_LEVEL_INFO = re.compile(r"\b(INFO|NOTICE)\b", re.IGNORECASE)
RE_LEVEL_DEBUG = re.compile(r"\b(DEBUG|TRACE)\b", re.IGNORECASE)
RE_EXCEPTION = re.compile(r"\b([A-Za-z_]+(?:Exception|Error|Failure))\b")
RE_HTTP_CODE = re.compile(r"\b(?:HTTP|status|code|response)\s*[:=]?\s*([45]\d{2})\b|\b([45]\d{2})\s*(?:Internal Server Error|Bad Request|Unauthorized|Forbidden|Not Found|Gateway Timeout|Service Unavailable)\b", re.IGNORECASE)

# Padroes Operacionais
PATTERNS = {
    "CIRCUIT_BREAKER": re.compile(r"\b(?:circuit[ -]breaker|open circuit|short circuit)\b", re.IGNORECASE),
    "TIMEOUT": re.compile(r"\b(?:timeout|timed out|request timed out|gateway timeout)\b", re.IGNORECASE),
    "RETRY": re.compile(r"\b(?:retry|retrying|attempt\s+\d+)\b", re.IGNORECASE),
    "CONN_REFUSED": re.compile(r"\b(?:connection refused|conn refused|econnrefused)\b", re.IGNORECASE),
    "DEPLOYMENT": re.compile(r"\b(?:deploying|deployed|deployment|release\s+v?\d+)\b", re.IGNORECASE),
    "STARTUP": re.compile(r"\b(?:starting|started|startup|booting|bootstrapped|listening on)\b", re.IGNORECASE),
    "SHUTDOWN": re.compile(r"\b(?:stopping|stopped|shutdown|shutting down|terminating|terminated)\b", re.IGNORECASE),
}

# Correlacoes
CORRELATION_KEYS = ["request_id", "requestId", "trace_id", "traceId", "correlation_id", "correlationId", "order_id", "orderId", "user_id", "userId"]


def parse_timestamp_string(text: str) -> Tuple[Optional[datetime.datetime], Optional[str]]:
    """Extrai e converte timestamp para datetime UTC."""
    if not text:
        return None, None

    # 1. ISO 8601
    m = RE_ISO.search(text)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            clean = raw.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(clean)
            return dt, raw
        except Exception:
            pass

    # 2. BR Format (DD/MM/YYYY HH:MM:SS)
    m = RE_BR.search(text)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            parts = raw.split(" ")
            d_parts = parts[0].split("/")
            day, month, year = int(d_parts[0]), int(d_parts[1]), int(d_parts[2])
            time_part = parts[1]
            t_parts = time_part.split(":")
            hour, minute = int(t_parts[0]), int(t_parts[1])
            sec_parts = t_parts[2].split(".")
            sec = int(sec_parts[0])
            micro = int(sec_parts[1][:6].ljust(6, "0")) if len(sec_parts) > 1 else 0
            dt = datetime.datetime(year, month, day, hour, minute, sec, micro, tzinfo=datetime.timezone.utc)
            return dt, raw
        except Exception:
            pass

    # 3. Syslog Format (e.g. Aug 14 10:00:00)
    m = RE_SYSLOG.search(text)
    if m:
        mon_str, day_str, time_str = m.group(1).lower(), m.group(2), m.group(3)
        month = MONTH_MAP.get(mon_str, 1)
        day = int(day_str)
        year = datetime.datetime.now().year
        t_parts = time_str.split(":")
        dt = datetime.datetime(year, month, day, int(t_parts[0]), int(t_parts[1]), int(t_parts[2]), tzinfo=datetime.timezone.utc)
        return dt, m.group(0)

    # 4. Epoch MS
    m = RE_EPOCH_MS.search(text)
    if m:
        ts = int(m.group(1)) / 1000.0
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        return dt, m.group(1)

    return None, None


def format_iso(dt: datetime.datetime) -> str:
    """Retorna string ISO 8601 UTC padronizada."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def extract_correlations(text: str) -> Dict[str, str]:
    corrs = {}
    for k in CORRELATION_KEYS:
        pat = re.compile(r"(?i)\b" + re.escape(k) + r"\b\s*[:=]\s*['\"]?([a-zA-Z0-9_-]{6,64})")
        m = pat.search(text)
        if m:
            val = m.group(1).strip(" '\"")
            corrs[k] = val
    return corrs


def parse_raw_events(content: str) -> Tuple[List[Dict[str, Any]], int]:
    """Parse flexivel de texto plano, JSON Lines, JSONs de eventos ou log-optimizer."""
    events = []
    without_timestamp = 0

    trimmed = content.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                for idx, item in enumerate(parsed, start=1):
                    if isinstance(item, dict):
                        ts_str = item.get("timestamp") or item.get("@timestamp") or item.get("time") or str(item)
                        dt, raw_ts = parse_timestamp_string(str(ts_str))
                        msg = item.get("message") or item.get("msg") or json.dumps(item, ensure_ascii=False)
                        lvl = item.get("level") or item.get("status") or ""
                        full_msg = f"[{lvl}] {msg}" if lvl and lvl not in msg else msg
                        events.append({
                            "line": idx,
                            "raw": full_msg,
                            "timestamp": format_iso(dt) if dt else None,
                            "dt": dt,
                            "structured": item
                        })
                        if not dt:
                            without_timestamp += 1
                return events, without_timestamp

            if isinstance(parsed, dict):
                entries = parsed.get("lines") or parsed.get("events") or parsed.get("result", {}).get("clusters") or []
                if entries and isinstance(entries, list):
                    for idx, item in enumerate(entries, start=1):
                        msg = item.get("template") or item.get("message") or str(item)
                        first_seen = item.get("first_seen", {})
                        ts_str = first_seen.get("message", "") or msg
                        dt, raw_ts = parse_timestamp_string(ts_str)
                        lvl = item.get("level") or ""
                        full_msg = f"[{lvl}] {msg}" if lvl and lvl not in msg else msg
                        events.append({
                            "line": first_seen.get("line", idx),
                            "raw": full_msg,
                            "timestamp": format_iso(dt) if dt else None,
                            "dt": dt,
                            "structured": item
                        })
                        if not dt:
                            without_timestamp += 1
                    return events, without_timestamp
        except Exception:
            pass

    lines = content.splitlines()
    curr_event: Optional[Dict[str, Any]] = None

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        dt, raw_ts = parse_timestamp_string(line)

        if dt is None and curr_event is not None and (raw_line.startswith((" ", "\t", "at ", "Caused by:", "...")) or line.startswith(("at ", "Caused by:", "..."))):
            curr_event["lines"].append(raw_line)
            continue

        if curr_event is not None:
            full_msg = "\n".join(curr_event["lines"])
            events.append({
                "line": curr_event["line"],
                "raw": full_msg,
                "timestamp": format_iso(curr_event["dt"]) if curr_event["dt"] else None,
                "dt": curr_event["dt"]
            })
            if not curr_event["dt"]:
                without_timestamp += 1

        curr_event = {
            "line": idx,
            "dt": dt,
            "lines": [raw_line]
        }

    if curr_event is not None:
        full_msg = "\n".join(curr_event["lines"])
        events.append({
            "line": curr_event["line"],
            "raw": full_msg,
            "timestamp": format_iso(curr_event["dt"]) if curr_event["dt"] else None,
            "dt": curr_event["dt"]
        })
        if not curr_event["dt"]:
            without_timestamp += 1

    return events, without_timestamp


def classify_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    text = ev["raw"]
    tags = []
    is_error = False
    is_priority = False

    struct = ev.get("structured", {})
    if isinstance(struct, dict):
        lvl = str(struct.get("level", "")).upper()
        if lvl in ("ERROR", "FATAL", "CRITICAL", "SEVERE"):
            is_error = True
            is_priority = True
            tags.append(lvl)

    if RE_LEVEL_ERROR.search(text):
        if "ERROR" not in tags:
            tags.append("ERROR")
        is_error = True
        is_priority = True
    elif RE_LEVEL_WARN.search(text):
        if "WARN" not in tags:
            tags.append("WARN")
    elif RE_LEVEL_INFO.search(text):
        if "INFO" not in tags:
            tags.append("INFO")
    elif RE_LEVEL_DEBUG.search(text):
        if "DEBUG" not in tags:
            tags.append("DEBUG")

    exc_match = RE_EXCEPTION.search(text)
    if exc_match:
        tags.append(f"EXCEPTION:{exc_match.group(1)}")
        is_error = True
        is_priority = True

    http_match = RE_HTTP_CODE.search(text)
    if http_match:
        code = http_match.group(1) or http_match.group(2)
        tags.append(f"HTTP_{code}")
        is_error = True
        is_priority = True

    for p_name, pat in PATTERNS.items():
        if pat.search(text):
            tags.append(p_name)
            is_priority = True
            if p_name in ("CIRCUIT_BREAKER", "TIMEOUT", "CONN_REFUSED"):
                is_error = True

    correlations = extract_correlations(text)
    if correlations:
        is_priority = True

    return {
        "line": ev["line"],
        "timestamp": ev["timestamp"],
        "dt": ev["dt"],
        "message": text,
        "is_error": is_error,
        "is_priority": is_priority,
        "tags": tags,
        "correlations": correlations
    }


def bucket_floor(dt: datetime.datetime, interval_str: str) -> str:
    """Arredonda timestamp para balde de tempo (1s, 1m, 5m, 10m)."""
    if interval_str == "1s":
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    elif interval_str == "5m":
        minute = (dt.minute // 5) * 5
        return dt.strftime(f"%Y-%m-%dT%H:{minute:02d}:00Z")
    elif interval_str == "10m":
        minute = (dt.minute // 10) * 10
        return dt.strftime(f"%Y-%m-%dT%H:{minute:02d}:00Z")
    else:  # 1m padrao
        return dt.strftime("%Y-%m-%dT%H:%M:00Z")


def generate_log_timeline(content: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Gera linha do tempo cronológica ordenada e métricas de incidentes."""
    options = options or {}
    interval = str(options.get("interval", "1m")).lower()
    only_priority = bool(options.get("only_priority", False))
    output_format = str(options.get("output_format", "json")).lower()

    raw_events, without_ts_count = parse_raw_events(content)

    classified_events = [classify_event(e) for e in raw_events]

    events_with_ts = [e for e in classified_events if e["dt"] is not None]
    events_without_ts = [e for e in classified_events if e["dt"] is None]

    events_with_ts.sort(key=lambda x: x["dt"])
    sorted_events = events_with_ts + events_without_ts

    seen = set()
    deduped_events = []
    discarded_count = 0
    for e in sorted_events:
        key = (e["line"], e["timestamp"], e["message"])
        if key in seen:
            discarded_count += 1
            continue
        seen.add(key)
        deduped_events.append(e)

    if only_priority:
        timeline_events = [e for e in deduped_events if e["is_priority"]]
    else:
        timeline_events = deduped_events

    buckets_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"total": 0, "errors": 0, "events": []})
    for e in timeline_events:
        if e["dt"]:
            b_key = bucket_floor(e["dt"], interval)
            buckets_map[b_key]["total"] += 1
            if e["is_error"]:
                buckets_map[b_key]["errors"] += 1
            buckets_map[b_key]["events"].append(e["line"])

    bucket_list = [{"bucket": k, "total": v["total"], "errors": v["errors"], "lines": v["events"][:10]} for k, v in sorted(buckets_map.items())]

    first_event = timeline_events[0] if timeline_events else None
    first_error = next((e for e in timeline_events if e["is_error"]), None)
    last_event = timeline_events[-1] if timeline_events else None

    error_peak = None
    if bucket_list:
        error_peak = max(bucket_list, key=lambda b: b["errors"])
        if error_peak["errors"] == 0:
            error_peak = None

    def _clean_ev(ev: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not ev:
            return None
        return {
            "line": ev["line"],
            "timestamp": ev["timestamp"],
            "tags": ev["tags"],
            "message": ev["message"][:200]
        }

    summary = {
        "total_events": len(raw_events),
        "timeline_events_count": len(timeline_events),
        "events_without_timestamp": without_ts_count,
        "discarded_events": discarded_count,
        "first_event": _clean_ev(first_event),
        "first_error": _clean_ev(first_error),
        "error_peak": error_peak,
        "last_event": _clean_ev(last_event),
        "interval_used": interval
    }

    result = {
        "summary": summary,
        "buckets": bucket_list,
        "timeline": [
            {
                "line": e["line"],
                "timestamp": e["timestamp"],
                "is_error": e["is_error"],
                "is_priority": e["is_priority"],
                "tags": e["tags"],
                "correlations": e["correlations"],
                "message": e["message"]
            }
            for e in timeline_events[:100]
        ],
        "warnings": []
    }

    if without_ts_count > 0:
        result["warnings"].append(f"{without_ts_count} eventos nao possuiam timestamp e foram anexados ao final.")

    if output_format == "markdown":
        result["formatted_output"] = format_markdown(result)
    elif output_format == "compact_text":
        result["formatted_output"] = format_compact_text(result)

    return result


def format_markdown(res: Dict[str, Any]) -> str:
    lines = ["# ⏱️ Linha do Tempo de Incidentes", ""]
    s = res["summary"]
    lines.append(f"- **Total de Eventos**: {s['total_events']}")
    lines.append(f"- **Eventos na Linha do Tempo**: {s['timeline_events_count']}")
    if s["first_error"]:
        lines.append(f"- **Primeiro Erro**: Linha {s['first_error']['line']} às `{s['first_error']['timestamp']}` — {s['first_error']['tags']}")
    if s["error_peak"]:
        lines.append(f"- **Pico de Erros**: Balde `{s['error_peak']['bucket']}` com {s['error_peak']['errors']} erros")
    lines.append("")
    lines.append("## Eventos Cronológicos")
    lines.append("| Linha | Timestamp (UTC) | Tags | Mensagem |")
    lines.append("|---|---|---|---|")
    for e in res["timeline"][:30]:
        ts = e["timestamp"] or "Sem timestamp"
        tags_str = ", ".join(e["tags"]) if e["tags"] else "-"
        msg_preview = e["message"].splitlines()[0][:80].replace("|", "\\|")
        lines.append(f"| {e['line']} | `{ts}` | {tags_str} | {msg_preview} |")
    return "\n".join(lines)


def format_compact_text(res: Dict[str, Any]) -> str:
    lines = []
    for e in res["timeline"][:50]:
        ts = e["timestamp"] or "[NO_TS]"
        tags = f"[{' '.join(e['tags'])}]" if e["tags"] else ""
        first_line = e["message"].splitlines()[0]
        lines.append(f"L{e['line']:04d} | {ts} | {tags} {first_line}")
    return "\n".join(lines)
