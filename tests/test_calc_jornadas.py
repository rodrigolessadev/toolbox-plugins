import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "calc-jornadas" / "domain.py"

spec = importlib.util.spec_from_file_location("calc_jornadas_domain", DOMAIN_PATH)
calc_domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc_domain)

def test_hora_para_min():
    assert calc_domain.hora_para_min("08:00") == 480
    assert calc_domain.hora_para_min("12:30") == 750
    assert calc_domain.hora_para_min("invalid") == 0

def test_min_para_hora():
    assert calc_domain.min_para_hora(480) == "08:00"
    assert calc_domain.min_para_hora(-60) == "-01:00"
    assert calc_domain.min_para_hora(0) == "00:00"

def test_calcular_totais_jornada_normal():
    entradas = ["08:00", "13:00"]
    saidas = ["12:00", "17:00"]
    res = calc_domain.calcular_totais_jornada(entradas, saidas, jornada_prevista_min=480)
    assert res["success"] is True
    assert res["total_trabalhado_min"] == 480
    assert res["total_trabalhado_str"] == "08:00"
    assert res["saldo_min"] == 0
    assert res["saldo_str"] == "00:00"
    assert len(res["detalhes"]) == 2

def test_calcular_totais_jornada_extra():
    entradas = ["08:00", "13:00"]
    saidas = ["12:00", "18:00"]
    res = calc_domain.calcular_totais_jornada(entradas, saidas, jornada_prevista_min=480)
    assert res["total_trabalhado_min"] == 540
    assert res["total_trabalhado_str"] == "09:00"
    assert res["saldo_min"] == 60
    assert res["saldo_str"] == "01:00"
