import os
import re
from datetime import datetime
from typing import List, Tuple

RE_TS = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?|"
    r"\d{2}[/-]\d{2}[/-]\d{4}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?|"
    r"\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"
)

def parse_blocks(text: str) -> List[dict]:
    blocks = []
    current_lines = []
    current_header = ""
    current_ts = ""

    for line in text.splitlines():
        m = RE_TS.match(line)
        if m:
            if current_lines:
                blocks.append({
                    "ts": current_ts,
                    "header": current_header,
                    "text": "\n".join(current_lines),
                })
            current_ts = m.group(1)
            current_header = line
            current_lines = [line]
        else:
            if current_lines:
                current_lines.append(line)
            else:
                current_lines = [line]
                current_header = line

    if current_lines:
        blocks.append({
            "ts": current_ts,
            "header": current_header,
            "text": "\n".join(current_lines),
        })
    return blocks

def filter_log_text(text: str, regex_term: str = "", level: str = "", deduplicate: bool = False) -> dict:
    blocks = parse_blocks(text)
    re_filter = re.compile(regex_term, re.IGNORECASE) if regex_term.strip() else None
    level_filter = level.strip().upper() if level and level != "TODOS" else None

    seen_signatures = set()
    filtered = []

    for b in blocks:
        if level_filter and level_filter not in b["header"].upper():
            continue
        if re_filter and not re_filter.search(b["text"]):
            continue
        if deduplicate:
            sig = b["header"]
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)
        filtered.append(b["text"])

    return {
        "success": True,
        "total_blocks": len(blocks),
        "filtered_blocks": len(filtered),
        "result_text": "\n\n".join(filtered)
    }
