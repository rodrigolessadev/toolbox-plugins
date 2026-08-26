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
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone scan-search."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else SCAN_SEARCH_ICON_PATH
    if not target_icon.exists():
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        h_icon_big = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            32,
            32,
            LR_LOADFROMFILE,
        )
        h_icon_small = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            16,
            16,
            LR_LOADFROMFILE,
        )

        if not h_icon_big and not h_icon_small:
            return False

        if hwnd:
            target_hwnds = [hwnd]
        else:
            current_pid = os.getpid()
            target_hwnds = []

            def _enum_windows_cb(handle: int, _: Any) -> bool:
                lpdw_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(handle, ctypes.byref(lpdw_pid))
                if lpdw_pid.value == current_pid:
                    if user32.IsWindowVisible(handle):
                        target_hwnds.append(handle)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(_enum_windows_cb), 0)

        success = False
        for target in target_hwnds:
            if h_icon_big:
                user32.SendMessageW(target, WM_SETICON, ICON_BIG, h_icon_big)
            if h_icon_small:
                user32.SendMessageW(target, WM_SETICON, ICON_SMALL, h_icon_small)
            success = True
        return success
    except Exception:
        pass
    return False
