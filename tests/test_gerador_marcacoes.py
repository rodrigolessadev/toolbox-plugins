import importlib.util
from datetime import date
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "gerador-marcacoes" / "domain.py"

spec = importlib.util.spec_from_file_location("gerador_marcacoes_domain", DOMAIN_PATH)
gm_domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm_domain)


def test_time_to_minutes():
    assert gm_domain.time_to_minutes("08:00") == "480"
    assert gm_domain.time_to_minutes("12:00") == "720"
    assert gm_domain.time_to_minutes("12:30") == "750"
    assert gm_domain.time_to_minutes("invalid") == "0"


def test_format_date_value_oracle_and_sqlserver():
    assert gm_domain.format_date_value("17-08-2026 00:00:00.000", "sqlserver") == "'17-08-2026 00:00:00.000'"
    assert gm_domain.format_date_value("17-08-2026 00:00:00.000", "oracle") == "TO_DATE('17-08-2026 00:00:00', 'DD-MM-YYYY HH24:MI:SS')"
    assert gm_domain.format_date_value("17/08/2026 00:00:00.000", "oracle") == "TO_DATE('17-08-2026 00:00:00', 'DD-MM-YYYY HH24:MI:SS')"


def test_gerar_sql_marcacoes_oracle_format():
    res = gm_domain.gerar_sql_marcacoes(
        banco="oracle",
        numcra="600000010",
        start_date="2026-08-17",
        end_date="2026-08-17",
        horarios=["08:00", "12:00"],
        week_days=[1], # Seg
        main_fields={"NUMEMP": "1", "TIPCOL": "1", "NUMCAD": "10"}
    )
    assert res["success"] is True
    assert res["count"] == 2
    
    line1 = res["inserts"][0]
    assert "INSERT INTO R070ACC(NUMCRA,DATACC,HORACC" in line1
    assert "TO_DATE('17-08-2026 00:00:00', 'DD-MM-YYYY HH24:MI:SS')" in line1
    assert "TO_DATE('31-12-1900 00:00:00', 'DD-MM-YYYY HH24:MI:SS')" in line1
    assert ",480," in line1
    assert ",10," in line1
    assert "'E'" in line1
    assert "'N'" in line1


def test_gerar_sql_marcacoes_sqlserver_format():
    res = gm_domain.gerar_sql_marcacoes(
        banco="sqlserver",
        numcra="600000010",
        start_date="2026-08-17",
        end_date="2026-08-17",
        horarios=["08:00"],
        week_days=[1],
        main_fields={"NUMEMP": "1", "TIPCOL": "1", "NUMCAD": "10"}
    )
    assert res["success"] is True
    assert res["count"] == 1
    
    line = res["inserts"][0]
    assert "'17-08-2026 00:00:00.000'" in line
    assert "'31-12-1900 00:00:00.000'" in line
    assert ",480," in line


def test_optional_fields_override():
    res = gm_domain.gerar_sql_marcacoes(
        banco="sqlserver",
        numcra="600000010",
        start_date="2026-08-17",
        end_date="2026-08-17",
        horarios=["08:00"],
        week_days=[1],
        optional_values={"DIRACC": "S", "EXCPON": "S"},
        selected_optional=["DIRACC", "EXCPON"]
    )
    assert res["success"] is True
    line = res["inserts"][0]
    assert "'S'" in line


def test_gerar_sql_marcacoes_validations():
    # Sem data
    res_no_date = gm_domain.gerar_sql_marcacoes(
        banco="sqlserver",
        numcra="123",
        start_date="",
        horarios=["08:00"]
    )
    assert res_no_date["success"] is False
    assert "Data" in res_no_date["message"]

    # Sem horários
    res_no_horarios = gm_domain.gerar_sql_marcacoes(
        banco="sqlserver",
        numcra="123",
        start_date="2026-08-17",
        horarios=[]
    )
    assert res_no_horarios["success"] is False
    assert "horário" in res_no_horarios["message"]

    # Data final anterior à data inicial
    res_invalid_range = gm_domain.gerar_sql_marcacoes(
        banco="sqlserver",
        numcra="123",
        start_date="2026-08-20",
        end_date="2026-08-10",
        horarios=["08:00"]
    )
    assert res_invalid_range["success"] is False
    assert "anterior" in res_invalid_range["message"]


def test_gerar_sql_marcacoes_empty_and_custom_numcra_numcad():
    # NumCra e NumCad vazios iniciam com "0" na instrução SQL
    res_empty = gm_domain.gerar_sql_marcacoes(
        banco="sqlserver",
        numcra="",
        start_date="2026-08-17",
        horarios=["08:00"],
        week_days=[1],
        main_fields={"NUMCAD": ""}
    )
    assert res_empty["success"] is True
    line = res_empty["inserts"][0]
    # INSERT INTO R070ACC(...) VALUES(0,'17-08-2026 00:00:00.000',480,1,1,1,1,0,'E',1,'E',2,1,1,0,...)
    assert line.startswith("INSERT INTO R070ACC(")
    assert "VALUES(0,'17-08-2026 00:00:00.000'" in line

    # NumCra e NumCad customizados
    res_custom = gm_domain.gerar_sql_marcacoes(
        banco="sqlserver",
        numcra="987654",
        start_date="2026-08-17",
        horarios=["09:30"],
        week_days=[1],
        main_fields={"NUMCAD": "4321", "USOMAR": "2", "NUMEMP": "5", "TIPCOL": "2"}
    )
    assert res_custom["success"] is True
    line_custom = res_custom["inserts"][0]
    assert "VALUES(987654,'17-08-2026 00:00:00.000',570" in line_custom
    assert ",4321," in line_custom
    assert ",5,2," in line_custom

