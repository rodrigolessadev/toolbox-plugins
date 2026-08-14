import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "dist", "build", "target",
    "__pycache__", ".pytest_cache", ".idea", ".vscode", "temp_cache"
}

RE_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
RE_BEARER = re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9._~+/-]+=*")
RE_PRIVATE_KEY = re.compile(r"-----BEGIN[ A-Z0-9_-]+PRIVATE KEY-----[\s\S]*?-----END[ A-Z0-9_-]+PRIVATE KEY-----")
RE_PASSWORD_ASSIGN = re.compile(r"(?i)(password|secret|apikey|api_key|token|auth_token)\s*[:=]\s*['\"][^'\"]+['\"]")

# Padroes para tipos de simbolos
PATTERN_FUNCTION = re.compile(r"(?i)^\s*(?:async\s+)?(?:def|function|fn|public\s+(?:static\s+)?[\w<>\[\]]+\s+|private\s+[\w<>\[\]]+\s+|func)\s+([a-zA-Z0-9_]+)")
PATTERN_CLASS = re.compile(r"(?i)^\s*(?:public\s+|export\s+)?(?:class|struct|interface|trait|enum)\s+([a-zA-Z0-9_]+)")
PATTERN_ROUTE = re.compile(r"(?i)(?:@(?:app|router|api)\.(?:get|post|put|delete|patch)|Route\(['\"]|app\.use\(['\"])")
PATTERN_EXCEPTION = re.compile(r"(?i)(?:raise|throw|except|catch)\s+([a-zA-Z0-9_]+Exception|[a-zA-Z0-9_]+Error)")


def is_binary_buffer(buf: bytes) -> bool:
    return b"\x00" in buf


def mask_secrets(text: str) -> str:
    if not text:
        return text
    t = RE_PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)
    t = RE_JWT.sub("[REDACTED_JWT]", t)
    t = RE_BEARER.sub("Bearer [REDACTED]", t)
    t = RE_PASSWORD_ASSIGN.sub(r"\1: '[REDACTED]'", t)
    return t


def calculate_file_hash(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()


def extract_sources(options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    proj_dir_str = options.get("project_path") or options.get("directory") or "."
    terms = options.get("terms") or []
    if isinstance(terms, str):
        terms = [terms]
    search_type = str(options.get("search_type", "literal")).lower()
    allowed_exts = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in options.get("allowed_extensions", [])}
    ignored_dirs = set(options.get("ignored_dirs") or []) | DEFAULT_IGNORED_DIRS
    context_lines = int(options.get("context_lines", 3))
    max_results = int(options.get("max_results", 50))
    max_file_size = int(options.get("max_file_size_bytes", 1024 * 1024))
    line_range = options.get("line_range")

    warnings: List[str] = []
    results: List[Dict[str, Any]] = []
    file_index: Dict[str, Dict[str, Any]] = {}
    total_files_scanned = 0

    proj_dir = Path(proj_dir_str)
    if not proj_dir.exists():
        return {
            "summary": {
                "total_files_scanned": 0,
                "total_matches": 0,
                "returned_matches": 0,
                "is_truncated": False
            },
            "results": [],
            "index": {},
            "warnings": [f"Diretorio nao encontrado: {proj_dir_str}"]
        }

    # Compilar regexes de busca se aplicável
    compiled_patterns = []
    for t in terms:
        if not t:
            continue
        if search_type == "regex":
            try:
                compiled_patterns.append((re.compile(t, re.IGNORECASE), "regex", t))
            except Exception as e:
                warnings.append(f"Regex invalida '{t}': {e}. Usando busca literal.")
                compiled_patterns.append((re.compile(re.escape(t), re.IGNORECASE), "literal", t))
        elif search_type == "function":
            compiled_patterns.append((re.compile(r"(?i)^\s*(?:async\s+)?(?:def|function|fn|func|public\s+[\w<>\[\]]+\s+)\s*" + re.escape(t)), "function", t))
        elif search_type == "class":
            compiled_patterns.append((re.compile(r"(?i)^\s*(?:class|struct|interface|enum)\s+" + re.escape(t)), "class", t))
        elif search_type == "route":
            compiled_patterns.append((re.compile(r"(?i)(?:@(?:app|router|api)|Route\(['\"]|app\.use\(['\"]).*" + re.escape(t)), "route", t))
        elif search_type == "exception":
            compiled_patterns.append((re.compile(r"(?i)(?:raise|throw|except|catch)\s+.*" + re.escape(t)), "exception", t))
        else:
            compiled_patterns.append((re.compile(re.escape(t), re.IGNORECASE), "literal", t))

    # Varredura recursiva de arquivos
    for root, dirs, files in os.walk(proj_dir):
        # Excluir pastas ignoradas in-place
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

        for f in files:
            file_path = Path(root) / f
            total_files_scanned += 1

            if allowed_exts and file_path.suffix.lower() not in allowed_exts:
                continue

            try:
                stat = file_path.stat()
                if stat.st_size > max_file_size:
                    warnings.append(f"Arquivo ignorado por exceder o tamanho maximo: {file_path.name}")
                    continue

                raw_bytes = file_path.read_bytes()
                if is_binary_buffer(raw_bytes[:8192]):
                    continue

                text = raw_bytes.decode("utf-8-sig", errors="replace")
                f_hash = calculate_file_hash(raw_bytes)
                rel_path = str(file_path.relative_to(proj_dir)).replace("\\", "/")

                lines = text.splitlines()
                file_matches = []

                # Se nao tiver termos, mas tiver line_range, extrai intervalo
                if not compiled_patterns and line_range and isinstance(line_range, dict):
                    l_from = max(1, int(line_range.get("from", 1)))
                    l_to = min(len(lines), int(line_range.get("to", len(lines))))
                    snippet_lines = [f"{i:4d} | {mask_secrets(lines[i-1])}" for i in range(l_from, l_to + 1)]
                    results.append({
                        "file": rel_path,
                        "line": l_from,
                        "start_line": l_from,
                        "end_line": l_to,
                        "match_type": "range",
                        "matched_text": lines[l_from - 1] if lines else "",
                        "snippet": "\n".join(snippet_lines),
                        "file_hash": f_hash
                    })
                    file_index[rel_path] = {"matches_count": 1, "file_hash": f_hash}
                    continue

                for line_idx, line in enumerate(lines, start=1):
                    # Checar cada termo
                    for pat, m_type, term_raw in compiled_patterns:
                        if pat.search(line):
                            start_l = max(1, line_idx - context_lines)
                            end_l = min(len(lines), line_idx + context_lines)

                            snippet_parts = []
                            for c in range(start_l, end_l + 1):
                                marker = " >> " if c == line_idx else "    "
                                safe_line = mask_secrets(lines[c - 1])
                                snippet_parts.append(f"{marker}{c:4d} | {safe_line}")

                            match_item = {
                                "file": rel_path,
                                "line": line_idx,
                                "start_line": start_l,
                                "end_line": end_l,
                                "match_type": m_type,
                                "matched_text": mask_secrets(line.strip()),
                                "snippet": "\n".join(snippet_parts),
                                "file_hash": f_hash
                            }
                            file_matches.append(match_item)
                            break  # 1 match por linha

                if file_matches:
                    file_index[rel_path] = {"matches_count": len(file_matches), "file_hash": f_hash}
                    results.extend(file_matches)

            except Exception as e:
                warnings.append(f"Erro ao processar {file_path.name}: {e}")

    total_matches = len(results)
    is_truncated = total_matches > max_results
    if is_truncated:
        warnings.append(f"Resultados limitados ao maximo de {max_results} ocorrencias.")

    return {
        "summary": {
            "total_files_scanned": total_files_scanned,
            "total_matches": total_matches,
            "returned_matches": len(results[:max_results]),
            "is_truncated": is_truncated
        },
        "results": results[:max_results],
        "index": file_index,
        "warnings": warnings
    }
