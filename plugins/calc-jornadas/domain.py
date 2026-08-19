from dataclasses import dataclass
from typing import List, Dict, Any

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
