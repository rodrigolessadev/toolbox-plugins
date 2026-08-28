"""
Testes unitários centralizados para o plugin Novo-ticket.
Valida inicialização, manipulação de configurações, isolamento do CONFIG_FILE e sanitização defensiva.
"""

import json
import sys
from pathlib import Path
import pytest

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

NOVO_TICKET_DIR = PLUGINS_DIR / "novo-ticket"
if str(NOVO_TICKET_DIR) not in sys.path:
    sys.path.insert(0, str(NOVO_TICKET_DIR))

import domain as novo_ticket_domain
import main as novo_ticket_main


@pytest.fixture(autouse=True)
def isolate_config(tmp_path: Path, monkeypatch):
    """Garante que nenhum teste persista dados em ~/.toolbox/novo_ticket_config.json real."""
    test_cfg = tmp_path / "novo_ticket_test_config.json"
    monkeypatch.setattr(novo_ticket_domain, "CONFIG_FILE", test_cfg)
    if hasattr(novo_ticket_main, "domain"):
        monkeypatch.setattr(novo_ticket_main.domain, "CONFIG_FILE", test_cfg)
    if "domain" in sys.modules and hasattr(sys.modules["domain"], "CONFIG_FILE"):
        monkeypatch.setattr(sys.modules["domain"], "CONFIG_FILE", test_cfg)


def test_novo_ticket_default_config_empty(tmp_path: Path):
    """Garante que quando não há configuração salva, o base_dir retornado é vazio."""
    cfg_file = tmp_path / "empty_cfg.json"
    data = novo_ticket_domain.load_user_config(cfg_file)
    assert data == {"base_dir": ""}


def test_novo_ticket_nonexistent_directory_cleared(tmp_path: Path):
    """Garante que diretórios que não existem no disco (ex.: temporários de testes) são limpos."""
    cfg_file = tmp_path / "ghost_cfg.json"
    ghost_dir = tmp_path / "deleted_pytest_dir_12345"
    cfg_file.write_text(json.dumps({"base_dir": str(ghost_dir)}), encoding="utf-8")

    data = novo_ticket_domain.load_user_config(cfg_file)
    assert data["base_dir"] == ""


def test_novo_ticket_valid_directory_retained(tmp_path: Path):
    """Garante que diretórios válidos e existentes são preservados."""
    cfg_file = tmp_path / "valid_cfg.json"
    valid_dir = tmp_path / "real_tickets"
    valid_dir.mkdir()
    cfg_file.write_text(json.dumps({"base_dir": str(valid_dir)}), encoding="utf-8")

    data = novo_ticket_domain.load_user_config(cfg_file)
    assert data["base_dir"] == str(valid_dir)


def test_novo_ticket_api_isolated_config_workflow(tmp_path: Path):
    """Valida ciclo completo get_config / set_base_dir na API."""
    api = novo_ticket_main.NovoTicketApi()
    
    # 1. get_config inicial
    res_get = api.get_config()
    assert res_get["success"] is True
    assert res_get["config"]["base_dir"] == ""

    # 2. set_base_dir
    tickets_dir = tmp_path / "MeusTickets"
    tickets_dir.mkdir()
    res_set = api.set_base_dir(str(tickets_dir))
    assert res_set["success"] is True

    # 3. get_config subsequente
    res_get2 = api.get_config()
    assert res_get2["success"] is True
    assert res_get2["config"]["base_dir"] == str(tickets_dir)
