"""
Logica pura do Gerador de Marcacoes (sem dependencia de tkinter).

Separada do main.py para que os testes possam importar a logica em
ambientes headless (CI, sandbox) sem precisar do Tk.

Porta fiel de app/(main)/(routes)/insert/_components/insert-builder.ts
do KapiNote.
"""

from datetime import date, datetime, timedelta

# Defaults dos campos principais
DEFAULTS = {name: "" for name in (
    "NUMCRA", "USOMAR", "NUMEMP", "TIPCOL", "NUMCAD",
)}

# Campos numericos (sem aspas) e de data (com formatacao por dialeto).
# NUMCRA foi removido: no Protheus o numero do cracha aceita alfanumerico
# (ex: "M001", "V002"), entao precisa de escape de aspas. O TS original
# herdava o mesmo erro do insert-builder.ts.
NUMERIC_FIELDS = {
    "SEQACC", "TIPACC", "CODPLT", "CODRLG", "CODFNC", "QTDACC",
    "CODREF", "USOREF", "VALREF", "CODSOR", "FLAACC", "CODBNF",
    "STARLG", "CODDSP", "MOTIGN", "NUMNSR", "USOMAR", "NUMEMP",
    "TIPCOL", "NUMCAD",
}
DATE_FIELDS = {"DATAPU"}

# Ordem dos campos no INSERT
INSERT_ORDER = [
    "NUMCRA", "USOMAR", "NUMEMP", "TIPCOL", "NUMCAD",
    "SEQACC", "TIPACC", "CODPLT", "CODRLG", "CODFNC",
    "DIRACC", "QTDACC", "ORIACC", "DATACC", "DATAPU",
    "HORACC", "CODREF", "USOREF", "VALREF", "CODSOR",
    "FLAACC", "CODBNF", "STARLG", "EXCPON", "CODDSP",
    "MOTIGN", "NUMNSR",
]

# Defaults dos 20 campos opcionais (mesma ordem do Select Radix do KapiNote)
OPTIONAL_DEFAULTS = {
    "SEQACC": "1",  "TIPACC": "1",  "CODPLT": "1",  "CODRLG": "1",
    "CODFNC": "0",  "DIRACC": "E",  "QTDACC": "1",  "ORIACC": "E",
    "DATAPU": "31-12-1900 00:00:00.000",
    "CODREF": "0",  "USOREF": "0",  "VALREF": "0",  "CODSOR": "0",
    "FLAACC": "0",  "CODBNF": "0",  "STARLG": "0",  "EXCPON": "N",
    "CODDSP": "0",  "MOTIGN": "0",  "NUMNSR": "0",
}


# ---------------------------------------------------------------------------
# Helpers de dialeto
# ---------------------------------------------------------------------------

def fn_data_atual(banco: str) -> str:
    """GETDATE() para SQL Server, SYSDATE para Oracle."""
    return "GETDATE()" if banco == "sqlserver" else "SYSDATE"


def fn_isnull(expr: str, fallback, banco: str) -> str:
    """ISNULL(x, y) para SQL Server, NVL(x, y) para Oracle."""
    return f"ISNULL({expr}, {fallback})" if banco == "sqlserver" else f"NVL({expr}, {fallback})"


def traduzir_tipo(tipo: str, banco: str) -> str:
    """Mapeia tipos SQL Server -> Oracle (para uso em CREATE TABLE)."""
    if banco == "sqlserver":
        return tipo
    mapa = {
        "varchar": "VARCHAR2", "nvarchar": "VARCHAR2", "char": "CHAR",
        "datetime": "DATE", "smalldatetime": "DATE",
        "int": "NUMBER", "smallint": "NUMBER(5)", "tinyint": "NUMBER(3)",
        "bigint": "NUMBER(19)", "bit": "NUMBER(1)",
        "decimal": "NUMBER", "numeric": "NUMBER",
        "float": "BINARY_DOUBLE", "real": "BINARY_FLOAT",
        "text": "CLOB", "ntext": "NCLOB",
    }
    return mapa.get(tipo.lower(), tipo.upper())


# ---------------------------------------------------------------------------
# Formatacao de valores
# ---------------------------------------------------------------------------

def time_to_minutes(hhmm: str) -> int:
    """'08:30' -> 510 minutos (usado em HORACC)."""
    if not hhmm or ":" not in hhmm:
        return 0
    try:
        h, m = hhmm.split(":", 1)
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return 0


def format_date_value(d: date, banco: str) -> str:
    """Formata data no padrao aceito pelo dialeto."""
    base = d.strftime("%d-%m-%Y 00:00:00.000")
    if banco == "sqlserver":
        return f"'{d.strftime('%Y%m%d')} 00:00:00.000'"
    return f"TO_DATE('{base}', 'DD-MM-YYYY HH24:MI:SS')"


def escape_sql_string(s) -> str:
    """Escapa aspas simples para SQL."""
    if s is None:
        return ""
    return str(s).replace("'", "''")


def format_value(field: str, raw: str, banco: str) -> str:
    """Formata um valor de acordo com o tipo do campo e o dialeto."""
    raw = (raw or "").strip()
    if field in NUMERIC_FIELDS:
        return raw if raw else "0"
    if field in DATE_FIELDS and raw:
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                d = datetime.strptime(raw, fmt).date()
                return format_date_value(d, banco)
            except ValueError:
                continue
        return f"'{escape_sql_string(raw)}'"
    return f"'{escape_sql_string(raw)}'"


# ---------------------------------------------------------------------------
# date_range - filtragem por dia da semana
# ---------------------------------------------------------------------------

def date_range(inicio: date, fim: date, dias_semana: set):
    """Gera datas no intervalo (inclusivo) que casam com dias_semana.

    dias_semana usa a convencao JavaScript: 0=Dom, 1=Seg, ..., 6=Sab.
    """
    if not dias_semana:
        return []
    out = []
    cur = inicio
    while cur <= fim:
        js_day = (cur.weekday() + 1) % 7  # Python weekday -> JS getDay
        if js_day in dias_semana:
            out.append(cur)
        cur += timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# gerar_inserts
# ---------------------------------------------------------------------------

def gerar_inserts(fields: dict, horarios: list, datas: list, banco: str,
                  selected_optional: list) -> str:
    """
    Gera os INSERTs SQL para R070ACC.

    Args:
        fields: dict com valores de MAIN_FIELDS + opcionais selecionados.
        horarios: lista de strings 'HH:MM'.
        datas: lista de objetos date (ja filtradas por dia da semana).
        banco: 'sqlserver' ou 'oracle'.
        selected_optional: lista de nomes de campos opcionais adicionados.

    Returns:
        String com INSERTs separados por '\\n'.
    """
    if not horarios:
        raise ValueError("Adicione pelo menos um horario.")
    if not datas:
        raise ValueError("Nenhuma data no intervalo (verifique os dias da semana).")

    # Mescla defaults com valores do form
    final = dict(DEFAULTS)
    final.update({k: v for k, v in fields.items() if v})
    for name, default in OPTIONAL_DEFAULTS.items():
        if name not in final and name not in selected_optional:
            final[name] = default

    lines = []
    for d in datas:
        datacc_sql = format_date_value(d, banco)
        for hhmm in horarios:
            minutos = time_to_minutes(hhmm)
            parts = []
            for col in INSERT_ORDER:
                if col == "DATACC":
                    parts.append(datacc_sql)
                elif col == "HORACC":
                    parts.append(str(minutos))
                elif col in NUMERIC_FIELDS:
                    val = final.get(col, "0")
                    parts.append(str(val) if val else "0")
                elif col in DATE_FIELDS:
                    val = final.get(col, "")
                    if val:
                        parts.append(format_value(col, val, banco))
                    else:
                        parts.append(format_date_value(date(1900, 12, 31), banco))
                else:
                    val = final.get(col, "")
                    parts.append(f"'{escape_sql_string(val)}'")
            cols_sql = ", ".join(INSERT_ORDER)
            vals_sql = ", ".join(parts)
            lines.append(f"INSERT INTO R070ACC ({cols_sql}) VALUES ({vals_sql});")
    return "\n".join(lines)
