"""Testes unitários para o plugin Logon AWS & Port Forwarding (Issue #67).
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

    # Config padrão inicial com valores corporativos
    cfg = domain.load_config()
    assert cfg["profile"] == "rodrigo.lessa"
    assert cfg["local_port"] == 42586

    # Salva customização
    domain.save_config({"profile": "prod-admin", "local_port": 5433})
    saved = domain.load_config()
    assert saved["profile"] == "prod-admin"
    assert saved["local_port"] == 5433


def test_initial_status_is_disconnected_even_if_port_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida que sem processo ativo o status é sempre desconectado ao abrir o plugin."""
    mgr = domain.AwsTunnelManager()
    mgr.process = None

    # Simula porta aberta no sistema operacional por outro serviço
    monkeypatch.setattr(domain, "is_port_open", lambda port, host="127.0.0.1", timeout=0.6: True)

    status = mgr.get_status(42586)
    assert status["connected"] is False
    assert status["process_running"] is False


@patch("subprocess.run")
def test_discover_ec2_target(mock_run: MagicMock) -> None:
    """Testa busca automática de instância EC2 em sa-east-1."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="i-0123456789abcdef0\n",
        stderr=""
    )

    ok, inst_id = domain.discover_ec2_target("rodrigo.lessa", "sa-east-1")
    assert ok is True
    assert inst_id == "i-0123456789abcdef0"


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
    # Inicia com target fixo mockado
    res = mgr.start_tunnel(profile="rodrigo.lessa", local_port=42586, target_instance_id="i-mocked123")
    assert res["success"] is True
    assert res["instance_id"] == "i-mocked123"

    # Bloqueia iniciar túnel duplicado
    res2 = mgr.start_tunnel(profile="rodrigo.lessa", local_port=42586)
    assert res2["success"] is False
    assert "Já existe um túnel ativo" in res2["error"]

    # Encerra túnel
    res_stop = mgr.stop_tunnel()
    assert res_stop["success"] is True
    assert mock_proc.terminate.called
    assert mgr.process is None
