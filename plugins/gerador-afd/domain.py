import random
from datetime import datetime, date, timedelta
from typing import List, Tuple

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
