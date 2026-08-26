import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

FILE_SEARCH_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "file-search.ico"

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
    raw = (text or "").strip()
    if not raw:
        return {
            "success": False,
            "message": "Nenhum conteúdo de log fornecido.",
            "total_blocks": 0,
            "filtered_blocks": 0,
            "result_text": ""
        }

    blocks = parse_blocks(raw)
    re_filter = None
    if regex_term.strip():
        try:
            re_filter = re.compile(regex_term.strip(), re.IGNORECASE)
        except Exception as e:
            return {
                "success": False,
                "message": f"Expressão Regular inválida: {e}",
                "total_blocks": len(blocks),
                "filtered_blocks": 0,
                "result_text": ""
            }

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


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone file-search."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else FILE_SEARCH_ICON_PATH
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
