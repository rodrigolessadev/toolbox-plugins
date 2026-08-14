import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse, urlunparse

# Padroes Regex Globais
RE_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
)
RE_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
RE_BEARER = re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.\=]{15,}", re.IGNORECASE)
RE_AUTH_BASIC = re.compile(r"(Basic\s+)[a-zA-Z0-9+/=]{15,}", re.IGNORECASE)

# Chave=Valor ou Chave: Valor sensiveis em texto plano
RE_KEY_VALUE_SENSITIVE = re.compile(
    r"(?i)\b(password|senha|passwd|pwd|secret|client_secret|token|access_token|refresh_token|api_key|apikey)\s*([:=])\s*([^\s,;<>]+)"
)

# Connection Strings e URLs com credenciais
RE_CONN_STRING_SQL = re.compile(
    r"(?:Server|Data Source|Host)=[^;]+;(?:Database|Initial Catalog)=[^;]+;(?=.*(?:User|Password|Pwd)=)[^\r\n]+",
    re.IGNORECASE
)
RE_URL_CREDENTIALS = re.compile(
    r"(?:https?|mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis|amqp|oracle|jdbc:[a-zA-Z0-9]+)://([a-zA-Z0-9_.\-]+):([^@\s/]+)@([^\s]+)",
    re.IGNORECASE
)

# Documentos
RE_CPF_FORMATTED = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_CNPJ_FORMATTED = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_CREDIT_CARD = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")

# Contatos
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_PHONE = re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}[-.\s]?\d{4}\b")

# Chaves sensiveis em JSON / Query
SENSITIVE_FIELD_NAMES = {
    "password", "senha", "passwd", "pwd", "secret", "client_secret",
    "token", "access_token", "refresh_token", "api_key", "apikey", "key",
    "cpf", "cnpj", "credit_card", "card_number", "cvv", "cvc", "auth",
    "authorization", "cookie", "set-cookie"
}


def sanitize_text(text: str, options: Optional[Dict[str, Any]] = None, stats: Optional[Dict[str, int]] = None) -> str:
    """Sanitiza texto aplicando padroes de mascaramento configurados."""
    if not text:
        return text

    options = options or {}
    stats = stats if stats is not None else defaultdict(int)

    repl = options.get("replacement", "[REDACTED]")
    mask_email = options.get("mask_email", True)
    mask_phone = options.get("mask_phone", True)
    mask_docs = options.get("mask_documents", True)
    mask_headers = options.get("mask_headers", True)
    custom_patterns = options.get("custom_patterns", [])

    # 1. Chaves Privadas
    def _sub_pk(m):
        stats["private_key"] += 1
        return repl
    text = RE_PRIVATE_KEY.sub(_sub_pk, text)

    # 2. Connection Strings e URLs com credenciais
    def _sub_conn(m):
        stats["connection_string"] += 1
        return repl
    text = RE_CONN_STRING_SQL.sub(_sub_conn, text)

    def _sub_url_cred(m):
        stats["credentials_url"] += 1
        return f"{m.group(0).split('://')[0]}://[USER]:[PASSWORD]@{m.group(3)}"
    text = RE_URL_CREDENTIALS.sub(_sub_url_cred, text)

    # 3. JWTs
    def _sub_jwt(m):
        stats["jwt"] += 1
        return repl
    text = RE_JWT.sub(_sub_jwt, text)

    # 4. Headers de Autenticacao (Bearer / Basic)
    if mask_headers:
        def _sub_bearer(m):
            stats["bearer_token"] += 1
            return f"{m.group(1)}{repl}"
        text = RE_BEARER.sub(_sub_bearer, text)

        def _sub_basic(m):
            stats["basic_auth"] += 1
            return f"{m.group(1)}{repl}"
        text = RE_AUTH_BASIC.sub(_sub_basic, text)

    # 5. Pares Chave=Valor sensiveis (password=..., senha: ...)
    def _sub_kv(m):
        stats["sensitive_kv"] += 1
        sep = m.group(2)
        spacing = " " if sep == ":" else ""
        return f"{m.group(1)}{sep}{spacing}{repl}"
    text = RE_KEY_VALUE_SENSITIVE.sub(_sub_kv, text)

    # 6. Cartao de Credito
    def _sub_card(m):
        stats["credit_card"] += 1
        return repl
    text = RE_CREDIT_CARD.sub(_sub_card, text)

    # 7. Documentos (CPF / CNPJ)
    if mask_docs:
        def _sub_cpf(m):
            stats["cpf"] += 1
            return repl
        text = RE_CPF_FORMATTED.sub(_sub_cpf, text)

        def _sub_cnpj(m):
            stats["cnpj"] += 1
            return repl
        text = RE_CNPJ_FORMATTED.sub(_sub_cnpj, text)

    # 8. E-mail
    if mask_email:
        def _sub_email(m):
            stats["email"] += 1
            return repl
        text = RE_EMAIL.sub(_sub_email, text)

    # 9. Telefone
    if mask_phone:
        def _sub_phone(m):
            val = m.group(0).strip()
            digits = re.sub(r"\D", "", val)
            if len(digits) in (10, 11) and not val.startswith("19") and not val.startswith("20"):
                stats["phone"] += 1
                return repl
            return val
        text = RE_PHONE.sub(_sub_phone, text)

    # 10. Padroes Customizados
    for pat in custom_patterns:
        try:
            c_re = re.compile(pat)
            def _sub_custom(m):
                stats["custom_pattern"] += 1
                return repl
            text = c_re.sub(_sub_custom, text)
        except Exception:
            pass

    return text


def sanitize_json_data(data: Any, options: Optional[Dict[str, Any]] = None, stats: Optional[Dict[str, int]] = None) -> Any:
    """Sanitiza recursivamente estruturas de dados JSON mantendo tipos e chaves."""
    options = options or {}
    stats = stats if stats is not None else defaultdict(int)
    repl = options.get("replacement", "[REDACTED]")
    mask_fields = options.get("mask_json_fields", True)

    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if mask_fields and (k_lower in SENSITIVE_FIELD_NAMES or any(s in k_lower for s in ("password", "senha", "secret", "token", "cpf", "cnpj", "card", "cvv"))):
                stats["sensitive_json_field"] += 1
                new_dict[k] = repl
            else:
                new_dict[k] = sanitize_json_data(v, options, stats)
        return new_dict
    elif isinstance(data, list):
        return [sanitize_json_data(item, options, stats) for item in data]
    elif isinstance(data, str):
        return sanitize_text(data, options, stats)
    return data


def sanitize_har(har_dict: dict, options: Optional[Dict[str, Any]] = None, stats: Optional[Dict[str, int]] = None) -> dict:
    """Sanitiza estrutura HAR 1.2 com integridade de especificacao."""
    options = options or {}
    stats = stats if stats is not None else defaultdict(int)
    repl = options.get("replacement", "[REDACTED]")

    log = har_dict.get("log", {})
    entries = log.get("entries", [])

    for entry in entries:
        req = entry.get("request", {})
        res = entry.get("response", {})

        # 1. Sanitizar URL e Query
        url = req.get("url", "")
        if url:
            try:
                parsed = urlparse(url)
                if parsed.query:
                    qs = parse_qs(parsed.query, keep_blank_values=True)
                    new_qs = []
                    for k, vals in qs.items():
                        if k.lower() in SENSITIVE_FIELD_NAMES or any(s in k.lower() for s in ("token", "secret", "pass", "pwd", "auth", "key", "cpf")):
                            stats["sensitive_query_param"] += 1
                            new_qs.append(f"{k}={repl}")
                        else:
                            for v in vals:
                                new_qs.append(f"{k}={sanitize_text(v, options, stats)}")
                    new_query = "&".join(new_qs)
                    req["url"] = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                else:
                    req["url"] = sanitize_text(url, options, stats)
            except Exception:
                req["url"] = sanitize_text(url, options, stats)

        # 2. Sanitizar Headers
        for h in req.get("headers", []):
            name = str(h.get("name", "")).lower()
            if name in ("authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "apikey"):
                stats["sensitive_header"] += 1
                h["value"] = repl
            else:
                h["value"] = sanitize_text(str(h.get("value", "")), options, stats)

        for h in res.get("headers", []):
            name = str(h.get("name", "")).lower()
            if name in ("set-cookie", "authorization"):
                stats["sensitive_header"] += 1
                h["value"] = repl
            else:
                h["value"] = sanitize_text(str(h.get("value", "")), options, stats)

        # 3. Sanitizar PostData
        post_data = req.get("postData", {})
        post_text = post_data.get("text", "")
        if post_text:
            try:
                p_json = json.loads(post_text)
                post_data["text"] = json.dumps(sanitize_json_data(p_json, options, stats), ensure_ascii=False)
            except Exception:
                post_data["text"] = sanitize_text(post_text, options, stats)

        # 4. Sanitizar Response Content
        content = res.get("content", {})
        res_text = content.get("text", "")
        if res_text:
            try:
                r_json = json.loads(res_text)
                content["text"] = json.dumps(sanitize_json_data(r_json, options, stats), ensure_ascii=False)
            except Exception:
                content["text"] = sanitize_text(res_text, options, stats)

    return har_dict


def detect_format(content: str) -> str:
    """Detecta automaticamente se o conteudo e HAR, JSON, JSON Lines ou Texto."""
    stripped = content.strip()
    if not stripped:
        return "text"

    # HAR check
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "log" in data and isinstance(data["log"], dict) and "entries" in data["log"]:
                return "har"
            return "json"
        except Exception:
            pass

    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            json.loads(stripped)
            return "json"
        except Exception:
            pass

    # JSON Lines (NDJSON) check
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    if len(lines) > 1 and all(l.startswith("{") and l.endswith("}") for l in lines[:10]):
        try:
            json.loads(lines[0])
            json.loads(lines[1])
            return "json_lines"
        except Exception:
            pass

    return "text"


def sanitize_content(content: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Sanitiza o conteudo detectando o formato e contabilizando metricas."""
    options = options or {}
    stats: Dict[str, int] = defaultdict(int)
    char_before = len(content)

    fmt = detect_format(content)

    if fmt == "har":
        try:
            har_obj = json.loads(content)
            sanitized_har = sanitize_har(har_obj, options, stats)
            output_str = json.dumps(sanitized_har, indent=2, ensure_ascii=False)
        except Exception:
            output_str = sanitize_text(content, options, stats)
    elif fmt == "json":
        try:
            json_obj = json.loads(content)
            sanitized_json = sanitize_json_data(json_obj, options, stats)
            output_str = json.dumps(sanitized_json, indent=2, ensure_ascii=False)
        except Exception:
            output_str = sanitize_text(content, options, stats)
    elif fmt == "json_lines":
        out_lines = []
        for line in content.splitlines():
            line_strip = line.strip()
            if not line_strip:
                out_lines.append(line)
                continue
            try:
                item_obj = json.loads(line_strip)
                sanitized_item = sanitize_json_data(item_obj, options, stats)
                out_lines.append(json.dumps(sanitized_item, ensure_ascii=False))
            except Exception:
                out_lines.append(sanitize_text(line, options, stats))
        output_str = "\n".join(out_lines)
    else:
        output_str = sanitize_text(content, options, stats)

    char_after = len(output_str)
    was_modified = output_str != content
    total_subs = sum(stats.values())

    return {
        "detected_format": fmt,
        "substitutions_by_type": dict(stats),
        "total_substitutions": total_subs,
        "characters_before": char_before,
        "characters_after": char_after,
        "was_modified": was_modified,
        "dry_run": bool(options.get("dry_run", False)),
        "sanitized_content": output_str
    }
