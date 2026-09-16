import json
import os
import re
import sys
from pathlib import Path
from typing import Any, List, Optional

SCAN_SEARCH_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "scan-search.ico"


def extract_field(data: Any, field: str) -> List[str]:
    results = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == field:
                results.append(json.dumps(v, ensure_ascii=False, indent=2) if isinstance(v, (dict, list)) else str(v))
            if isinstance(v, (dict, list)):
                results.extend(extract_field(v, field))
    elif isinstance(data, list):
        for item in data:
            results.extend(extract_field(item, field))
    return results


def extract_json_from_text(raw_text: str, target_field: str = "") -> dict:
    raw = (raw_text or "").strip()
    if not raw:
        return {"success": False, "message": "Texto vazio.", "items": [], "count": 0}

    extracted_jsons = []
    # 1. Tenta parse completo direto
    try:
        parsed = json.loads(raw)
        extracted_jsons.append(parsed)
    except Exception:
        # 2. Busca e decodifica blocos JSON {...} e [...] com suporte a aninhamento
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(raw):
            m = re.search(r'[\{\[]', raw[pos:])
            if not m:
                break
            start = pos + m.start()
            try:
                obj, end_idx = decoder.raw_decode(raw[start:])
                extracted_jsons.append(obj)
                pos = start + end_idx
            except Exception:
                pos = start + 1

    if not extracted_jsons:
        return {"success": False, "message": "Nenhum JSON válido detectado no texto.", "items": [], "count": 0}

    results = []
    target = target_field.strip()
    if target:
        for item in extracted_jsons:
            fields = extract_field(item, target)
            results.extend(fields)
    else:
        for item in extracted_jsons:
            results.append(json.dumps(item, indent=2, ensure_ascii=False))

    return {
        "success": True,
        "count": len(results),
        "items": results
    }


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows (delega para shared.web_utils)."""
    try:
        from shared.web_utils import set_window_taskbar_icon as _set_icon
    except ImportError:
        from plugins.shared.web_utils import set_window_taskbar_icon as _set_icon
    return _set_icon(icon_path=icon_path or SCAN_SEARCH_ICON_PATH, hwnd=hwnd)
