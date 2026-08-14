import json
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Padrões Regex de Extração de Metadados
RE_TIMESTAMP = re.compile(
    r'(?P<iso>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'
    r'|(?P<br>\d{2}/\d{2}/\d{4}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
    r'|(?P<apache>\[\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}(?: [+-]\d{4})?\])'
    r'|(?P<syslog>[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'
)

RE_LEVEL = re.compile(
    r'\b(?P<level>FATAL|CRITICAL|ERROR|EXCEPTION|WARN|WARNING|INFO|DEBUG|TRACE|SEVERE)\b',
    re.IGNORECASE
)

RE_HTTP_STATUS = re.compile(r"\b(?:status[:=]?\s*|HTTP/\d\.\d[\"\s]+)(?P<status>[1-5]\d{2})\b", re.IGNORECASE)
RE_HTTP_METHOD = re.compile(r"\b(?P<method>GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(?P<endpoint>/[^\s\"\'?#]+)", re.IGNORECASE)

RE_REQUEST_ID = re.compile(r"(?:request[-_]?id|req[-_]?id|x-request-id)[:=\s\"]+([a-zA-Z0-9_-]{8,64})", re.IGNORECASE)
RE_TRACE_ID = re.compile(r"(?:trace[-_]?id|x-b3-traceid|traceId)[:=\s\"]+([a-zA-Z0-9_-]{8,64})", re.IGNORECASE)
RE_CORRELATION_ID = re.compile(r"(?:correlation[-_]?id|x-correlation-id|correlationId)[:=\s\"]+([a-zA-Z0-9_-]{8,64})", re.IGNORECASE)
RE_USER_ID = re.compile(r"(?:user[-_]?id|userId|usuario[-_]?id)[:=\s\"]+([a-zA-Z0-9_.@-]{3,64})", re.IGNORECASE)
RE_ORDER_ID = re.compile(r"(?:order[-_]?id|orderId|pedido[-_]?id)[:=\s\"]+([a-zA-Z0-9_-]{3,64})", re.IGNORECASE)
RE_SERVICE = re.compile(r"(?:service(?:[-_]?name)?|app(?:lication)?|servico)[:=\s\"\[]+([a-zA-Z0-9_-]{2,32})", re.IGNORECASE)

# Padrões de Mascaramento
RE_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
RE_BEARER = re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE)
RE_AUTH_BASIC = re.compile(r"(Basic\s+)[a-zA-Z0-9+/=]{15,}", re.IGNORECASE)
RE_API_KEY = re.compile(r"((?:api[-_]?key|apikey|secret[-_]?key|token|client[-_]?secret)[:=\s\"]+)[a-zA-Z0-9_\-]{16,}", re.IGNORECASE)
RE_PASSWORD = re.compile(r"((?:password|passwd|pwd|senha)[:=\s\"]+)[^\s\",;&]+", re.IGNORECASE)
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b(?<!\d)\d{11}(?!\d)\b")
RE_CREDIT_CARD = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
RE_COOKIE = re.compile(r"(Cookie:\s*)[^\r\n]+", re.IGNORECASE)

# Padrões de Normalização de Template
RE_NORM_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
RE_NORM_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b")
RE_NORM_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b|\b[0-9a-fA-F]{16,64}\b")
RE_NORM_NUM = re.compile(r"\b\d+\b")
RE_NORM_QUOTED = re.compile(r"\"[^\"]*\"|\'[^\']*\'")
RE_NORM_DURATION = re.compile(r"\b\d+(?:\.\d+)?(?:ms|s|m|µs|ns)\b", re.IGNORECASE)


@dataclass
class LogEvent:
    line_number: int
    raw_message: str
    message: str
    timestamp: Optional[str] = None
    level: str = "INFO"
    service: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    order_id: Optional[str] = None
    endpoint: Optional[str] = None
    http_status: Optional[int] = None
    is_error: bool = False
    stack_trace: Optional[str] = None
    template: str = ""


def mask_sensitive_data(text: str, mask_email: bool = True) -> str:
    """Aplica regras determinísticas de mascaramento de dados sensíveis."""
    if not text:
        return text

    text = RE_JWT.sub("[JWT_MASKED]", text)
    text = RE_BEARER.sub(r"\1[MASKED]", text)
    text = RE_AUTH_BASIC.sub(r"\1[MASKED]", text)
    text = RE_API_KEY.sub(r"\1[KEY_MASKED]", text)
    text = RE_PASSWORD.sub(r"\1[PASSWORD_MASKED]", text)
    text = RE_CREDIT_CARD.sub("[CARD_MASKED]", text)
    text = RE_CPF.sub("[CPF_MASKED]", text)
    text = RE_COOKIE.sub(r"\1[MASKED]", text)
    if mask_email:
        text = RE_EMAIL.sub("[EMAIL_MASKED]", text)
    return text


def normalize_template(message: str) -> str:
    """Gera um template determinístico substituindo valores dinâmicos."""
    t = RE_TIMESTAMP.sub("<TIMESTAMP>", message)
    t = RE_NORM_UUID.sub("<UUID>", t)
    t = RE_NORM_IP.sub("<IP>", t)
    t = RE_NORM_HEX.sub("<HEX>", t)
    t = RE_NORM_DURATION.sub("<DURATION>", t)
    t = RE_NORM_QUOTED.sub("<STR>", t)
    t = RE_NORM_NUM.sub("<NUM>", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_line_event(line: str, line_number: int, mask_sensitive: bool = True) -> LogEvent:
    """Analisa uma linha individual ou JSON estruturado."""
    raw = line.strip()
    msg = raw
    ts = None
    lvl = "INFO"
    svc = None
    req_id = None
    trc_id = None
    corr_id = None
    usr_id = None
    ord_id = None
    endpoint = None
    http_status = None
    stack = None

    if raw.startswith("{") and raw.endswith("}"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                msg = str(data.get("message") or data.get("msg") or data.get("log") or raw)
                ts = str(data.get("timestamp") or data.get("time") or data.get("@timestamp") or "") or None
                lvl = str(data.get("level") or data.get("severity") or "INFO").upper()
                svc = str(data.get("service") or data.get("app") or "") or None
                req_id = str(data.get("request_id") or data.get("requestId") or data.get("reqId") or "") or None
                trc_id = str(data.get("trace_id") or data.get("traceId") or "") or None
                corr_id = str(data.get("correlation_id") or data.get("correlationId") or "") or None
                usr_id = str(data.get("user_id") or data.get("userId") or "") or None
                ord_id = str(data.get("order_id") or data.get("orderId") or "") or None
                stack = data.get("stack") or data.get("stack_trace") or data.get("exception")
                if stack and isinstance(stack, (dict, list)):
                    stack = json.dumps(stack)
        except Exception:
            pass

    if not ts:
        m_ts = RE_TIMESTAMP.search(msg)
        if m_ts:
            ts = m_ts.group(0).strip("[]")

    m_lvl = RE_LEVEL.search(msg)
    if m_lvl:
        lvl = m_lvl.group("level").upper()
        if lvl == "WARNING":
            lvl = "WARN"

    if not req_id:
        m_req = RE_REQUEST_ID.search(msg)
        if m_req:
            req_id = m_req.group(1)

    if not trc_id:
        m_trc = RE_TRACE_ID.search(msg)
        if m_trc:
            trc_id = m_trc.group(1)

    if not corr_id:
        m_corr = RE_CORRELATION_ID.search(msg)
        if m_corr:
            corr_id = m_corr.group(1)

    if not usr_id:
        m_usr = RE_USER_ID.search(msg)
        if m_usr:
            usr_id = m_usr.group(1)

    if not ord_id:
        m_ord = RE_ORDER_ID.search(msg)
        if m_ord:
            ord_id = m_ord.group(1)

    if not svc:
        m_svc = RE_SERVICE.search(msg)
        if m_svc:
            svc = m_svc.group(1)

    m_http = RE_HTTP_STATUS.search(msg)
    if m_http:
        try:
            http_status = int(m_http.group("status"))
        except ValueError:
            pass

    m_meth = RE_HTTP_METHOD.search(msg)
    if m_meth:
        endpoint = f"{m_meth.group('method')} {m_meth.group('endpoint')}"

    is_err = lvl in {"ERROR", "FATAL", "CRITICAL", "EXCEPTION", "SEVERE"} or (http_status is not None and http_status >= 500)

    if mask_sensitive:
        msg = mask_sensitive_data(msg)
        raw = mask_sensitive_data(raw)
        if stack:
            stack = mask_sensitive_data(str(stack))

    template = normalize_template(msg)

    return LogEvent(
        line_number=line_number,
        raw_message=raw,
        message=msg,
        timestamp=ts,
        level=lvl,
        service=svc,
        request_id=req_id,
        trace_id=trc_id,
        correlation_id=corr_id,
        user_id=usr_id,
        order_id=ord_id,
        endpoint=endpoint,
        http_status=http_status,
        is_error=is_err,
        stack_trace=str(stack) if stack else None,
        template=template,
    )


def parse_log_content(content: str, mask_sensitive: bool = True) -> List[LogEvent]:
    """Processa texto simples, NDJSON ou lista JSON, agrupando stack traces multiline."""
    if not content or not content.strip():
        return []

    stripped = content.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            items = json.loads(stripped)
            if isinstance(items, list):
                events = []
                for i, item in enumerate(items, 1):
                    line_str = json.dumps(item) if isinstance(item, dict) else str(item)
                    events.append(parse_line_event(line_str, i, mask_sensitive))
                return events
        except Exception:
            pass

    lines = content.splitlines()
    events: List[LogEvent] = []
    current_event: Optional[LogEvent] = None
    stack_lines: List[str] = []

    for i, line in enumerate(lines, 1):
        line_strip = line.strip()
        if not line_strip:
            continue

        is_stack_line = (
            line.startswith(" ")
            or line.startswith("\t")
            or line_strip.startswith("at ")
            or line_strip.startswith("Caused by:")
            or line_strip.startswith("Traceback")
            or "Exception in" in line_strip
        )

        if is_stack_line and current_event:
            stack_lines.append(line_strip)
            continue

        if current_event:
            if stack_lines:
                current_event.stack_trace = "\n".join(stack_lines)
                stack_lines = []
            events.append(current_event)

        current_event = parse_line_event(line, i, mask_sensitive)

    if current_event:
        if stack_lines:
            current_event.stack_trace = "\n".join(stack_lines)
        events.append(current_event)

    return events


def optimize_logs(content: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executa a otimização, clusterização, geração de timeline e estatísticas."""
    options = options or {}
    levels_filter = set(l.upper() for l in options.get("levels", []))
    keywords = [k.lower() for k in options.get("keywords", [])]
    corr_ids = set(options.get("correlation_ids", []))
    samples_per_group = max(1, options.get("samples_per_group", 3))
    mask_sensitive = options.get("mask_sensitive_data", True)
    max_output_chars = options.get("max_output_chars", 500000)

    char_count_before = len(content)
    raw_lines = len(content.splitlines()) if content else 0

    all_events = parse_log_content(content, mask_sensitive)

    filtered_events: List[LogEvent] = []
    events_discarded = 0

    for ev in all_events:
        if levels_filter and ev.level not in levels_filter and not ev.is_error:
            events_discarded += 1
            continue

        if keywords and not any(k in ev.message.lower() for k in keywords):
            events_discarded += 1
            continue

        if corr_ids:
            found_id = (
                ev.correlation_id in corr_ids
                or ev.request_id in corr_ids
                or ev.trace_id in corr_ids
            )
            if not found_id and not ev.is_error:
                events_discarded += 1
                continue

        filtered_events.append(ev)

    clusters_map: Dict[str, Dict[str, Any]] = {}
    for ev in filtered_events:
        tmpl = ev.template or "EMPTY_EVENT"
        if tmpl not in clusters_map:
            clusters_map[tmpl] = {
                "cluster_id": f"cluster_{len(clusters_map) + 1}",
                "template": tmpl,
                "count": 0,
                "levels": set(),
                "services": set(),
                "correlation_ids": set(),
                "first_timestamp": ev.timestamp,
                "last_timestamp": ev.timestamp,
                "line_numbers": [],
                "samples": [],
                "is_error": ev.is_error,
            }

        cl = clusters_map[tmpl]
        cl["count"] += 1
        cl["levels"].add(ev.level)
        if ev.service:
            cl["services"].add(ev.service)
        if ev.correlation_id:
            cl["correlation_ids"].add(ev.correlation_id)
        if ev.request_id:
            cl["correlation_ids"].add(ev.request_id)
        if ev.timestamp:
            cl["last_timestamp"] = ev.timestamp
            if not cl["first_timestamp"]:
                cl["first_timestamp"] = ev.timestamp
        cl["line_numbers"].append(ev.line_number)
        if len(cl["samples"]) < samples_per_group:
            cl["samples"].append({
                "line": ev.line_number,
                "timestamp": ev.timestamp,
                "level": ev.level,
                "message": ev.message,
                "stack_trace": ev.stack_trace,
            })

    clusters_list = []
    for cl in sorted(clusters_map.values(), key=lambda x: x["count"], reverse=True):
        clusters_list.append({
            "cluster_id": cl["cluster_id"],
            "template": cl["template"],
            "count": cl["count"],
            "levels": sorted(list(cl["levels"])),
            "services": sorted(list(cl["services"])),
            "correlation_ids": sorted(list(cl["correlation_ids"])),
            "first_timestamp": cl["first_timestamp"],
            "last_timestamp": cl["last_timestamp"],
            "line_numbers_count": len(cl["line_numbers"]),
            "line_numbers_sample": cl["line_numbers"][:10],
            "samples": cl["samples"],
            "is_error": cl["is_error"],
        })

    timeline_list = []
    for ev in filtered_events:
        if ev.is_error or (ev.correlation_id and corr_ids and ev.correlation_id in corr_ids):
            timeline_list.append({
                "line": ev.line_number,
                "timestamp": ev.timestamp,
                "level": ev.level,
                "service": ev.service,
                "request_id": ev.request_id,
                "correlation_id": ev.correlation_id,
                "endpoint": ev.endpoint,
                "http_status": ev.http_status,
                "message": ev.message,
                "has_stack_trace": bool(ev.stack_trace),
            })

    counts_by_level = defaultdict(int)
    counts_by_service = defaultdict(int)
    counts_by_minute = defaultdict(int)

    for ev in filtered_events:
        counts_by_level[ev.level] += 1
        if ev.service:
            counts_by_service[ev.service] += 1
        if ev.timestamp and len(ev.timestamp) >= 16:
            counts_by_minute[ev.timestamp[:16]] += 1

    top_error_templates = [
        {"template": cl["template"], "count": cl["count"]}
        for cl in clusters_list if cl["is_error"]
    ][:5]

    result_payload = {
        "summary": {
            "total_lines": raw_lines,
            "total_events": len(all_events),
            "events_matched": len(filtered_events),
            "events_discarded": events_discarded,
            "unique_clusters": len(clusters_list),
            "errors_count": sum(1 for ev in filtered_events if ev.is_error),
        },
        "clusters": clusters_list,
        "timeline": timeline_list,
        "evidence": [cl["samples"][0] for cl in clusters_list if cl["is_error"] and cl["samples"]],
        "statistics": {
            "input_lines": raw_lines,
            "events_processed": len(filtered_events),
            "events_discarded": events_discarded,
            "clusters": len(clusters_list),
            "counts_by_level": dict(counts_by_level),
            "counts_by_service": dict(counts_by_service),
            "counts_by_minute": dict(counts_by_minute),
            "top_error_templates": top_error_templates,
            "characters_before": char_count_before,
            "characters_after": 0,
            "reduction_percent": 0.0,
        },
    }

    serialized = json.dumps(result_payload, ensure_ascii=False)
    char_count_after = len(serialized)
    reduction = round(max(0.0, (1.0 - (char_count_after / max(1, char_count_before)))) * 100, 2)
    result_payload["statistics"]["characters_after"] = char_count_after
    result_payload["statistics"]["reduction_percent"] = reduction

    if char_count_after > max_output_chars:
        result_payload["clusters"] = result_payload["clusters"][:20]
        result_payload["timeline"] = result_payload["timeline"][:50]
        result_payload["truncated"] = True
        result_payload["original_clusters_count"] = len(clusters_list)
        result_payload["original_timeline_count"] = len(timeline_list)

    return result_payload
