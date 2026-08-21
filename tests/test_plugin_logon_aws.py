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
    """Testa leitura e gravação de configurações com profile vazio inicial."""
    temp_config = tmp_path / "config.json"
    monkeypatch.setattr(domain, "CONFIG_FILE", temp_config)

    # Config padrão inicial sem usuário fixo
    cfg = domain.load_config()
    assert cfg["profile"] == ""
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


@patch("subprocess.run")
def test_check_sts_session(mock_run: MagicMock) -> None:
    """Valida checagem de sessão AWS STS com sessão válida e expirada."""
    # 1. Sessão ativa
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='{"UserId": "AROA...", "Account": "123456789012", "Arn": "arn:aws:sts::123456789012:assumed-role/..."}',
        stderr=""
    )
    ok, msg = domain.check_sts_session("rodrigo.lessa")
    assert ok is True
    assert "UserId" in msg

    # 2. Sessão expirada / erro
    mock_run.return_value = MagicMock(
        returncode=254,
        stdout="",
        stderr="The SSO session associated with this profile has expired or is invalid."
    )
    ok, err = domain.check_sts_session("rodrigo.lessa")
    assert ok is False
    assert "expired" in err


@patch("domain.check_sts_session")
@patch.object(domain.AwsTunnelManager, "start_tunnel")
def test_one_click_connect_with_active_session(
    mock_start_tunnel: MagicMock,
    mock_check_sts: MagicMock,
) -> None:
    """Valida que sessão ativa pula o SSO e inicia o túnel diretamente."""
    mock_check_sts.return_value = (True, "Session Active")
    mock_start_tunnel.return_value = {"success": True}

    mgr = domain.AwsTunnelManager()
    res = mgr.one_click_connect("rodrigo.lessa", 42586, "sa-east-1")
    assert res["success"] is True

    # Aguarda a thread do one_click executar
    import time
    time.sleep(0.1)

    mock_check_sts.assert_called_once_with("rodrigo.lessa")
    mock_start_tunnel.assert_called_once_with("rodrigo.lessa", 42586, "sa-east-1")


@patch("domain.check_sts_session")
@patch.object(domain.AwsTunnelManager, "run_sso_login")
def test_one_click_connect_with_expired_session(
    mock_sso_login: MagicMock,
    mock_check_sts: MagicMock,
) -> None:
    """Valida que sessão expirada aciona o fluxo de login SSO com callback."""
    mock_check_sts.return_value = (False, "Expired")
    mock_sso_login.return_value = {"success": True}

    mgr = domain.AwsTunnelManager()
    res = mgr.one_click_connect("rodrigo.lessa", 42586, "sa-east-1")
    assert res["success"] is True

    import time
    time.sleep(0.1)

    mock_check_sts.assert_called_once_with("rodrigo.lessa")
    mock_sso_login.assert_called_once()


def test_cancel_sso_login() -> None:
    """Valida cancelamento do processo de login SSO."""
    mgr = domain.AwsTunnelManager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mgr.sso_process = mock_proc

    res = mgr.cancel_sso_login()
    assert res["success"] is True
    assert mock_proc.terminate.called
    assert mgr.sso_process is None
    assert mgr.current_state == "idle"


@patch("subprocess.Popen")
def test_run_sso_login_browser(mock_popen: MagicMock) -> None:
    """Valida que aws sso login é invocado diretamente para abrir o navegador padrão."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdout = None
    mock_proc.wait.return_value = 0
    mock_popen.return_value = mock_proc

    mgr = domain.AwsTunnelManager()
    mgr.run_sso_login("rodrigo.lessa")
    import time
    time.sleep(0.05)
    cmd_called = mock_popen.call_args[0][0]
    assert cmd_called == ["aws", "sso", "login", "--profile", "rodrigo.lessa"]


def test_status_icon_assets_exist() -> None:
    """Valida que os arquivos .ico conectados e desconectados existem e têm tamanho válido."""
    assert domain.ICON_CONNECTED_PATH.exists(), "icon-connected.ico deve existir"
    assert domain.ICON_DISCONNECTED_PATH.exists(), "icon-disconnected.ico deve existir"
    assert domain.ICON_CONNECTED_PATH.stat().st_size > 1000
    assert domain.ICON_DISCONNECTED_PATH.stat().st_size > 1000


def test_empty_profile_validation_rejects_execution() -> None:
    """Valida que chamadas com profile vazio são rejeitadas com erro amigável."""
    mgr = domain.AwsTunnelManager()
    
    res_sso = mgr.run_sso_login("")
    assert res_sso["success"] is False
    assert "informe seu usuário/profile" in res_sso["error"]

    res_tunnel = mgr.start_tunnel("")
    assert res_tunnel["success"] is False
    assert "informe seu usuário/profile" in res_tunnel["error"]

    res_click = mgr.one_click_connect("")
    assert res_click["success"] is False
    assert "informe seu usuário/profile" in res_click["error"]


def test_set_window_taskbar_icon_win32_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida a rotina de set_window_taskbar_icon com HWND explícito."""
    if sys.platform == "win32":
        # Chama com hwnd mockado/nulo sem lançar exceções
        res = domain.set_window_taskbar_icon(True, hwnd=12345)
        # Pode retornar False se o HWND não for válido no OS real, mas não deve quebrar
        assert isinstance(res, bool)
    else:
        assert domain.set_window_taskbar_icon(True) is False


def test_terminate_process_tree() -> None:
    """Valida que terminate_process_tree lida com processos None ou ativos com segurança."""
    # Com None
    domain.terminate_process_tree(None)

    # Com processo mock
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 99999
    
    with patch("subprocess.run") as mock_run:
        domain.terminate_process_tree(mock_proc)
        mock_proc.terminate.assert_called_once()
        if sys.platform == "win32":
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "taskkill" in args
            assert "99999" in args


def test_stop_all_cleans_active_processes() -> None:
    """Valida que stop_all encerra tanto o processo de túnel quanto o processo de SSO."""
    mgr = domain.AwsTunnelManager()
    mock_t_proc = MagicMock()
    mock_t_proc.poll.return_value = None
    mock_t_proc.pid = 11111

    mock_s_proc = MagicMock()
    mock_s_proc.poll.return_value = None
    mock_s_proc.pid = 22222

    mgr.process = mock_t_proc
    mgr.sso_process = mock_s_proc
    mgr.current_state = "connected"

    with patch("domain.terminate_process_tree") as mock_term, \
         patch("domain.set_window_taskbar_icon") as mock_icon:
        mgr.stop_all()
        assert mock_term.call_count == 2
        assert mgr.process is None
        assert mgr.sso_process is None
        assert mgr.current_state == "idle"
        mock_icon.assert_called_once_with(False)






