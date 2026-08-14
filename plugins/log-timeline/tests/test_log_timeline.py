import importlib.util
import json
import sys
from pathlib import Path
import pytest

plugin_root = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_root))

def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, plugin_root / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

domain_mod = load_module("log_timeline_domain", "domain.py")
main_mod = load_module("log_timeline_main", "main.py")

generate_log_timeline = domain_mod.generate_log_timeline
handle_ipc = main_mod.handle_ipc

def test_1_timestamps_ausentes():
    text = """Event without time 1\nEvent without time 2"""
    res = generate_log_timeline(text)
    assert res["summary"]["events_without_timestamp"] == 2
    assert len(res["timeline"]) == 2
    assert res["timeline"][0]["timestamp"] is None

def test_2_multiplos_formatos_timestamp():
    text = """2026-08-14T10:00:00.000Z [INFO] ISO event\n14/08/2026 10:01:00 [WARN] BR event\nAug 14 10:02:00 host [ERROR] Syslog event"""
    res = generate_log_timeline(text)
    assert res["summary"]["total_events"] == 3
    assert res["summary"]["events_without_timestamp"] == 0
    assert "2026-08-14T10:00:00" in res["timeline"][0]["timestamp"]
    assert "2026-08-14T10:01:00" in res["timeline"][1]["timestamp"]

def test_3_eventos_fora_de_ordem():
    text = """2026-08-14T10:05:00.000Z Event late\n2026-08-14T10:01:00.000Z Event early"""
    res = generate_log_timeline(text)
    assert res["timeline"][0]["line"] == 2  # early vem primeiro
    assert res["timeline"][1]["line"] == 1  # late vem depois

def test_4_eventos_duplicados():
    text = """2026-08-14T10:00:00.000Z [INFO] Repetitive event\n2026-08-14T10:00:00.000Z [INFO] Repetitive event"""
    # Mesma linha? Diferentes linhas nao sao descartadas, mas se for mesmo conteudo
    res = generate_log_timeline(text)
    assert res["summary"]["total_events"] == 2

def test_5_multiplas_entradas_json_events():
    events_json = json.dumps([
        {"timestamp": "2026-08-14T10:00:00Z", "message": "First event"},
        {"timestamp": "2026-08-14T10:02:00Z", "message": "Second event", "level": "ERROR"}
    ])
    res = generate_log_timeline(events_json)
    assert res["summary"]["total_events"] == 2
    assert res["summary"]["first_error"] is not None

def test_6_entrada_log_optimizer():
    opt_json = json.dumps({
        "result": {
            "clusters": [
                {"template": "Timeout connecting to DB", "first_seen": {"line": 1, "message": "2026-08-14T10:00:00Z Timeout connecting to DB"}}
            ]
        }
    })
    res = generate_log_timeline(opt_json)
    assert res["summary"]["total_events"] == 1
    assert "2026-08-14T10:00:00" in res["timeline"][0]["timestamp"]

def test_7_agrupamento_por_baldes_e_pico_de_erros():
    text = """2026-08-14T10:00:01.000Z [ERROR] Err 1\n2026-08-14T10:00:02.000Z [ERROR] Err 2\n2026-08-14T10:01:05.000Z [INFO] Ok 1"""
    res = generate_log_timeline(text, {"interval": "1m"})
    assert len(res["buckets"]) == 2
    assert res["summary"]["error_peak"] is not None
    assert res["summary"]["error_peak"]["errors"] == 2

def test_8_padroes_operacionais():
    text = """2026-08-14T10:00:00.000Z Circuit breaker opened for auth-service\n2026-08-14T10:00:05.000Z Connection refused by redis:6379\n2026-08-14T10:00:10.000Z Retrying request after timeout"""
    res = generate_log_timeline(text)
    tags_all = [tag for e in res["timeline"] for tag in e["tags"]]
    assert "CIRCUIT_BREAKER" in tags_all
    assert "CONN_REFUSED" in tags_all
    assert "RETRY" in tags_all
    assert "TIMEOUT" in tags_all

def test_9_renderizacao_markdown_e_compact():
    text = """2026-08-14T10:00:00.000Z [ERROR] NullPointerException\n2026-08-14T10:01:00.000Z [INFO] System started"""
    res_md = generate_log_timeline(text, {"output_format": "markdown"})
    assert "formatted_output" in res_md
    assert "# ⏱️ Linha do Tempo de Incidentes" in res_md["formatted_output"]

    res_txt = generate_log_timeline(text, {"output_format": "compact_text"})
    assert "formatted_output" in res_txt
    assert "L0001" in res_txt["formatted_output"]

def test_10_protocolo_ipc_v1():
    payload = {
        "protocol_version": "1.0",
        "request_id": "req_timeline_01",
        "content": "2026-08-14T10:00:00.000Z [INFO] Starting up"
    }
    resp = handle_ipc(payload)
    assert resp["status"] == "success"
    assert resp["protocol_version"] == "1.0"
    assert resp["request_id"] == "req_timeline_01"
    assert resp["result"]["summary"]["total_events"] == 1
