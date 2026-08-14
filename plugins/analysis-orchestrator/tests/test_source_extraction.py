import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.source_extraction import extract_sources

def test_source_extraction_search(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("def authenticate():\n    pass\n", encoding="utf-8")
    res = extract_sources({"project_path": str(tmp_path), "terms": ["authenticate"]})
    assert res["summary"]["total_matches"] == 1
