import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

_plugin_dir = Path(__file__).parent.parent
if str(_plugin_dir.parent) not in sys.path:
    sys.path.insert(0, str(_plugin_dir.parent))
if str(_plugin_dir) not in sys.path:
    sys.path.insert(0, str(_plugin_dir))

_domain_path = _plugin_dir / "domain.py"
_spec_domain = importlib.util.spec_from_file_location("novo_ticket_domain", _domain_path)
domain = importlib.util.module_from_spec(_spec_domain)
_spec_domain.loader.exec_module(domain)

_main_path = _plugin_dir / "main.py"
_spec_main = importlib.util.spec_from_file_location("novo_ticket_main", _main_path)
main_mod = importlib.util.module_from_spec(_spec_main)
_spec_main.loader.exec_module(main_mod)
NovoTicketApi = main_mod.NovoTicketApi


@pytest.fixture(autouse=True)
def isolate_config(tmp_path: Path, monkeypatch):
    """Garante que nenhum teste persista dados em ~/.toolbox/novo_ticket_config.json real."""
    test_cfg = tmp_path / "novo_ticket_test_config.json"
    monkeypatch.setattr(domain, "CONFIG_FILE", test_cfg)
    if hasattr(main_mod, "domain"):
        monkeypatch.setattr(main_mod.domain, "CONFIG_FILE", test_cfg)
    if "domain" in sys.modules and hasattr(sys.modules["domain"], "CONFIG_FILE"):
        monkeypatch.setattr(sys.modules["domain"], "CONFIG_FILE", test_cfg)


def test_format_file_size():
    assert domain.format_file_size(500) == "500 B"
    assert domain.format_file_size(1024) == "1.0 KB"
    assert domain.format_file_size(1536) == "1.5 KB"
    assert domain.format_file_size(1024 * 1024) == "1.0 MB"
    assert domain.format_file_size(5 * 1024 * 1024 + 512 * 1024) == "5.5 MB"
    assert domain.format_file_size(2 * 1024 * 1024 * 1024) == "2.00 GB"


def test_config_load_and_save(tmp_path: Path):
    cfg_file = tmp_path / "custom_config.json"
    
    # 1. Carrega de arquivo inexistente -> default
    initial = domain.load_user_config(cfg_file)
    assert initial == {"base_dir": ""}

    # 2. Salva configuração
    sample_dir = tmp_path / "Atendimentos"
    sample_dir.mkdir()
    success = domain.save_user_config({"base_dir": str(sample_dir), "theme": "dark"}, cfg_file)
    assert success is True
    assert cfg_file.exists()

    # 3. Lê configuração gravada
    loaded = domain.load_user_config(cfg_file)
    assert loaded["base_dir"] == str(sample_dir)
    assert loaded["theme"] == "dark"

    # 4. Lê arquivo com JSON inválido -> fallback seguro
    cfg_file.write_text("INVALID_JSON{", encoding="utf-8")
    fallback = domain.load_user_config(cfg_file)
    assert fallback == {"base_dir": ""}


def test_config_load_clears_nonexistent_directory(tmp_path: Path):
    cfg_file = tmp_path / "deleted_dir_config.json"
    fake_deleted_dir = tmp_path / "non_existent_folder_xyz"
    cfg_file.write_text(json.dumps({"base_dir": str(fake_deleted_dir)}), encoding="utf-8")
    
    loaded = domain.load_user_config(cfg_file)
    assert loaded["base_dir"] == ""


def test_list_ticket_files(tmp_path: Path):
    ticket_dir = tmp_path / "CLIENTE_123"
    ticket_dir.mkdir(parents=True)

    # Cria arquivos de teste
    (ticket_dir / "README.md").write_text("# Ticket 123", encoding="utf-8")
    (ticket_dir / "anotacoes.markdown").write_text("Notas importantes", encoding="utf-8")
    
    sub = ticket_dir / "logs"
    sub.mkdir()
    (sub / "app.log").write_text("2026-08-26 10:00:00 INFO Started", encoding="utf-8")
    (sub / "payload.json").write_text('{"status": "ok"}', encoding="utf-8")

    files = domain.list_ticket_files(ticket_dir)
    names = [f["name"] for f in files]
    assert "README.md" in names
    assert "anotacoes.markdown" in names
    assert "app.log" in names
    assert "payload.json" in names
    assert len(files) == 4


def test_open_ticket_file_validation(tmp_path: Path):
    # Arquivo não fornecido
    res = domain.open_ticket_file("")
    assert res["success"] is False
    assert "não fornecido" in res["message"]

    # Arquivo inexistente
    res2 = domain.open_ticket_file(str(tmp_path / "non_existent.md"))
    assert res2["success"] is False
    assert "não encontrado" in res2["message"]


def test_open_ticket_file_markdown_integration(tmp_path: Path):
    sample_md = tmp_path / "documento.md"
    sample_md.write_text("# Teste MD", encoding="utf-8")

    fake_plugins_root = tmp_path / "plugins"
    mv_dir = fake_plugins_root / "markdown-viewer"
    mv_dir.mkdir(parents=True)
    (mv_dir / "main.py").write_text("# fake markdown viewer", encoding="utf-8")

    with patch("subprocess.Popen") as mock_popen:
        res = domain.open_ticket_file(str(sample_md), plugins_root=fake_plugins_root)
        assert res["success"] is True
        assert res["opened_with"] == "markdown-viewer"
        assert mock_popen.called


def test_novo_ticket_api_files_and_config(tmp_path: Path, monkeypatch):
    test_cfg = tmp_path / "config.json"
    monkeypatch.setattr(domain, "CONFIG_FILE", test_cfg)
    if hasattr(main_mod, "domain"):
        monkeypatch.setattr(main_mod.domain, "CONFIG_FILE", test_cfg)
    if "domain" in sys.modules and hasattr(sys.modules["domain"], "CONFIG_FILE"):
        monkeypatch.setattr(sys.modules["domain"], "CONFIG_FILE", test_cfg)

    api = NovoTicketApi()
    ticket_dir = tmp_path / "SENIOR_999"
    ticket_dir.mkdir()
    (ticket_dir / "resumo.md").write_text("# Resumo", encoding="utf-8")

    # get_config & set_base_dir
    set_res = api.set_base_dir(str(tmp_path))
    assert set_res["success"] is True

    get_res = api.get_config()
    assert get_res["success"] is True
    assert get_res["config"]["base_dir"] == str(tmp_path)
    assert test_cfg.exists()

    # get_ticket_details com arquivos
    details = api.get_ticket_details(str(ticket_dir))
    assert details["success"] is True
    assert "files" in details["ticket"]
    assert len(details["ticket"]["files"]) == 1
    assert details["ticket"]["files"][0]["name"] == "resumo.md"

    # list_ticket_files
    files_res = api.list_ticket_files(str(ticket_dir))
    assert files_res["success"] is True
    assert files_res["count"] == 1
