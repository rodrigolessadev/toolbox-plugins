"""Motor de geração de comandos SQL INSERT para a tabela R070ACC.
Implementação compatível 1:1 com o gerador do Kapinote.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set

DEFAULT_VALUES: Dict[str, str] = {
    "NUMCRA": "600000010",
    "DATACC": "03-04-2025 00:00:00.000",
    "HORACC": "720",
    "USOMAR": "2",
    "NUMEMP": "1",
    "TIPCOL": "1",
    "NUMCAD": "0",
    "SEQACC": "1",
    "TIPACC": "1",
    "CODPLT": "1",
    "CODRLG": "1",
    "CODFNC": "0",
    "DIRACC": "E",
    "QTDACC": "1",
    "ORIACC": "E",
    "DATAPU": "31-12-1900 00:00:00.000",
    "CODREF": "0",
    "USOREF": "0",
    "VALREF": "0",
    "CODSOR": "0",
    "FLAACC": "0",
    "CODBNF": "0",
    "STARLG": "0",
    "EXCPON": "N",
    "CODDSP": "0",
    "MOTIGN": "0",
    "NUMNSR": "0",
}

FIXED_FIELDS = [
    {"name": "NUMCRA", "label": "NumCra - Número do Crachá", "defaultValue": "600000010"},
    {"name": "DATACC", "label": "DatAcc - Data do Acesso", "defaultValue": "03-04-2025 00:00:00.000"},
    {"name": "HORACC", "label": "HorAcc - Hora do Acesso", "defaultValue": "720"},
]

MAIN_FIELDS = [
    {"name": "USOMAR", "label": "UsoMar - Uso da Marcação", "defaultValue": "2"},
    {"name": "NUMEMP", "label": "NumEmp - Código da Empresa", "defaultValue": "1"},
    {"name": "TIPCOL", "label": "TipCol - Tipo de Colaborador", "defaultValue": "1"},
    {"name": "NUMCAD", "label": "NumCad - Cadastro do Colaborador", "defaultValue": "0"},
]

OPTIONAL_FIELDS = [
    {"name": "SEQACC", "label": "SeqAcc - Sequência do Registro", "defaultValue": "1"},
    {"name": "TIPACC", "label": "TipAcc - Tipo do Acesso", "defaultValue": "1"},
    {"name": "CODPLT", "label": "CodPlt - Código do Site", "defaultValue": "1"},
    {"name": "CODRLG", "label": "CodRlg - Código do Coletor no Acesso", "defaultValue": "1"},
    {"name": "CODFNC", "label": "CodFnc - Código da Função no Acesso", "defaultValue": "0"},
    {"name": "DIRACC", "label": "DirAcc - Direção do Acesso", "defaultValue": "E"},
    {"name": "QTDACC", "label": "QtdAcc - Quantidade no Acesso", "defaultValue": "1"},
    {"name": "ORIACC", "label": "OriAcc - Origem da Marcação", "defaultValue": "E"},
    {"name": "DATAPU", "label": "DatApu - Data de Apuração da Marcação", "defaultValue": "31-12-1900 00:00:00.000"},
    {"name": "CODREF", "label": "CodRef - Código da Refeição da Marcação", "defaultValue": "0"},
    {"name": "USOREF", "label": "UsoRef - Uso da Refeição", "defaultValue": "0"},
    {"name": "VALREF", "label": "ValRef - Valor da Refeição", "defaultValue": "0"},
    {"name": "CODSOR", "label": "CodSoR - Código da Solicitação no Relógio", "defaultValue": "0"},
    {"name": "FLAACC", "label": "FlaAcc - Flag do Acesso", "defaultValue": "0"},
    {"name": "CODBNF", "label": "CodBnf - Código do Benefício", "defaultValue": "0"},
    {"name": "STARLG", "label": "StaRlg - Status do Coletor na Hora da Coleta", "defaultValue": "0"},
    {"name": "EXCPON", "label": "ExCon - Excluído do Ponto", "defaultValue": "N"},
    {"name": "CODDSP", "label": "CodDsp - Código do Dispositivo", "defaultValue": "0"},
    {"name": "MOTIGN", "label": "MotIgn - Motivo Marcação Ignorada", "defaultValue": "0"},
    {"name": "NUMNSR", "label": "NumNSR - Número NSR", "defaultValue": "0"},
]

INSERT_ORDER = [
    "NUMCRA", "DATACC", "HORACC", "SEQACC", "TIPACC", "CODPLT", "CODRLG", "CODFNC",
    "DIRACC", "QTDACC", "ORIACC", "USOMAR", "NUMEMP", "TIPCOL", "NUMCAD",
    "DATAPU", "CODREF", "USOREF", "VALREF", "CODSOR", "FLAACC", "CODBNF",
    "STARLG", "EXCPON", "CODDSP", "MOTIGN", "NUMNSR",
]

NUMERIC_FIELDS: Set[str] = {
    "NUMCRA", "HORACC", "SEQACC", "TIPACC", "CODPLT", "CODRLG", "CODFNC", "QTDACC",
    "USOMAR", "NUMEMP", "TIPCOL", "NUMCAD", "CODREF", "USOREF", "VALREF",
    "CODSOR", "FLAACC", "CODBNF", "STARLG", "CODDSP", "MOTIGN", "NUMNSR",
}

DATE_FIELDS: Set[str] = {"DATACC", "DATAPU"}


def time_to_minutes(time_str: str) -> str:
    """Converte 'HH:MM' em total de minutos no dia (string numérica)."""
    try:
        parts = time_str.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return str(h * 60 + m)
    except Exception:
        return "0"


def escape_sql_string(value: str) -> str:
    """Escapa apóstrofos para literais SQL (' -> '')."""
    return str(value).replace("'", "''")


def format_date_value(value: str, banco: str) -> str:
    """Formata valor de data para o dialeto alvo (SQL Server ou Oracle).
    Formato base de entrada esperado: 'dd-MM-yyyy HH:mm:ss.000' ou 'dd/MM/yyyy ...'
    """
    val = str(value).strip()
    if "/" in val:
        parts = val.split(" ")
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else "00:00:00.000"
        d_parts = date_part.split("/")
        if len(d_parts) == 3:
            val = f"{d_parts[0]}-{d_parts[1]}-{d_parts[2]} {time_part}"

    b = banco.strip().lower()
    if b == "sqlserver":
        return f"'{val}'"

    # Oracle: TO_DATE sem milissegundos
    without_ms = re.sub(r"\.\d+$", "", val)
    return f"TO_DATE('{without_ms}', 'DD-MM-YYYY HH24:MI:SS')"


def format_value(field_name: str, value: str, banco: str) -> str:
    """Formata um valor de campo específico conforme regras de tipo e dialeto."""
    if field_name in NUMERIC_FIELDS:
        val = str(value).strip()
        return val if val else DEFAULT_VALUES.get(field_name, "0")

    if field_name in DATE_FIELDS:
        return format_date_value(value, banco)

    # Campos de texto
    escaped = escape_sql_string(str(value).strip() if value is not None else DEFAULT_VALUES.get(field_name, ""))
    return f"'{escaped}'"


def gerar_insert_sql(
    form_data: Dict[str, Any],
    horacc_list: List[str],
    dates: List[date],
    selected_optional: Optional[List[str]] = None,
    banco: str = "sqlserver"
) -> Dict[str, Any]:
    """Gera lista de instruções INSERT INTO R070ACC exatamente no formato do Kapinote."""
    selected_optional = selected_optional or []
    inserts: List[str] = []

    active_horarios = [h.strip() for h in horacc_list if h and h.strip()]
    if not active_horarios:
        active_horarios = ["08:00"]

    active_dates = dates if dates else [None]

    # Lookups rápidos para defaults
    fixed_map = {f["name"]: f["defaultValue"] for f in FIXED_FIELDS}
    main_map = {f["name"]: f["defaultValue"] for f in MAIN_FIELDS}
    optional_map = {f["name"]: f["defaultValue"] for f in OPTIONAL_FIELDS}

    for horacc in active_horarios:
        for cur_date in active_dates:
            values_map: Dict[str, str] = {}

            for field_name in INSERT_ORDER:
                raw_value = ""

                # Campos fixos
                if field_name in fixed_map:
                    if field_name == "HORACC":
                        raw_value = time_to_minutes(horacc)
                    elif field_name == "DATACC" and cur_date:
                        raw_value = f"{cur_date.strftime('%d-%m-%Y')} 00:00:00.000"
                    else:
                        raw_value = form_data.get(field_name) or fixed_map[field_name]

                # Campos principais
                elif field_name in main_map:
                    raw_value = form_data.get(field_name) or main_map[field_name]

                # Campos opcionais
                elif field_name in optional_map:
                    if field_name in selected_optional:
                        raw_value = form_data.get(field_name) or optional_map[field_name]
                    else:
                        raw_value = optional_map[field_name]

                values_map[field_name] = format_value(field_name, raw_value, banco)

            columns = ",".join(INSERT_ORDER)
            values = ",".join(values_map[col] for col in INSERT_ORDER)
            inserts.append(f"INSERT INTO R070ACC({columns}) VALUES({values})")

    sql_output = "\n".join(inserts)
    return {
        "success": True,
        "count": len(inserts),
        "sql": sql_output,
        "inserts": inserts
    }


def gerar_sql_marcacoes(
    banco: str = "sqlserver",
    numcra: str = "600000010",
    start_date: str = "",
    end_date: str = "",
    horarios: Optional[List[str]] = None,
    week_days: Optional[List[int]] = None,
    main_fields: Optional[Dict[str, Any]] = None,
    optional_values: Optional[Dict[str, Any]] = None,
    selected_optional: Optional[List[str]] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """Ponto de entrada unificado para a API JavaScript do pywebview."""
    banco_clean = (banco or "sqlserver").lower()
    horarios = [h for h in (horarios or ["08:00", "12:00", "13:00", "18:00"]) if h]
    week_days = week_days if week_days is not None else [1, 2, 3, 4, 5]
    selected_optional = selected_optional or []

    # Processamento de intervalo de datas
    dates: List[date] = []
    if start_date and end_date:
        try:
            d_ini = datetime.strptime(start_date, "%Y-%m-%d").date()
            d_fim = datetime.strptime(end_date, "%Y-%m-%d").date()
            cur = d_ini
            while cur <= d_fim:
                # 0=Dom, 1=Seg, 2=Ter, 3=Qua, 4=Qui, 5=Sex, 6=Sab
                js_day = (cur.weekday() + 1) % 7
                if js_day in week_days:
                    dates.append(cur)
                cur += timedelta(days=1)
        except Exception as e:
            return {"success": False, "message": f"Data inválida: {e}", "sql": "", "count": 0}
    elif start_date:
        try:
            dates = [datetime.strptime(start_date, "%Y-%m-%d").date()]
        except Exception as e:
            return {"success": False, "message": f"Data inválida: {e}", "sql": "", "count": 0}

    form_data: Dict[str, Any] = {
        "NUMCRA": numcra,
    }
    if main_fields:
        form_data.update(main_fields)
    if optional_values:
        form_data.update(optional_values)

    return gerar_insert_sql(
        form_data=form_data,
        horacc_list=horarios,
        dates=dates,
        selected_optional=selected_optional,
        banco=banco_clean,
    )
