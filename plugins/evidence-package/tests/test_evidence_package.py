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

domain_mod = load_module("evidence_package_domain", "domain.py")
main_mod = load_module("evidence_package_main", "main.py")

build_evidence_package = domain_mod.build_evidence_package
handle_ipc = main_mod.handle_ipc

def test_1_entradas_vazias():
    payload = {}
    res = build_evidence_package(payload)
    assert "manifest" in res
    assert "incident_summary" in res
    assert "evidence" in res
    assert "timeline" in res
    assert "references" in res
    assert "DISCLAIMER" in res["disclaimer"]

def test_2_correlacao_cruzada_har_e_timeline():
    payload = {
        "incident_info": {"id": "INC-100", "service": "auth-service"},
        "har": {
            "log": {
                "entries": [
                    {
                        "startedDateTime": "2026-08-14T10:00:00.000Z",
                        "request": {"method": "POST", "url": "https://api.senior.com.br/login"},
                        "response": {"status": 500}
                    }
                ]
            }
        },
        "timeline": [
            {
                "line": 42,
                "timestamp": "2026-08-14T10:00:01.000Z",
                "message": "[ERROR] NullPointerException during login",
                "is_error": True
            }
        ]
    }
    res = build_evidence_package(payload)
    assert res["incident_summary"]["incident_id"] == "INC-100"
    assert res["incident_summary"]["stats"]["errors_observed"] == 2
    assert len(res["evidence"]) == 2
    types = {e["type"] for e in res["evidence"]}
    assert "http_request" in types
    assert "timeline_event" in types

def test_3_filtro_por_janela_temporal():
    payload = {
        "time_range": {"from": "2026-08-14T10:00:00Z", "to": "2026-08-14T10:10:00Z"},
        "timeline": [
            {"line": 1, "timestamp": "2026-08-14T09:50:00Z", "message": "Too early"},
            {"line": 2, "timestamp": "2026-08-14T10:05:00Z", "message": "In range"},
            {"line": 3, "timestamp": "2026-08-14T10:20:00Z", "message": "Too late"}
        ]
    }
    res = build_evidence_package(payload)
    assert len(res["evidence"]) == 1
    assert "In range" in res["evidence"][0]["data"]["message"]

def test_4_deduplicacao_de_evidencias():
    payload = {
        "timeline": [
            {"line": 10, "timestamp": "2026-08-14T10:00:00Z", "message": "Identical event"},
            {"line": 10, "timestamp": "2026-08-14T10:00:00Z", "message": "Identical event"}
        ]
    }
    res = build_evidence_package(payload)
    assert len(res["evidence"]) == 1

def test_5_clusters_ingestao_e_referencias():
    payload = {
        "clusters": [
            {
                "template": "Timeout connecting to DB after <DURATION>",
                "count": 15,
                "first_seen": {"line": 104, "message": "2026-08-14T10:00:00Z Timeout connecting to DB after 3000 ms"}
            }
        ]
    }
    res = build_evidence_package(payload)
    assert len(res["evidence"]) == 1
    assert res["evidence"][0]["type"] == "log"
    assert res["evidence"][0]["data"]["frequency"] == 15
    assert len(res["references"]["clusters"]) == 1

def test_6_limite_maximo_e_truncamento():
    payload = {
        "timeline": [
            {"line": i, "timestamp": f"2026-08-14T10:{i:02d}:00Z", "message": f"Event {i}"}
            for i in range(20)
        ]
    }
    res = build_evidence_package(payload, {"max_evidence_items": 5})
    assert len(res["evidence"]) == 5
    assert res["incident_summary"]["stats"]["is_truncated"] is True
    assert len(res["warnings"]) > 0

def test_7_disclaimer_sem_causa_raiz():
    payload = {"incident_info": {"title": "Slowdown"}}
    res = build_evidence_package(payload)
    assert "evidencias" in res["manifest"]["disclaimer"].lower()
    assert "conclusoes" in res["manifest"]["disclaimer"].lower()

def test_8_protocolo_ipc_v1():
    payload = {
        "protocol_version": "1.0",
        "request_id": "req_evidence_01",
        "incident_info": {"id": "INC-555", "service": "payment-gateway"}
    }
    resp = handle_ipc(payload)
    assert resp["status"] == "success"
    assert resp["protocol_version"] == "1.0"
    assert resp["request_id"] == "req_evidence_01"
    assert resp["result"]["manifest"]["incident_id"] == "INC-555"
