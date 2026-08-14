import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse, urlunparse

# Padrões de Mascaramento
RE_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
RE_BEARER = re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.\=]{15,}", re.IGNORECASE)
RE_AUTH_BASIC = re.compile(r"(Basic\s+)[a-zA-Z0-9+/=]{15,}", re.IGNORECASE)
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|(?<!\d)\d{11}(?!\d)")
RE_CREDIT_CARD = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Padrões de Normalização de URLs para Clusters
RE_NORM_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
RE_NORM_NUM = re.compile(r"(?<![a-zA-Z0-9])\d+(?![a-zA-Z0-9])")

SENSITIVE_PARAM_NAMES = {
    "token", "secret", "key", "apikey", "api_key", "password", "passwd", "pwd",
    "senha", "auth", "access_token", "refresh_token", "cpf", "card", "cvv"
}


def mask_sensitive_text(text: str) -> str:
    """Aplica regras de mascaramento em texto livre."""
    if not text:
        return text
    text = RE_JWT.sub("[JWT_MASKED]", text)
    text = RE_BEARER.sub(r"\1[MASKED]", text)
    text = RE_AUTH_BASIC.sub(r"\1[MASKED]", text)
    text = RE_CREDIT_CARD.sub("[CARD_MASKED]", text)
    text = RE_CPF.sub("[CPF_MASKED]", text)
    return text


def mask_url_and_params(url_str: str) -> str:
    """Mascara query parameters sensíveis mantendo a estrutura da URL."""
    try:
        parsed = urlparse(url_str)
        if not parsed.query:
            return url_str
        qs = parse_qs(parsed.query, keep_blank_values=True)
        new_qs = []
        for k, vals in qs.items():
            if k.lower() in SENSITIVE_PARAM_NAMES or any(s in k.lower() for s in ("token", "secret", "pass", "pwd", "auth", "key", "cpf")):
                new_qs.append(f"{k}=[MASKED]")
            else:
                for v in vals:
                    masked_v = mask_sensitive_text(v)
                    new_qs.append(f"{k}={masked_v}")
        new_query = "&".join(new_qs)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        return url_str


def mask_headers(headers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mascara cabeçalhos HTTP sensíveis."""
    masked_list = []
    for h in headers:
        name = str(h.get("name", ""))
        value = str(h.get("value", ""))
        lower_name = name.lower()

        if lower_name in ("authorization", "proxy-authorization"):
            value = mask_sensitive_text(value) if "bearer" in value.lower() or "basic" in value.lower() else "[AUTH_MASKED]"
        elif lower_name in ("cookie", "set-cookie"):
            value = "[COOKIE_MASKED]"
        elif lower_name in ("x-api-key", "apikey", "secret-key", "token", "x-auth-token"):
            value = "[KEY_MASKED]"
        else:
            value = mask_sensitive_text(value)

        masked_list.append({"name": name, "value": value})
    return masked_list


def mask_json_body(data: Any) -> Any:
    """Mascara recursivamente campos sensíveis em estruturas JSON."""
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "senha", "pwd", "secret", "token", "cpf", "card", "cvv", "key", "jwt")):
                new_dict[k] = "[MASKED]"
            else:
                new_dict[k] = mask_json_body(v)
        return new_dict
    elif isinstance(data, list):
        return [mask_json_body(item) for item in data]
    elif isinstance(data, str):
        return mask_sensitive_text(data)
    return data


def classify_resource(url_str: str, mime_type: str, method: str, status: int) -> str:
    """Classifica a requisição HTTP em categorias padronizadas."""
    mime = (mime_type or "").lower()
    parsed = urlparse(url_str)
    path = parsed.path.lower()

    if "image/" in mime or any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")):
        return "Image"
    if "font" in mime or any(path.endswith(ext) for ext in (".woff", ".woff2", ".ttf", ".eot", ".otf")):
        return "Font"
    if "javascript" in mime or path.endswith(".js") or path.endswith(".mjs"):
        return "JavaScript"
    if "text/css" in mime or path.endswith(".css"):
        return "CSS"
    if "text/html" in mime or path.endswith(".html") or path.endswith(".htm"):
        return "Document"
    if status == 101 or "websocket" in mime:
        return "WebSocket"
    if "application/json" in mime or "application/xml" in mime or method in ("POST", "PUT", "PATCH", "DELETE") or "/api/" in path or "/graphql" in path:
        return "API"
    return "Unknown"


def normalize_path_template(path: str) -> str:
    """Normaliza o path substituindo IDs e UUIDs para agrupamento."""
    p = RE_NORM_UUID.sub("<UUID>", path)
    p = RE_NORM_NUM.sub("<NUM>", p)
    return p


@dataclass
class HttpEvidence:
    index: int
    started_date_time: str
    method: str
    url: str
    host: str
    path: str
    status: int
    status_text: str
    duration_ms: float
    resource_type: str
    is_failure: bool
    is_slow: bool
    is_redirect: bool
    is_retry: bool = False
    dns_time: float = 0.0
    connect_time: float = 0.0
    ssl_time: float = 0.0
    send_time: float = 0.0
    wait_time: float = 0.0
    receive_time: float = 0.0
    request_headers: List[Dict[str, Any]] = field(default_factory=list)
    response_headers: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    request_size: int = 0
    response_size: int = 0
    error_summary: Optional[str] = None


def optimize_har(content: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Processa um arquivo HAR 1.2 e gera o resumo de otimização e evidências."""
    options = options or {}
    slow_threshold_ms = options.get("slow_threshold_ms", 1000)
    failure_statuses = set(options.get("failure_statuses", [400, 401, 403, 404, 408, 409, 422, 429, 500, 502, 503, 504]))
    context_before = options.get("context_before", 5)
    context_after = options.get("context_after", 5)
    preserve_static = options.get("preserve_static_resources", False)
    preserve_api = options.get("preserve_api_requests", True)
    include_req_body = options.get("include_request_body", True)
    include_res_body = options.get("include_response_body", True)
    max_body_chars = options.get("max_body_chars", 3000)
    mask_sensitive = options.get("mask_sensitive_data", True)
    keywords = [k.lower() for k in options.get("keywords", [])]
    corr_ids = [c.lower() for c in options.get("correlation_ids", [])]

    if not content or not content.strip():
        return {
            "summary": {
                "total_requests": 0,
                "api_requests": 0,
                "static_requests": 0,
                "failed_requests": 0,
                "slow_requests": 0,
                "redirects": 0,
                "retries": 0
            },
            "failures": [],
            "slow_requests": [],
            "sequence": [],
            "clusters": [],
            "contexts": [],
            "evidence": [],
            "warnings": ["Conteúdo HAR vazio."]
        }

    try:
        data = json.loads(content)
    except Exception as e:
        raise ValueError(f"HAR JSON inválido: {e}")

    log = data.get("log")
    if not isinstance(log, dict):
        raise ValueError("Estrutura HAR inválida: elemento 'log' ausente ou inválido.")

    raw_entries = log.get("entries", [])
    if not isinstance(raw_entries, list):
        raw_entries = []

    evidences: List[HttpEvidence] = []
    endpoint_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    total_requests = len(raw_entries)
    api_requests = 0
    static_requests = 0
    failed_requests = 0
    slow_requests = 0
    redirects = 0
    retries = 0

    for idx, entry in enumerate(raw_entries):
        req = entry.get("request", {})
        res = entry.get("response", {})
        timings = entry.get("timings", {})

        url_raw = req.get("url", "")
        method = req.get("method", "GET").upper()
        status = res.get("status", 0)
        status_text = res.get("statusText", "")
        time_ms = float(entry.get("time", 0.0))
        started = entry.get("startedDateTime", "")

        parsed_url = urlparse(url_raw)
        host = parsed_url.netloc
        path = parsed_url.path or "/"

        content_obj = res.get("content", {})
        mime_type = content_obj.get("mimeType", "")

        res_type = classify_resource(url_raw, mime_type, method, status)
        is_static = res_type in ("Image", "Font", "JavaScript", "CSS")
        if is_static:
            static_requests += 1
        elif res_type == "API":
            api_requests += 1

        is_fail = status in failure_statuses or status >= 400
        is_slow = time_ms >= slow_threshold_ms
        is_redir = 300 <= status < 400 or bool(res.get("redirectURL"))

        if is_fail:
            failed_requests += 1
        if is_slow:
            slow_requests += 1
        if is_redir:
            redirects += 1

        call_sig = f"{method}:{host}:{path}"
        is_retry = any(prev.get("is_fail") or prev.get("status") == 0 for prev in endpoint_history[call_sig])
        if is_retry:
            retries += 1
        endpoint_history[call_sig].append({"index": idx, "is_fail": is_fail, "status": status})

        req_headers = req.get("headers", [])
        res_headers = res.get("headers", [])

        req_body_str = None
        if include_req_body:
            post_data = req.get("postData", {})
            text_data = post_data.get("text", "")
            if text_data:
                if mask_sensitive:
                    try:
                        parsed_json = json.loads(text_data)
                        req_body_str = json.dumps(mask_json_body(parsed_json), ensure_ascii=False)
                    except Exception:
                        req_body_str = mask_sensitive_text(text_data)
                else:
                    req_body_str = text_data
                if len(req_body_str) > max_body_chars:
                    req_body_str = req_body_str[:max_body_chars] + "... [TRUNCATED]"

        res_body_str = None
        if include_res_body and not is_static:
            raw_res_text = content_obj.get("text", "")
            encoding = content_obj.get("encoding", "")
            if encoding == "base64":
                res_body_str = f"[BASE64_PAYLOAD ({len(raw_res_text)} chars)]"
            elif raw_res_text:
                if mask_sensitive:
                    try:
                        parsed_json = json.loads(raw_res_text)
                        res_body_str = json.dumps(mask_json_body(parsed_json), ensure_ascii=False)
                    except Exception:
                        res_body_str = mask_sensitive_text(raw_res_text)
                else:
                    res_body_str = raw_res_text
                if len(res_body_str) > max_body_chars:
                    res_body_str = res_body_str[:max_body_chars] + "... [TRUNCATED]"

        url_final = mask_url_and_params(url_raw) if mask_sensitive else url_raw
        if mask_sensitive:
            req_headers = mask_headers(req_headers)
            res_headers = mask_headers(res_headers)

        ev = HttpEvidence(
            index=idx,
            started_date_time=started,
            method=method,
            url=url_final,
            host=host,
            path=path,
            status=status,
            status_text=status_text,
            duration_ms=time_ms,
            resource_type=res_type,
            is_failure=is_fail,
            is_slow=is_slow,
            is_redirect=is_redir,
            is_retry=is_retry,
            dns_time=float(timings.get("dns", 0.0) or 0.0),
            connect_time=float(timings.get("connect", 0.0) or 0.0),
            ssl_time=float(timings.get("ssl", 0.0) or 0.0),
            send_time=float(timings.get("send", 0.0) or 0.0),
            wait_time=float(timings.get("wait", 0.0) or 0.0),
            receive_time=float(timings.get("receive", 0.0) or 0.0),
            request_headers=req_headers,
            response_headers=res_headers,
            request_body=req_body_str,
            response_body=res_body_str,
            request_size=int(req.get("headersSize", 0) + (req.get("bodySize", 0) if req.get("bodySize", 0) > 0 else 0)),
            response_size=int(res.get("headersSize", 0) + (res.get("bodySize", 0) if res.get("bodySize", 0) > 0 else 0)),
        )
        evidences.append(ev)

    # 1. Sequência compacta de navegação
    sequence = [
        f"{ev.method} {ev.path} {ev.status} {round(ev.duration_ms)}ms ({ev.resource_type})"
        for ev in evidences
        if preserve_static or ev.resource_type not in ("Image", "Font")
    ]

    # 2. Lista de Falhas
    failures_list = [
        {
            "index": ev.index,
            "started": ev.started_date_time,
            "method": ev.method,
            "url": ev.url,
            "status": ev.status,
            "status_text": ev.status_text,
            "duration_ms": ev.duration_ms,
            "resource_type": ev.resource_type,
            "request_headers": ev.request_headers,
            "response_headers": ev.response_headers,
            "request_body": ev.request_body,
            "response_body": ev.response_body,
        }
        for ev in evidences if ev.is_failure
    ]

    # 3. Lista de Requests Lentos
    slow_list = [
        {
            "index": ev.index,
            "method": ev.method,
            "url": ev.url,
            "status": ev.status,
            "duration_ms": ev.duration_ms,
            "timings": {
                "dns": ev.dns_time,
                "connect": ev.connect_time,
                "wait_ttfb": ev.wait_time,
                "receive": ev.receive_time
            }
        }
        for ev in evidences if ev.is_slow and not ev.is_failure
    ]

    # 4. Janelas de Contexto ao redor de Falhas
    contexts = []
    failure_indices = [ev.index for ev in evidences if ev.is_failure]
    for f_idx in failure_indices:
        start_idx = max(0, f_idx - context_before)
        end_idx = min(len(evidences), f_idx + context_after + 1)
        contexts.append({
            "failure_index": f_idx,
            "window": [
                {
                    "index": e.index,
                    "method": e.method,
                    "path": e.path,
                    "status": e.status,
                    "duration_ms": e.duration_ms,
                    "is_target": e.index == f_idx,
                }
                for e in evidences[start_idx:end_idx]
            ]
        })

    # 5. Agrupamentos / Clusters de chamadas repetidas
    clusters_map: Dict[str, Dict[str, Any]] = {}
    for ev in evidences:
        tmpl_path = normalize_path_template(ev.path)
        sig = f"{ev.method} {ev.host}{tmpl_path} [{ev.status}]"
        if sig not in clusters_map:
            clusters_map[sig] = {
                "signature": sig,
                "method": ev.method,
                "host": ev.host,
                "path_template": tmpl_path,
                "status": ev.status,
                "count": 0,
                "durations": [],
                "first_occurrence": ev.started_date_time,
                "last_occurrence": ev.started_date_time,
            }
        cl = clusters_map[sig]
        cl["count"] += 1
        cl["durations"].append(ev.duration_ms)
        cl["last_occurrence"] = ev.started_date_time

    clusters_list = []
    for cl in sorted(clusters_map.values(), key=lambda x: x["count"], reverse=True):
        avg_dur = round(sum(cl["durations"]) / max(1, len(cl["durations"])), 1)
        clusters_list.append({
            "signature": cl["signature"],
            "method": cl["method"],
            "host": cl["host"],
            "path_template": cl["path_template"],
            "status": cl["status"],
            "count": cl["count"],
            "avg_duration_ms": avg_dur,
            "first_occurrence": cl["first_occurrence"],
            "last_occurrence": cl["last_occurrence"],
        })

    # 6. Evidências detalhadas (Preserva todas as chamadas não-estáticas ou com headers/cookies)
    evidence_list = []
    for ev in evidences:
        has_headers = any(h.get("value") in ("[COOKIE_MASKED]", "[KEY_MASKED]") or "bearer" in str(h.get("value", "")).lower() for h in ev.request_headers + ev.response_headers)
        if ev.is_failure or ev.is_slow or ev.is_redirect or (preserve_api and ev.resource_type in ("API", "Document")) or has_headers or ev.method in ("POST", "PUT", "PATCH", "DELETE"):
            evidence_list.append({
                "index": ev.index,
                "started": ev.started_date_time,
                "method": ev.method,
                "url": ev.url,
                "status": ev.status,
                "duration_ms": ev.duration_ms,
                "resource_type": ev.resource_type,
                "request_headers": ev.request_headers,
                "response_headers": ev.response_headers,
                "request_body": ev.request_body,
                "response_body": ev.response_body,
            })

    return {
        "summary": {
            "total_requests": total_requests,
            "api_requests": api_requests,
            "static_requests": static_requests,
            "failed_requests": failed_requests,
            "slow_requests": slow_requests,
            "redirects": redirects,
            "retries": retries,
        },
        "failures": failures_list,
        "slow_requests": slow_list,
        "sequence": sequence,
        "clusters": clusters_list,
        "contexts": contexts,
        "evidence": evidence_list,
        "warnings": [],
    }
