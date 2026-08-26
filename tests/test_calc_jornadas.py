import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "calc-jornadas" / "domain.py"
MAIN_PATH = ROOT / "plugins" / "calc-jornadas" / "main.py"

spec_domain = importlib.util.spec_from_file_location("calc_jornadas_domain", DOMAIN_PATH)
calc_domain = importlib.util.module_from_spec(spec_domain)
spec_domain.loader.exec_module(calc_domain)

spec_main = importlib.util.spec_from_file_location("calc_jornadas_main", MAIN_PATH)
calc_main = importlib.util.module_from_spec(spec_main)
spec_main.loader.exec_module(calc_main)


def test_hora_para_min():
    assert calc_domain.hora_para_min("08:00") == 480
    assert calc_domain.hora_para_min("12:30") == 750
    assert calc_domain.hora_para_min("22:00") == 1320
    assert calc_domain.hora_para_min("05:00") == 300
    assert calc_domain.hora_para_min("invalid") == 0


def test_min_para_hora():
    assert calc_domain.min_para_hora(480) == "08:00"
    assert calc_domain.min_para_hora(-60) == "-01:00"
    assert calc_domain.min_para_hora(0) == "00:00"
    assert calc_domain.min_para_hora(831) == "13:51"


def test_exemplo_1_kapinote():
    """
    Exemplo 1 do KapiNote:
    18:00 - 22:00 (Normais: 04:00, Not: 00:00, Total: 04:00)
    23:00 - 08:00 (Normais: 03:00, Not: 06:00, NotRed: 06:51, Total: 09:51)
    Total: 13:51
    """
    params = calc_domain.ParametrosJornada()
    grupos = [
        {"entrada": "18:00", "saida": "22:00"},
        {"entrada": "23:00", "saida": "08:00"},
    ]
    res = calc_domain.consolidar_jornadas(grupos, params)
    assert res["success"] is True
    assert res["resultados"][0]["resultado"]["normais"] == "04:00"
    assert res["resultados"][0]["resultado"]["noturnas"] == "00:00"
    assert res["resultados"][0]["resultado"]["not_red"] == "00:00"
    assert res["resultados"][0]["resultado"]["total"] == "04:00"

    assert res["resultados"][1]["resultado"]["normais"] == "03:00"
    assert res["resultados"][1]["resultado"]["noturnas"] == "06:00"
    assert res["resultados"][1]["resultado"]["not_red"] == "06:51"
    assert res["resultados"][1]["resultado"]["total"] == "09:51"

    assert res["totais"]["total"] == "13:51"
    assert res["totais"]["normais"] == "07:00"
    assert res["totais"]["noturnas"] == "06:00"
    assert res["totais"]["not_red"] == "06:51"


def test_exemplo_2_kapinote():
    """Exemplo 2: 20:15 - 23:45 + 00:30 - 06:15 -> Total: 10:09"""
    params = calc_domain.ParametrosJornada()
    grupos = [
        {"entrada": "20:15", "saida": "23:45"},
        {"entrada": "00:30", "saida": "06:15"},
    ]
    res = calc_domain.consolidar_jornadas(grupos, params)
    assert res["totais"]["total"] == "10:09"


def test_exemplo_3_kapinote():
    """Exemplo 3: 21:20 - 00:10 + 04:40 - 09:25 -> Total: 07:57"""
    params = calc_domain.ParametrosJornada()
    grupos = [
        {"entrada": "21:20", "saida": "00:10"},
        {"entrada": "04:40", "saida": "09:25"},
    ]
    res = calc_domain.consolidar_jornadas(grupos, params)
    assert res["totais"]["total"] == "07:57"


def test_exemplo_4_kapinote_100_noturno():
    """Exemplo 4: 22:10 - 02:25 + 02:55 - 07:40 -> Total: 09:54"""
    params = calc_domain.ParametrosJornada()
    grupos = [
        {"entrada": "22:10", "saida": "02:25"},
        {"entrada": "02:55", "saida": "07:40"},
    ]
    res = calc_domain.consolidar_jornadas(grupos, params)
    assert res["totais"]["total"] == "09:54"


def test_exemplo_5_kapinote():
    """Exemplo 5: 17:35 - 23:20 + 23:40 - 04:25 -> Total: 11:22"""
    params = calc_domain.ParametrosJornada()
    grupos = [
        {"entrada": "17:35", "saida": "23:20"},
        {"entrada": "23:40", "saida": "04:25"},
    ]
    res = calc_domain.consolidar_jornadas(grupos, params)
    assert res["totais"]["total"] == "11:22"


def test_exemplo_6_kapinote():
    """Exemplo 6: 19:10 - 01:35 + 04:20 - 10:05 -> Total: 12:47"""
    params = calc_domain.ParametrosJornada()
    grupos = [
        {"entrada": "19:10", "saida": "01:35"},
        {"entrada": "04:20", "saida": "10:05"},
    ]
    res = calc_domain.consolidar_jornadas(grupos, params)
    assert res["totais"]["total"] == "12:47"


def test_jornada_noturna_pura():
    """22:00 às 05:00: 7h noturnas relógio (420 min) -> 8h computadas (480 min)"""
    params = calc_domain.ParametrosJornada()
    res = calc_domain.calcular_jornada("22:00", "05:00", params)
    assert res.minutos_normais == 0
    assert res.minutos_noturnos == 420
    assert res.minutos_noturnos_reduzidos == 480
    assert res.total_minutos == 480


def test_jornada_diurna_pura():
    """08:00 às 17:00: 9h diurnas puras (540 min)"""
    params = calc_domain.ParametrosJornada()
    res = calc_domain.calcular_jornada("08:00", "17:00", params)
    assert res.minutos_normais == 540
    assert res.minutos_noturnos == 0
    assert res.minutos_noturnos_reduzidos == 0
    assert res.total_minutos == 540


def test_calc_jornadas_api_bridge():
    api = calc_main.CalcJornadasApi()
    grupos = [
        {"entrada": "18:00", "saida": "22:00"},
        {"entrada": "23:00", "saida": "08:00"},
        {"entrada": "", "saida": ""},
    ]
    params = {
        "inicio_noturno": "22:00",
        "fim_noturno": "05:00",
        "fator_minutos": "52,5",
    }
    res = api.consolidar(grupos, params)
    assert res["success"] is True
    assert res["totais"]["total"] == "13:51"
    assert len(res["resultados"]) == 3
    assert res["resultados"][2]["resultado"] is None


def test_clock_icon_and_taskbar_helper():
    icon_path = calc_domain.CLOCK_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = calc_domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)
