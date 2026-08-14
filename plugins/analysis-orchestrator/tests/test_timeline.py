import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.timeline import generate_log_timeline

def test_timeline_chronological():
    text = "2026-08-14T10:05:00Z Event late\n2026-08-14T10:01:00Z Event early"
    res = generate_log_timeline(text)
    assert "2026-08-14T10:01:00" in res["timeline"][0]["timestamp"]
