import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.log_optimization import optimize_logs

def test_log_optimization_reduction():
    text = "\n".join([f"2026-08-14T10:00:00Z [INFO] User {i} logged in" for i in range(10)])
    res = optimize_logs(text)
    assert res["summary"]["total_lines"] == 10
    assert len(res["clusters"]) == 1
