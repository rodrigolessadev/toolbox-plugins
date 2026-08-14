import datetime
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, urlparse

DEFAULT_FAILURE_STATUSES = {400, 401, 403, 404, 408, 409, 429, 500, 502, 503, 504}
DEFAULT_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_CORRELATION_FIELDS = [
    "request_id", "requestId", "trace_id", "traceId", "span_id", "spanId",
    "correlation_id", "correlationId", "order_id", "orderId", "transaction_id", "transactionId"
]

DEFAULT_FIELD_MAPPING = {
    "timestamp": ["@timestamp", "timestamp", "event.created"],
    "service": ["service.name", "service", "app"],
    "request_id": ["request.id", "request_id", "requestId"],
    "trace_id": ["trace.id", "trace_id", "traceId"],
    "span_id": ["span.id", "span_id", "spanId"],
    "correlation_id": ["correlation.id", "correlation_id", "correlationId"],
    "http_method": ["http.request.method", "method"],
    "http_status": ["http.response.status_code", "status_code", "status"],
    "url_path": ["url.path", "http.request.path", "path"]
}

RE_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


def parse_iso_datetime(dt_str: str) -> Optional[datetime.datetime]:
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(clean)
    except Exception:
        return None


def format_iso(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def normalize_field_name(k: str) -> str:
    cleaned = str(k).lower().replace("-", "_").replace(".", "_")
    if cleaned.startswith("x_"):
        cleaned = cleaned[2:]
    return cleaned


def extract_identifiers_from_dict(data: Any, target_fields: Set[str], found: Dict[str, Set[str]]) -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            k_norm = normalize_field_name(k)
            for target in target_fields:
                if k_norm == normalize_field_name(target):
                    if isinstance(v, (str, int, float)) and str(v).strip():
                        found[target].add(str(v).strip())
            extract_identifiers_from_dict(v, target_fields, found)
    elif isinstance(data, list):
        for item in data:
            extract_identifiers_from_dict(item, target_fields, found)


def extract_identifiers_from_text(text: str, target_fields: Set[str], found: Dict[str, Set[str]]) -> None:
    if not text:
        return
    try:
        parsed = json.loads(text)
        extract_identifiers_from_dict(parsed, target_fields, found)
        return
    except Exception:
        pass

    for target in target_fields:
        pat = re.compile(r"(?i)\b" + re.escape(target) + r"\b\s*[:=]\s*['\"]?([a-zA-Z0-9_-]{6,64})")
        for m in pat.finditer(text):
            val = m.group(1).strip(" '\"")
            found[target].add(val)


def sanitize_header_value(name: str, value: str) -> str:
    name_lower = name.lower()
    if name_lower in ("authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "apikey", "token"):
        return "[REDACTED]"
    if RE_JWT.search(value):
        return RE_JWT.sub("[REDACTED]", value)
    return value


def plan_har_kibana_queries(raw_content: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    clock_skew_ms = int(options.get("clock_skew_ms", 5000))
    context_before_ms = int(options.get("context_before_ms", 10000))
    context_after_ms = int(options.get("context_after_ms", 10000))
    slow_threshold_ms = int(options.get("slow_threshold_ms", 1000))
    failure_statuses = set(options.get("failure_statuses", DEFAULT_FAILURE_STATUSES))
    state_changing_methods = set(options.get("state_changing_methods", DEFAULT_STATE_CHANGING_METHODS))
    correlation_fields = set(options.get("correlation_fields", DEFAULT_CORRELATION_FIELDS))
    field_mapping = options.get("field_mapping", DEFAULT_FIELD_MAPPING)
    max_queries = int(options.get("max_queries", 50))
    generate_kql = bool(options.get("generate_kql", True))
    generate_query_dsl = bool(options.get("generate_query_dsl", True))

    warnings: List[str] = []

    try:
        har_json = json.loads(raw_content)
    except Exception as e:
        raise ValueError(f"HAR invalido: JSON malformado ({e})")

    if not isinstance(har_json, dict) or "log" not in har_json or not isinstance(har_json["log"], dict):
        raise ValueError("HAR invalido: Estrutura raiz 'log' ausente.")

    entries = har_json["log"].get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("HAR invalido: 'entries' nao e uma lista.")

    total_entries = len(entries)
    if total_entries == 0:
        warnings.append("HAR vazio: Nenhuma entrada encontrada no log.")

    parsed_requests = []
    global_identifiers: Dict[str, Set[str]] = defaultdict(set)
    hosts_set: Set[str] = set()
    paths_set: Set[str] = set()
    services_set: Set[str] = set()
    errors_list: List[Dict[str, Any]] = []

    min_start_dt: Optional[datetime.datetime] = None
    max_end_dt: Optional[datetime.datetime] = None

    api_count = 0
    failed_count = 0
    slow_count = 0
    redirect_count = 0
    retry_count = 0

    seen_endpoints: Dict[Tuple[str, str], int] = defaultdict(int)

    for idx, entry in enumerate(entries, start=1):
        req = entry.get("request", {})
        resp = entry.get("response", {})
        time_ms = float(entry.get("time", 0.0))

        started_str = entry.get("startedDateTime", "")
        dt_start = parse_iso_datetime(started_str)
        if dt_start:
            dt_end = dt_start + datetime.timedelta(milliseconds=time_ms)
            if min_start_dt is None or dt_start < min_start_dt:
                min_start_dt = dt_start
            if max_end_dt is None or dt_end > max_end_dt:
                max_end_dt = dt_end
        else:
            dt_end = None

        url = req.get("url", "")
        method = req.get("method", "GET").upper()
        status = int(resp.get("status", 0))

        parsed_url = urlparse(url)
        host = parsed_url.netloc
        path = parsed_url.path or "/"
        if host:
            hosts_set.add(host)
        if path:
            paths_set.add(path)

        is_failed = status in failure_statuses or status >= 400
        is_slow = time_ms >= slow_threshold_ms
        is_redirect = 300 <= status < 400
        is_state_change = method in state_changing_methods
        is_api = "/api/" in path or "json" in str(resp.get("content", {}).get("mimeType", "")).lower()

        endpoint_key = (method, path)
        seen_endpoints[endpoint_key] += 1
        is_retry = seen_endpoints[endpoint_key] > 1 and is_failed

        if is_api:
            api_count += 1
        if is_failed:
            failed_count += 1
        if is_slow:
            slow_count += 1
        if is_redirect:
            redirect_count += 1
        if is_retry:
            retry_count += 1

        req_identifiers: Dict[str, Set[str]] = defaultdict(set)
        sanitized_headers = []
        for h in req.get("headers", []):
            h_name = str(h.get("name", ""))
            h_val = str(h.get("value", ""))
            san_val = sanitize_header_value(h_name, h_val)
            sanitized_headers.append({"name": h_name, "value": san_val})
            h_norm = normalize_field_name(h_name)
            for target in correlation_fields:
                if h_norm == normalize_field_name(target):
                    if h_val and h_val != "[REDACTED]":
                        req_identifiers[target].add(h_val)
                        global_identifiers[target].add(h_val)

        for h in resp.get("headers", []):
            h_name = str(h.get("name", ""))
            h_val = str(h.get("value", ""))
            h_norm = normalize_field_name(h_name)
            for target in correlation_fields:
                if h_norm == normalize_field_name(target):
                    if h_val and h_val != "[REDACTED]":
                        req_identifiers[target].add(h_val)
                        global_identifiers[target].add(h_val)

        if parsed_url.query:
            qs = parse_qs(parsed_url.query)
            for qk, qvals in qs.items():
                qk_norm = normalize_field_name(qk)
                for target in correlation_fields:
                    if qk_norm == normalize_field_name(target):
                        for val in qvals:
                            if val:
                                req_identifiers[target].add(val)
                                global_identifiers[target].add(val)

        post_text = req.get("postData", {}).get("text", "")
        if post_text:
            extract_identifiers_from_text(post_text, correlation_fields, req_identifiers)
            extract_identifiers_from_text(post_text, correlation_fields, global_identifiers)

        resp_text = resp.get("content", {}).get("text", "")
        if resp_text:
            extract_identifiers_from_text(resp_text, correlation_fields, req_identifiers)
            extract_identifiers_from_text(resp_text, correlation_fields, global_identifiers)

        time_window = {}
        if dt_start and dt_end:
            adj_start = dt_start - datetime.timedelta(milliseconds=(clock_skew_ms + context_before_ms))
            adj_end = dt_end + datetime.timedelta(milliseconds=(clock_skew_ms + context_after_ms))
            time_window = {
                "from": format_iso(adj_start),
                "to": format_iso(adj_end),
                "original_start": format_iso(dt_start),
                "original_end": format_iso(dt_end)
            }

        req_summary = {
            "entry_index": idx,
            "method": method,
            "url": url,
            "host": host,
            "path": path,
            "status": status,
            "duration_ms": time_ms,
            "time_window": time_window,
            "is_failed": is_failed,
            "is_slow": is_slow,
            "is_retry": is_retry,
            "identifiers": {k: sorted(list(v)) for k, v in req_identifiers.items()}
        }
        parsed_requests.append(req_summary)

        if is_failed:
            errors_list.append({
                "entry_index": idx,
                "status": status,
                "method": method,
                "url": url,
                "time_window": time_window
            })

    session_time_range = {}
    if min_start_dt and max_end_dt:
        sess_from = min_start_dt - datetime.timedelta(milliseconds=(clock_skew_ms + context_before_ms))
        sess_to = max_end_dt + datetime.timedelta(milliseconds=(clock_skew_ms + context_after_ms))
        session_time_range = {
            "from": format_iso(sess_from),
            "to": format_iso(sess_to)
        }

    query_plan = []
    dedup_set: Set[str] = set()

    def _add_query(priority: int, strategy: str, reason: str, ids: List[str], time_range: Dict[str, Any], field_key: str, exact: bool, risk: str) -> None:
        if len(query_plan) >= max_queries:
            return
        fields = field_mapping.get(field_key, [field_key])
        primary_field = fields[0] if fields else field_key

        kql_str = ""
        if generate_kql and ids:
            if len(ids) == 1:
                kql_str = f'{primary_field} : "{ids[0]}"'
            else:
                joined = " or ".join(f'{primary_field} : "{i}"' for i in ids[:10])
                kql_str = f"({joined})"

        dsl: Dict[str, Any] = {"bool": {"must": []}}
        if generate_query_dsl:
            if ids:
                if len(ids) == 1:
                    dsl["bool"]["must"].append({"term": {f"{primary_field}.keyword": ids[0]}})
                else:
                    dsl["bool"]["must"].append({"terms": {f"{primary_field}.keyword": ids}})
            if time_range and "from" in time_range and "to" in time_range:
                ts_field = field_mapping.get("timestamp", ["@timestamp"])[0]
                dsl["bool"]["must"].append({
                    "range": {
                        ts_field: {
                            "gte": time_range["from"],
                            "lte": time_range["to"],
                            "format": "strict_date_optional_time"
                        }
                    }
                })

        dedup_key = f"{strategy}:{primary_field}:{sorted(ids)}:{time_range.get('from')}:{time_range.get('to')}"
        if dedup_key in dedup_set:
            return
        dedup_set.add(dedup_key)

        query_plan.append({
            "priority": priority,
            "strategy": strategy,
            "reason": reason,
            "identifiers": ids,
            "time_range": time_range,
            "kql": kql_str,
            "query_dsl": dsl,
            "suggested_fields": fields,
            "limit": 100,
            "is_exact": exact,
            "false_positive_risks": risk
        })

    trace_ids = sorted(list(global_identifiers.get("trace_id", set()) | global_identifiers.get("traceId", set())))
    if trace_ids:
        _add_query(1, "trace_id", "Trace ID extraido para correlacao distribuida exata", trace_ids, session_time_range, "trace_id", True, "Baixo")

    req_ids = sorted(list(global_identifiers.get("request_id", set()) | global_identifiers.get("requestId", set())))
    if req_ids:
        _add_query(2, "request_id", "Request ID encontrado em headers ou rotas", req_ids, session_time_range, "request_id", True, "Baixo")

    corr_ids = sorted(list(global_identifiers.get("correlation_id", set()) | global_identifiers.get("correlationId", set())))
    if corr_ids:
        _add_query(3, "correlation_id", "Correlation ID encontrado para correlacao de fluxo", corr_ids, session_time_range, "correlation_id", True, "Baixo")

    order_ids = sorted(list(global_identifiers.get("order_id", set()) | global_identifiers.get("orderId", set())))
    if order_ids:
        _add_query(4, "order_id", "Identificador de pedido/transacao encontrado", order_ids, session_time_range, "order_id", True, "Baixo")

    for err in errors_list[:10]:
        err_path = urlparse(err["url"]).path
        q_dsl = {
            "bool": {
                "must": [
                    {"term": {field_mapping.get("http_status", ["http.response.status_code"])[0]: err["status"]}},
                    {"term": {f"{field_mapping.get('url_path', ['url.path'])[0]}.keyword": err_path}}
                ]
            }
        }
        kql_err = f'{field_mapping.get("http_status", ["status"])[0]} : {err["status"]} and {field_mapping.get("url_path", ["path"])[0]} : "{err_path}"'
        dedup_k = f"failure:{err['status']}:{err_path}"
        if dedup_k not in dedup_set and len(query_plan) < max_queries:
            dedup_set.add(dedup_k)
            query_plan.append({
                "priority": 5,
                "strategy": "failure_endpoint",
                "reason": f"Investigacao de erro HTTP {err['status']} no endpoint {err_path}",
                "identifiers": [str(err["status"])],
                "time_range": err["time_window"],
                "kql": kql_err,
                "query_dsl": q_dsl,
                "suggested_fields": field_mapping.get("http_status", []) + field_mapping.get("url_path", []),
                "limit": 50,
                "is_exact": False,
                "false_positive_risks": "Medio (pode retornar chamadas de outros usuarios se o volume for alto)"
            })

    if not trace_ids and not req_ids and not corr_ids and not errors_list and session_time_range:
        warnings.append("Ausencia de identificadores unicos confiaveis no HAR: Plano gerado com base em rotas e janela temporal.")
        _add_query(7, "time_range_only", "Janela temporal da sessao do usuario", [], session_time_range, "timestamp", False, "Alto (requer filtragem adicional por usuario ou IP)")

    return {
        "har_summary": {
            "total_entries": total_entries,
            "api_entries": api_count,
            "failed_entries": failed_count,
            "slow_entries": slow_count,
            "redirect_entries": redirect_count,
            "retry_entries": retry_count,
            "time_range": session_time_range
        },
        "signals": {
            "identifiers": {k: sorted(list(v)) for k, v in global_identifiers.items()},
            "hosts": sorted(list(hosts_set)),
            "paths": sorted(list(paths_set))[:50],
            "services": sorted(list(services_set)),
            "errors": errors_list[:20],
            "time_ranges": [session_time_range] if session_time_range else []
        },
        "query_plan": query_plan,
        "requests": parsed_requests[:50],
        "warnings": warnings,
        "truncated": total_entries > 50
    }
