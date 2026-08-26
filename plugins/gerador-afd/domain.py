import os
import random
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Tuple, Optional, Any

def calcular_crc16(data: str) -> str:
    crc = 0
    for byte in data.encode("ascii", errors="replace"):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"

def limpar_numero(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())

def pad_left(value, size: int) -> str:
    return str(value).rjust(size, "0")

def pad_right(value: str, size: int) -> str:
    return str(value).ljust(size, " ")

def format_dh(dt: datetime) -> str:
    return dt.strftime("%d%m%Y%H%M")

def nome_arquivo(rep_number: str, cnpj: str) -> str:
    return f"AFD_{limpar_numero(rep_number).zfill(17)}_{limpar_numero(cnpj).zfill(14)}.txt"

def gerar_afd(
    rep_number: str,
    cnpj_cpf: str,
    razao_social: str,
    local_prestacao: str,
    pis: str,
    nome_empregado: str,
    start_date: str,
    end_date: str,
    horarios: List[str],
    variacao_minutos: int = 2,
    pular_fins_de_semana: bool = True,
) -> dict:
    cnpj_limpo = limpar_numero(cnpj_cpf).zfill(14)
    rep_limpo = limpar_numero(rep_number).zfill(17)
    pis_limpo = limpar_numero(pis).zfill(11)

    try:
        dt_ini = datetime.strptime(start_date, "%Y-%m-%d").date()
        dt_fim = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception as e:
        return {"success": False, "message": f"Data inválida: {e}"}

    lines = []
    nsr = 1

    razao_pad = razao_social[:150].ljust(150)
    h_data = f"{str(nsr).zfill(9)}11{cnpj_limpo}00000000000000{razao_pad}{rep_limpo}{dt_ini.strftime('%d%m%Y')}{dt_fim.strftime('%d%m%Y')}{datetime.now().strftime('%d%m%Y%H%M')}"
    lines.append(h_data)

    cur_date = dt_ini
    while cur_date <= dt_fim:
        if pular_fins_de_semana and cur_date.weekday() >= 5:
            cur_date += timedelta(days=1)
            continue

        for h_str in horarios:
            if not h_str.strip():
                continue
            nsr += 1
            try:
                parts = h_str.strip().split(":")
                hh = int(parts[0])
                mm = int(parts[1]) if len(parts) > 1 else 0
                dt_marca = datetime(cur_date.year, cur_date.month, cur_date.day, hh, mm)
                if variacao_minutos > 0:
                    delta = random.randint(-variacao_minutos, variacao_minutos)
                    dt_marca += timedelta(minutes=delta)
            except Exception:
                continue

            r_data = f"{str(nsr).zfill(9)}3{format_dh(dt_marca)}{pis_limpo}"
            lines.append(r_data)
        cur_date += timedelta(days=1)

    nsr += 1
    t_data = f"{str(nsr).zfill(9)}9{str(nsr).zfill(9)}"
    lines.append(t_data)

    content = "\r\n".join(lines) + "\r\n"
    filename = nome_arquivo(rep_number, cnpj_cpf)

    return {
        "success": True,
        "filename": filename,
        "total_records": len(lines),
        "content": content,
    }

def process_gerar_afd(params: dict) -> dict:
    return gerar_afd(**params)


FILE_CLOCK_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "file-clock.ico"


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone de arquivo/relógio AFD."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else FILE_CLOCK_ICON_PATH
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

