import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain import (
    sanitize_component,
    format_ticket_folder_name,
    validate_base_dir,
    validate_inputs,
    create_ticket_directory,
)


def test_sanitize_component():
    assert sanitize_component("cliente teste") == "CLIENTE TESTE"
    assert sanitize_component("  cliente/empresa:1  ") == "CLIENTE_EMPRESA_1"
    assert sanitize_component("ticket?*<>|") == "TICKET"
    assert sanitize_component("...nome...") == "NOME"
    assert sanitize_component("   ___   ") == ""
    assert sanitize_component("") == ""


def test_format_ticket_folder_name_valid():
    assert format_ticket_folder_name("acme", "12345") == "ACME_12345"
    assert format_ticket_folder_name("Cliente X", "INC-9876") == "CLIENTE X_INC-9876"
    assert format_ticket_folder_name("empresa: filial", "tk#01") == "EMPRESA_FILIAL_TK#01"


def test_format_ticket_folder_name_invalid():
    with pytest.raises(ValueError, match="Cliente"):
        format_ticket_folder_name("", "12345")

    with pytest.raises(ValueError, match="Cliente"):
        format_ticket_folder_name("   ???   ", "12345")

    with pytest.raises(ValueError, match="Ticket"):
        format_ticket_folder_name("ACME", "")

    with pytest.raises(ValueError, match="Ticket"):
        format_ticket_folder_name("ACME", "  :::  ")


def test_validate_base_dir(tmp_path: Path):
    # Diretório válido
    is_valid, msg, path = validate_base_dir(str(tmp_path))
    assert is_valid is True
    assert msg == ""
    assert path == tmp_path

    # Diretório vazio
    is_valid, msg, path = validate_base_dir("")
    assert is_valid is False
    assert "especificado" in msg

    # Diretório inexistente
    non_existent = tmp_path / "nao_existe"
    is_valid, msg, path = validate_base_dir(str(non_existent))
    assert is_valid is False
    assert "não existe" in msg

    # Arquivo em vez de pasta
    file_path = tmp_path / "arquivo.txt"
    file_path.write_text("teste", encoding="utf-8")
    is_valid, msg, path = validate_base_dir(str(file_path))
    assert is_valid is False
    assert "não é um diretório" in msg


def test_validate_inputs(tmp_path: Path):
    # Sucesso
    is_valid, msg, target = validate_inputs(str(tmp_path), "ACME", "100")
    assert is_valid is True
    assert target == tmp_path / "ACME_100"

    # Conflito: diretório já existe
    existing_dir = tmp_path / "ACME_100"
    existing_dir.mkdir()
    is_valid, msg, target = validate_inputs(str(tmp_path), "ACME", "100")
    assert is_valid is False
    assert "já existe" in msg


def test_create_ticket_directory_success(tmp_path: Path):
    success, msg, target = create_ticket_directory(str(tmp_path), "empresa a", "ticket-01")
    assert success is True
    assert target is not None
    assert target.exists()
    assert target.is_dir()
    assert target.name == "EMPRESA A_TICKET-01"
    assert "criado com sucesso" in msg


def test_create_ticket_directory_conflict(tmp_path: Path):
    target = tmp_path / "EMPRESA B_999"
    target.mkdir()

    success, msg, path = create_ticket_directory(str(tmp_path), "empresa b", "999")
    assert success is False
    assert "já existe" in msg