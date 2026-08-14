import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def scan_directory_assets(analysis_dir: Path, exclude_dir: Optional[Path] = None) -> Dict[str, Any]:
    raw_logs = []
    har_files = []
    source_dirs = []
    metadata_files = []

    for item in analysis_dir.iterdir():
        if exclude_dir and item == exclude_dir:
            continue
        if item.name.startswith("analysis-results-") or item.name.startswith("."):
            continue

        if item.is_file():
            if item.suffix.lower() in (".log", ".txt", ".jsonl", ".ndjson", ".out", ".err"):
                raw_logs.append(item)
            elif item.suffix.lower() == ".har":
                har_files.append(item)
            elif item.name in ("incident.json", "metadata.json") or (item.suffix.lower() == ".json" and not item.name.startswith("analysis-")):
                metadata_files.append(item)
        elif item.is_dir():
            if item.name.lower() in ("logs", "log"):
                for sub_f in item.rglob("*"):
                    if sub_f.is_file() and sub_f.suffix.lower() in (".log", ".txt", ".jsonl", ".ndjson", ".out", ".err"):
                        raw_logs.append(sub_f)
            elif item.name.lower() == "har":
                for sub_f in item.rglob("*.har"):
                    if sub_f.is_file():
                        har_files.append(sub_f)
            elif item.name.lower() in ("source", "src"):
                source_dirs.append(item)
            elif item.name.lower() == "metadata":
                for sub_f in item.rglob("*.json"):
                    if sub_f.is_file():
                        metadata_files.append(sub_f)

    incident_metadata = {}
    for mf in metadata_files:
        try:
            parsed = json.loads(mf.read_text(encoding="utf-8-sig", errors="replace"))
            if isinstance(parsed, dict):
                incident_metadata.update(parsed)
        except Exception:
            pass

    return {
        "raw_logs": raw_logs,
        "har_files": har_files,
        "source_dirs": source_dirs,
        "metadata_files": metadata_files,
        "incident_metadata": incident_metadata
    }
