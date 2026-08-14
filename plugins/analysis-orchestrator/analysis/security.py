import hashlib
import re
from pathlib import Path
from typing import Optional

RE_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
RE_BEARER = re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9._~+/-]+=*")
RE_PRIVATE_KEY = re.compile(r"-----BEGIN[ A-Z0-9_-]+PRIVATE KEY-----[\s\S]*?-----END[ A-Z0-9_-]+PRIVATE KEY-----")


def is_binary_buffer(buf: bytes) -> bool:
    return b"\x00" in buf


def mask_secrets(text: str) -> str:
    if not text:
        return text
    t = RE_PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)
    t = RE_JWT.sub("[REDACTED_JWT]", t)
    t = RE_BEARER.sub("Bearer [REDACTED]", t)
    return t


def calculate_file_hash(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()
