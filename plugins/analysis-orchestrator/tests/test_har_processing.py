import sys
import json
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.har_processing import optimize_har

def test_har_processing_optimize():
    har_json = json.dumps({
        "log": {
            "entries": [
                {
                    "startedDateTime": "2026-08-14T10:00:00Z",
                    "request": {"method": "GET", "url": "https://api.senior.com.br/users/123", "headers": []},
                    "response": {"status": 200, "content": {"text": "{}"}, "headers": []}
                }
            ]
        }
    })
    res = optimize_har(har_json)
    assert res["summary"]["total_requests"] == 1
