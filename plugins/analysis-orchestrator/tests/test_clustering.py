import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.clustering import cluster_logs

def test_clustering_templates():
    text = "2026-08-14T10:00:00Z Task 123 completed in 45ms\n2026-08-14T10:00:01Z Task 456 completed in 50ms"
    res = cluster_logs(text)
    assert res["summary"]["total_clusters"] == 1
