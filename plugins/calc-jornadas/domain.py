import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class ParametrosJornada:
    inicio_noturno: int = 22 * 60  # 22:00 = 1320 min
    fim_noturno: int = 5 * 60       # 05:00 = 300 min
    fator_minutos: float = 52.5     # Fator de redução noturna CLT (52.5 min = 1h computada)

    @property
    def fator_reducao(self) -> float:
        return self.fator_minutos / 60.0


@dataclass
class ResultadoJornada:
    total_minutos: int
    minutos_normais: int
    minutos_noturnos: int
    minutos_noturnos_reduzidos: int


def hora_para_min(hora: str) -> int:
    try:
        parts = hora.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h * 60 + m
    except Exception:
        return 0


def min_para_hora(minutos: int) -> str:
    sinal = "-" if minutos < 0 else ""
    total = round(abs(minutos))
    h = total // 60
    m = total % 60
    return f"{sinal}{h:02d}:{m:02d}"


def minutos_noturnos(entrada: int, saida: int, params: ParametrosJornada) -> int:
    saida_norm = saida
    if saida_norm <= entrada:
        saida_norm += 24 * 60

    minutos_dia = 24 * 60
    periodos = [
        (params.inicio_noturno, minutos_dia),
        (0, params.fim_noturno),
        (params.inicio_noturno + minutos_dia, 2 * minutos_dia),
        (minutos_dia, params.fim_noturno + minutos_dia),
    ]

    total_noturno = 0
    for p_inicio, p_fim in periodos:
        overlap_inicio = max(entrada, p_inicio)
        overlap_fim = min(saida_norm, p_fim)
        if overlap_fim > overlap_inicio:
            total_noturno += overlap_fim - overlap_inicio
    return total_noturno


def calcular_jornada(entrada_str: str, saida_str: str, params: ParametrosJornada) -> ResultadoJornada:
    entrada = hora_para_min(entrada_str)
    saida = hora_para_min(saida_str)
    if saida <= entrada:
        saida += 24 * 60

    total_minutos_real = saida - entrada
    noturno = minutos_noturnos(entrada, saida, params)
    normal = total_minutos_real - noturno
    noturno_reduzido = round(noturno / params.fator_reducao) if params.fator_reducao > 0 else noturno
    total_computado = normal + noturno_reduzido

    return ResultadoJornada(
        total_minutos=total_computado,
        minutos_normais=normal,
        minutos_noturnos=noturno,
        minutos_noturnos_reduzidos=noturno_reduzido,
    )


def consolidar_jornadas(grupos: List[Dict[str, str]], params: ParametrosJornada) -> Dict[str, Any]:
    resultados = []
    totais = {
        "minutos_normais": 0,
        "minutos_noturnos": 0,
        "minutos_noturnos_reduzidos": 0,
        "total_minutos": 0,
    }

    for g in grupos:
        e = g.get("entrada", "").strip()
        s = g.get("saida", "").strip()
        if not e or not s:
            resultados.append({**g, "resultado": None, "erro": None})
            continue
        try:
            res = calcular_jornada(e, s, params)
            res_dict = {
                "normais": min_para_hora(res.minutos_normais),
                "noturnas": min_para_hora(res.minutos_noturnos),
                "not_red": min_para_hora(res.minutos_noturnos_reduzidos),
                "total": min_para_hora(res.total_minutos),
                "minutos_normais": res.minutos_normais,
                "minutos_noturnos": res.minutos_noturnos,
                "minutos_noturnos_reduzidos": res.minutos_noturnos_reduzidos,
                "total_minutos": res.total_minutos,
            }
            totais["minutos_normais"] += res.minutos_normais
            totais["minutos_noturnos"] += res.minutos_noturnos
            totais["minutos_noturnos_reduzidos"] += res.minutos_noturnos_reduzidos
            totais["total_minutos"] += res.total_minutos
            resultados.append({**g, "resultado": res_dict, "erro": None})
        except Exception:
            resultados.append({**g, "resultado": None, "erro": "Horário inválido"})

    return {
        "success": True,
        "resultados": resultados,
        "totais": {
            "normais": min_para_hora(totais["minutos_normais"]),
            "noturnas": min_para_hora(totais["minutos_noturnos"]),
            "not_red": min_para_hora(totais["minutos_noturnos_reduzidos"]),
            "total": min_para_hora(totais["total_minutos"]),
            "minutos_normais": totais["minutos_normais"],
            "minutos_noturnos": totais["minutos_noturnos"],
            "minutos_noturnos_reduzidos": totais["minutos_noturnos_reduzidos"],
            "total_minutos": totais["total_minutos"],
            "tem_totais": totais["total_minutos"] > 0,
        }
    }


def calcular_totais_jornada(entradas: List[str], saidas: List[str], jornada_prevista_min: int = 480) -> dict:
    """Função legada mantida para retrocompatibilidade."""
    total_trabalhado = 0
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
        "detalhes": detalhes,
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
