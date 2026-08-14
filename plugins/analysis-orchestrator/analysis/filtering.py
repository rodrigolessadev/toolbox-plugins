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

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

RE_LEVEL = re.compile(r"\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|TRACE|SEVERE)\b", re.IGNORECASE)
RE_SERVICE = re.compile(r"\[([a-zA-Z0-9_.-]{3,30})\]")
RE_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
RE_BEARER = re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9._~+/-]+=*")


def parse_timestamp(text: str) -> Optional[datetime.datetime]:
    if not text:
        return None
    m = RE_ISO.search(text)
    if m:
        raw = m.group(1).replace(",", ".").replace("Z", "+00:00")
        try:
            return datetime.datetime.fromisoformat(raw)
        except Exception:
            pass

    m = RE_BR.search(text)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            parts = raw.split(" ")
            d_parts = parts[0].split("/")
            t_parts = parts[1].split(":")
            sec_parts = t_parts[2].split(".")
            micro = int(sec_parts[1][:6].ljust(6, "0")) if len(sec_parts) > 1 else 0
            return datetime.datetime(int(d_parts[2]), int(d_parts[1]), int(d_parts[0]), int(t_parts[0]), int(t_parts[1]), int(sec_parts[0]), micro, tzinfo=datetime.timezone.utc)
        except Exception:
            pass

    m = RE_SYSLOG.search(text)
    if m:
        mon = MONTH_MAP.get(m.group(1).lower(), 1)
        day = int(m.group(2))
        year = datetime.datetime.now().year
        t_parts = m.group(3).split(":")
        return datetime.datetime(year, mon, day, int(t_parts[0]), int(t_parts[1]), int(t_parts[2]), tzinfo=datetime.timezone.utc)

    m = RE_EPOCH_MS.search(text)
    if m:
        return datetime.datetime.fromtimestamp(int(m.group(1)) / 1000.0, tz=datetime.timezone.utc)

    return None


def format_iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def sanitize_text(text: str) -> str:
    if not text:
        return text
    t = RE_JWT.sub("[REDACTED_JWT]", text)
    t = RE_BEARER.sub("Bearer [REDACTED]", t)
    return t


def extract_event_fields(raw_msg: str) -> Dict[str, Any]:
    dt = parse_timestamp(raw_msg)
    lvl_match = RE_LEVEL.search(raw_msg)
    level = lvl_match.group(1).upper() if lvl_match else None
    if level == "WARNING":
        level = "WARN"

    srv_match = RE_SERVICE.search(raw_msg)
    service = srv_match.group(1) if srv_match else None

    return {
        "dt": dt,
        "timestamp": format_iso(dt),
        "level": level,
        "service": service
    }


def filter_incident_logs(content: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Filtra logs de incidente determinísticamente com base em critérios e contexto."""
    options = options or {}
    time_range = options.get("time_range") or {}
    dt_from = parse_timestamp(time_range.get("from")) if isinstance(time_range, dict) and time_range.get("from") else None
    dt_to = parse_timestamp(time_range.get("to")) if isinstance(time_range, dict) and time_range.get("to") else None

    levels = {lvl.upper().replace("WARNING", "WARN") for lvl in options.get("levels", [])}
    services = {s.lower() for s in options.get("services", [])}
    keywords = [kw.lower() for kw in options.get("keywords", []) if kw]
    correlation_ids = options.get("correlation_ids") or {}
    context_lines = int(options.get("context_lines", 0))
    max_events = int(options.get("max_events", 500))
    include_correlated = bool(options.get("include_correlated_regardless_of_level", True))
    sanitize = bool(options.get("sanitize_sensitive_data", True))
    output_format = str(options.get("output_format", "json")).lower()

    # Coletar todos os IDs solicitados em um conjunto
    target_ids: Set[str] = set()
    if isinstance(correlation_ids, dict):
        for k, v in correlation_ids.items():
            if isinstance(v, list):
                for val in v:
                    if str(val).strip():
                        target_ids.add(str(val).strip().lower())
            elif isinstance(v, (str, int)):
                if str(v).strip():
                    target_ids.add(str(v).strip().lower())

    # Fazer parsing dos eventos
    lines = content.splitlines()
    raw_events = []
    curr_event = None

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        dt = parse_timestamp(line)
        if dt is None and curr_event is not None and (raw_line.startswith((" ", "\t", "at ", "Caused by:", "...")) or line.startswith(("at ", "Caused by:", "..."))):
            curr_event["lines"].append(raw_line)
            continue

        if curr_event is not None:
            full_msg = "\n".join(curr_event["lines"])
            f_data = extract_event_fields(full_msg)
            raw_events.append({
                "line": curr_event["line"],
                "raw": full_msg,
                **f_data
            })

        curr_event = {
            "line": idx,
            "lines": [raw_line]
        }

    if curr_event is not None:
        full_msg = "\n".join(curr_event["lines"])
        f_data = extract_event_fields(full_msg)
        raw_events.append({
            "line": curr_event["line"],
            "raw": full_msg,
            "**": f_data
        })
        raw_events[-1].update(f_data)

    total_scanned = len(raw_events)

    # Avaliação de Match
    matched_indices: Set[int] = set()

    for idx, ev in enumerate(raw_events):
        msg_lower = ev["raw"].lower()

        # 1. Checar correlacao de IDs
        has_correlation_match = False
        if target_ids:
            for tid in target_ids:
                if tid in msg_lower:
                    has_correlation_match = True
                    break

        # 2. Checar filtro de tempo
        if ev["dt"] is not None:
            if dt_from and ev["dt"] < dt_from:
                continue
            if dt_to and ev["dt"] > dt_to:
                continue
        elif dt_from or dt_to:
            # Sem timestamp: se nao bateu correlacao forte, ignora
            if not has_correlation_match:
                continue

        # 3. Se for correlacionado e tiver bypass ativo
        if has_correlation_match and include_correlated:
            matched_indices.add(idx)
            continue

        # 4. Checar nivel
        if levels:
            if not ev["level"] or ev["level"] not in levels:
                continue

        # 5. Checar servico
        if services:
            if not ev["service"] or ev["service"].lower() not in services:
                continue

        # 6. Checar palavras-chave
        if keywords:
            if not any(kw in msg_lower for kw in keywords):
                continue

        # Se passou em todos os filtros ativos
        matched_indices.add(idx)

    # Expandir contexto (context_lines)
    all_included_indices: Set[int] = set()
    for m_idx in matched_indices:
        start_c = max(0, m_idx - context_lines)
        end_c = min(len(raw_events), m_idx + context_lines + 1)
        for c in range(start_c, end_c):
            all_included_indices.add(c)

    sorted_indices = sorted(list(all_included_indices))

    # Construir lista de eventos finais
    final_events = []
    seen = set()
    discarded_count = total_scanned - len(matched_indices)

    for i in sorted_indices:
        ev = raw_events[i]
        msg = sanitize_text(ev["raw"]) if sanitize else ev["raw"]
        key = (ev["line"], ev["timestamp"], msg)
        if key in seen:
            continue
        seen.add(key)

        is_direct_match = i in matched_indices
        final_events.append({
            "line": ev["line"],
            "timestamp": ev["timestamp"],
            "level": ev["level"],
            "service": ev["service"],
            "is_match": is_direct_match,
            "is_context": not is_direct_match,
            "message": msg
        })

    is_truncated = len(final_events) > max_events
    truncated_events = final_events[:max_events]

    summary = {
        "total_scanned_events": total_scanned,
        "matched_events_count": len(matched_indices),
        "returned_events_count": len(truncated_events),
        "discarded_events_count": discarded_count,
        "context_lines_applied": context_lines,
        "is_truncated": is_truncated
    }

    result = {
        "summary": summary,
        "events": truncated_events,
        "warnings": []
    }

    if is_truncated:
        result["warnings"].append(f"Saida limitada ao maximo de {max_events} eventos configurados.")

    if output_format == "compact_text":
        result["formatted_output"] = format_compact_text(result)

    return result


def format_compact_text(res: Dict[str, Any]) -> str:
    lines = []
    for e in res["events"]:
        flag = "[MATCH]" if e["is_match"] else "[CTX]  "
        ts = e["timestamp"] or "[NO_TS]"
        lvl = f"[{e['level']}]" if e['level'] else ""
        srv = f"[{e['service']}]" if e['service'] else ""
        first_line = e["message"].splitlines()[0]
        lines.append(f"{flag} L{e['line']:04d} | {ts} | {lvl}{srv} {first_line}")
    return "\n".join(lines)
