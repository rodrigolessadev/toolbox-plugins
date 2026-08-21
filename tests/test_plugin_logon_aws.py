"""Testes unitários para o plugin Logon AWS & Port Forwarding.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sys

ROOT = Path(__file__).parent.parent
PLUGIN_DIR = ROOT / "plugins" / "logon-aws"
sys.path.insert(0, str(PLUGIN_DIR))

import domain


def test_logon_aws_config_load_and_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Testa leitura e gravação de configurações."""
    temp_config = tmp_path / "config.json"
    monkeypatch.setattr(domain, "CONFIG_FILE", temp_config)

    # Config padrão inicial
    cfg = domain.load_config()
    assert cfg["profile"] == "default"
    assert cfg["local_port"] == 5432

    # Salva customização
    domain.save_config({"profile": "prod-admin", "local_port": 5433})
    saved = domain.load_config()
    assert saved["profile"] == "prod-admin"
    assert saved["local_port"] == 5433


def test_is_port_open_invalid_ports() -> None:
    """Valida que portas inválidas retornam False sem exceção."""
    assert domain.is_port_open(0) is False
    assert domain.is_port_open(-1) is False
    assert domain.is_port_open(70000) is False


def test_aws_tunnel_manager_logs() -> None:
    """Valida manipulação do histórico de logs."""
    mgr = domain.AwsTunnelManager()
    mgr.clear_logs()
    mgr.append_log("Mensagem de teste 1")
    mgr.append_log("Mensagem de teste 2")

    logs = mgr.get_logs()
    assert len(logs) == 2
    assert "Mensagem de teste 1" in logs[0]
    assert "Mensagem de teste 2" in logs[1]

    mgr.clear_logs()
    assert len(mgr.get_logs()) == 0


@patch("subprocess.Popen")
def test_aws_tunnel_manager_start_and_stop(mock_popen: MagicMock) -> None:
    """Testa inicialização e encerramento de processos de túnel com mock."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.wait.return_value = 0
    mock_popen.return_value = mock_proc

    mgr = domain.AwsTunnelManager()
    # Simula processo ativo
    mgr.process = mock_proc

    # Bloqueia iniciar túnel duplicado
    res2 = mgr.start_tunnel(profile="staging", local_port=5432)
    assert res2["success"] is False
    assert "Já existe um túnel ativo" in res2["error"]

    # Encerra túnel
    res_stop = mgr.stop_tunnel()
    assert res_stop["success"] is True
    assert mock_proc.terminate.called
    assert mgr.process is None
