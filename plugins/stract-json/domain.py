import json
import re
from typing import Any, List

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
    raw = raw_text.strip()
    if not raw:
        return {"success": False, "message": "Texto vazio.", "items": []}

    extracted_jsons = []
    # 1. Tenta parse completo
    try:
        parsed = json.loads(raw)
        extracted_jsons.append(parsed)
    except Exception:
        # 2. Busca blocos JSON {...} e [...]
        brace_matches = re.finditer(r'(\{[\s\S]*?\}|\[[\s\S]*?\])', raw)
        for m in brace_matches:
            block = m.group(1).strip()
            try:
                p = json.loads(block)
                extracted_jsons.append(p)
            except Exception:
                continue

    if not extracted_jsons:
        return {"success": False, "message": "Nenhum JSON válido detectado no texto.", "items": []}

    results = []
    if target_field.strip():
        for item in extracted_jsons:
            fields = extract_field(item, target_field.strip())
            results.extend(fields)
    else:
        for item in extracted_jsons:
            results.append(json.dumps(item, indent=2, ensure_ascii=False))

    return {
        "success": True,
        "count": len(results),
        "items": results
    }
