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
    assert gm_domain.time_to_minutes("08:00") == 480
    assert gm_domain.time_to_minutes("12:30") == 750
    assert gm_domain.time_to_minutes("invalid") == 0


def test_format_date_oracle_and_sqlserver():
    d = date(2026, 8, 25)
    assert gm_domain.format_date(d, "ORACLE") == "TO_DATE('25/08/2026', 'DD/MM/YYYY')"
    assert gm_domain.format_date(d, "SQLSERVER") == "CONVERT(DATETIME, '2026-08-25', 120)"
    assert gm_domain.format_date(d, "POSTGRES") == "'2026-08-25'"


def test_gerar_sql_marcacoes_success():
    res = gm_domain.gerar_sql_marcacoes(
        tabela="R070ACC",
        banco="ORACLE",
        campos_fixos={"NUMEMP": 1, "TIPCOL": 1, "NUMCAD": 100},
        start_date="2026-08-24",  # Segunda-feira
        end_date="2026-08-24",    # 1 dia útil
        horarios=["08:00", "12:00", "13:00", "18:00"],
        variacao_minutos=0,
        pular_fins_de_semana=True
    )
    assert res["success"] is True
    assert res["count"] == 4
    assert "INSERT INTO R070ACC" in res["sql"]
    assert "NUMCAD" in res["sql"]


def test_gerar_sql_marcacoes_invalid_date():
    res = gm_domain.gerar_sql_marcacoes(
        tabela="R070ACC",
        banco="ORACLE",
        campos_fixos={},
        start_date="invalid",
        end_date="2026-08-24",
        horarios=["08:00"]
    )
    assert res["success"] is False
    assert "Data inválida" in res["message"]
