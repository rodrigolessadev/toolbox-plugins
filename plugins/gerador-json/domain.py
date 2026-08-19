import json

def format_json(raw_text: str, indent: int = 2) -> dict:
    raw = raw_text.strip()
    if not raw:
        return {"success": False, "message": "Texto vazio."}
    try:
        data = json.loads(raw)
        formatted = json.dumps(data, indent=indent, ensure_ascii=False)
        return {"success": True, "result": formatted}
    except Exception as e:
        return {"success": False, "message": f"Erro de JSON: {e}"}

def minify_json(raw_text: str) -> dict:
    raw = raw_text.strip()
    if not raw:
        return {"success": False, "message": "Texto vazio."}
    try:
        data = json.loads(raw)
        minified = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return {"success": True, "result": minified}
    except Exception as e:
        return {"success": False, "message": f"Erro de JSON: {e}"}
