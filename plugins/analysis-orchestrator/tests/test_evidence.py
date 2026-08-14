import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.evidence import build_evidence_package

def test_evidence_package_build():
    payload = {"incident_info": {"id": "INC-123", "service": "auth-service"}}
    res = build_evidence_package(payload)
    assert res["incident_summary"]["incident_id"] == "INC-123"
    assert "manifest" in res
