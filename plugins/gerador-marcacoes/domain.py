import random
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

def format_date(dt: date, banco: str) -> str:
    b = banco.upper()
    if b == "ORACLE":
        return f"TO_DATE('{dt.strftime('%d/%m/%Y')}', 'DD/MM/YYYY')"
    elif b == "SQLSERVER":
        return f"CONVERT(DATETIME, '{dt.strftime('%Y-%m-%d')}', 120)"
    return f"'{dt.strftime('%Y-%m-%d')}'"

def time_to_minutes(t_str: str) -> int:
    parts = t_str.strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h * 60 + m

def gerar_sql_marcacoes(
    tabela: str,
    banco: str,
    campos_fixos: Dict[str, Any],
    start_date: str,
    end_date: str,
    horarios: List[str],
    variacao_minutos: int = 2,
    pular_fins_de_semana: bool = True
) -> dict:
    try:
        d_ini = datetime.strptime(start_date, "%Y-%m-%d").date()
        d_fim = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception as e:
        return {"success": False, "message": f"Data inválida: {e}"}

    tab = tabela.strip() or "R070ACC"
    inserts = []
    cur = d_ini

    while cur <= d_fim:
        if pular_fins_de_semana and cur.weekday() >= 5:
            cur += timedelta(days=1)
            continue

        for h in horarios:
            if not h.strip():
                continue
            base_min = time_to_minutes(h)
            if variacao_minutos > 0:
                delta = random.randint(-variacao_minutos, variacao_minutos)
                final_min = max(0, min(1439, base_min + delta))
            else:
                final_min = base_min

            cols = ["DATACC", "HORACC"]
            vals = [format_date(cur, banco), str(final_min)]

            for k, v in campos_fixos.items():
                cols.append(k)
                vals.append(f"'{v}'" if isinstance(v, str) and not v.isdigit() else str(v))

            stmt = f"INSERT INTO {tab} ({', '.join(cols)}) VALUES ({', '.join(vals)});"
            inserts.append(stmt)
        cur += timedelta(days=1)

    return {
        "success": True,
        "count": len(inserts),
        "sql": "\n".join(inserts)
    }
