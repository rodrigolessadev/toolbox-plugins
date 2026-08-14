import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.filtering import filter_incident_logs

def test_filtering_levels():
    text = "2026-08-14T10:00:00Z [INFO] Normal\n2026-08-14T10:01:00Z [ERROR] Error occurred"
    res = filter_incident_logs(text, {"levels": ["ERROR"]})
    assert res["summary"]["matched_events_count"] == 1
    assert "Error occurred" in res["events"][0]["message"]
