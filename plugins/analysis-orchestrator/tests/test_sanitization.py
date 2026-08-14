import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.sanitization import sanitize_content, sanitize_text

def test_sanitization_jwt():
    raw = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgN"
    res = sanitize_text(raw)
    assert "[REDACTED" in res

def test_sanitization_bearer():
    raw = "Bearer secret_token_12345"
    res = sanitize_text(raw)
    assert "Bearer [REDACTED]" in res

def test_sanitization_content():
    raw = "2026-08-14 [INFO] password: 'supersecret'"
    res = sanitize_content(raw)
    assert "[REDACTED]" in res["sanitized_content"]
