import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

@dataclass
class Params:
    ini_noturno: int = 22 * 60
    fim_noturno: int = 5 * 60
    fator_red_num: int = 60
    fator_red_den: int = 52.5
    jornada_padrao: int = 8 * 60
    intervalo_min: int = 60

def hora_para_min(s: str) -> int:
    try:
        parts = s.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h * 60 + m
    except Exception:
        return 0

def min_para_hora(m: int) -> str:
    sinal = "-" if m < 0 else ""
    m = abs(m)
    hh = m // 60
    mm = m % 60
    return f"{sinal}{hh:02d}:{mm:02d}"

def calcular_totais_jornada(entradas: List[str], saidas: List[str], jornada_prevista_min: int = 480) -> dict:
    total_trabalhado = 0
    total_intervalo = 0
    detalhes = []

    for i in range(min(len(entradas), len(saidas))):
        e_str = entradas[i].strip()
        s_str = saidas[i].strip()
        if not e_str or not s_str:
            continue
        e_min = hora_para_min(e_str)
        s_min = hora_para_min(s_str)
        if s_min < e_min:
            s_min += 1440  # virada de noite
        dur = s_min - e_min
        total_trabalhado += dur
        detalhes.append({"periodo": i + 1, "entrada": e_str, "saida": s_str, "duracao": min_para_hora(dur)})

    saldo = total_trabalhado - jornada_prevista_min

    return {
        "success": True,
        "total_trabalhado_min": total_trabalhado,
        "total_trabalhado_str": min_para_hora(total_trabalhado),
        "jornada_prevista_str": min_para_hora(jornada_prevista_min),
        "saldo_min": saldo,
        "saldo_str": min_para_hora(saldo),
        "detalhes": detalhes
    }


CLOCK_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "clock-3.ico"


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone de relógio."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else CLOCK_ICON_PATH
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

