import sys
from datetime import datetime
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain import (
    sanitize_component,
    format_ticket_folder_name,
    validate_base_dir,
    validate_inputs,
    create_ticket_directory,
    get_ticket_subdirectories,
    parse_datetime_str,
    parse_datetime_range,
    extract_log_line_timestamp,
    parse_log_blocks,
    filter_log_file,
    process_ticket_logs,
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
    is_valid, msg, path = validate_base_dir(str(tmp_path))
    assert is_valid is True
    assert msg == ""
    assert path == tmp_path

    is_valid, msg, path = validate_base_dir("")
    assert is_valid is False
    assert "especificado" in msg

    non_existent = tmp_path / "nao_existe"
    is_valid, msg, path = validate_base_dir(str(non_existent))
    assert is_valid is False
    assert "não existe" in msg


def test_create_ticket_directory_success(tmp_path: Path):
    success, msg, target = create_ticket_directory(str(tmp_path), "empresa a", "ticket-01")
    assert success is True
    assert target is not None
    assert target.exists()
    assert target.is_dir()
    assert target.name == "EMPRESA A_TICKET-01"


def test_parse_datetime_str():
    dt1 = parse_datetime_str("2026-08-19", "10:30")
    assert dt1 == datetime(2026, 8, 19, 10, 30, 0)

    dt2 = parse_datetime_str("19/08/2026", "14:45:10")
    assert dt2 == datetime(2026, 8, 19, 14, 45, 10)

    dt3 = parse_datetime_str("19-08-2026", "08:00")
    assert dt3 == datetime(2026, 8, 19, 8, 0, 0)

    with pytest.raises(ValueError):
        parse_datetime_str("data-invalida", "10:00")


def test_parse_datetime_range():
    start_dt, end_dt = parse_datetime_range("2026-08-19", "08:00", "2026-08-19", "18:00")
    assert start_dt == datetime(2026, 8, 19, 8, 0, 0)
    assert end_dt.hour == 18
    assert end_dt.minute == 0

    with pytest.raises(ValueError, match="não pode ser maior"):
        parse_datetime_range("2026-08-20", "10:00", "2026-08-19", "10:00")


def test_extract_log_line_timestamp():
    # Senior colchetes
    line_senior = "[19-08-2026 10:15:30] INFO: Processo iniciado"
    dt = extract_log_line_timestamp(line_senior)
    assert dt == datetime(2026, 8, 19, 10, 15, 30)

    # ISO
    line_iso = "2026-08-19 14:20:00.123 [main] ERROR - Falha de conexao"
    dt_iso = extract_log_line_timestamp(line_iso)
    assert dt_iso == datetime(2026, 8, 19, 14, 20, 0)

    # BR
    line_br = "19/08/2026 09:00:00 WARN Mensagem de aviso"
    dt_br = extract_log_line_timestamp(line_br)
    assert dt_br == datetime(2026, 8, 19, 9, 0, 0)

    # Sem timestamp
    assert extract_log_line_timestamp("   at org.hibernate.Session.close(Session.java:123)") is None


def test_parse_log_blocks():
    sample_log = (
        "[19-08-2026 10:00:00] INFO: Inicio do processamento\n"
        "Parametro A = 123\n"
        "Parametro B = 456\n"
        "[19-08-2026 10:05:00] ERROR: NullPointerException\n"
        "\tat com.example.Service.run(Service.java:42)\n"
        "\tat com.example.Main.main(Main.java:10)\n"
    )
    blocks = parse_log_blocks(sample_log)
    assert len(blocks) == 2
    assert blocks[0]["timestamp"] == datetime(2026, 8, 19, 10, 0, 0)
    assert len(blocks[0]["lines"]) == 3
    assert blocks[1]["timestamp"] == datetime(2026, 8, 19, 10, 5, 0)
    assert len(blocks[1]["lines"]) == 3


def test_filter_log_file_with_matches(tmp_path: Path):
    source = tmp_path / "app.log"
    source.write_text(
        "[19-08-2026 08:00:00] INFO: Fora do range (antes)\n"
        "[19-08-2026 10:15:00] INFO: Dentro do range\n"
        "Detalhes da operacao...\n"
        "[19-08-2026 11:30:00] ERROR: Outro log dentro\n"
        "[19-08-2026 14:00:00] INFO: Fora do range (depois)\n",
        encoding="utf-8"
    )
    target = tmp_path / "filtered" / "app.log"
    start_dt = datetime(2026, 8, 19, 10, 0, 0)
    end_dt = datetime(2026, 8, 19, 12, 0, 0)

    count = filter_log_file(source, target, start_dt, end_dt)
    assert count == 2
    assert target.exists()

    filtered_content = target.read_text(encoding="utf-8")
    assert "Dentro do range" in filtered_content
    assert "Outro log dentro" in filtered_content
    assert "Fora do range" not in filtered_content


def test_filter_log_file_no_matches_ignored(tmp_path: Path):
    source = tmp_path / "outdated.log"
    source.write_text(
        "[18-08-2026 08:00:00] INFO: Log de ontem\n",
        encoding="utf-8"
    )
    target = tmp_path / "filtered" / "outdated.log"
    start_dt = datetime(2026, 8, 19, 10, 0, 0)
    end_dt = datetime(2026, 8, 19, 12, 0, 0)

    count = filter_log_file(source, target, start_dt, end_dt)
    assert count == 0
    # O arquivo NAO deve ser criado
    assert not target.exists()


def test_get_ticket_subdirectories(tmp_path: Path):
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()
    (tmp_path / "logs_filtrados").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "arquivo.txt").write_text("txt", encoding="utf-8")

    subdirs = get_ticket_subdirectories(tmp_path)
    assert subdirs == ["sub1", "sub2"]


def test_process_ticket_logs_full_flow(tmp_path: Path):
    ticket_dir = tmp_path / "CLIENTE_TICKET123"
    ticket_dir.mkdir()

    sub_integrador = ticket_dir / "integrador"
    sub_integrador.mkdir()
    (sub_integrador / "sync.log").write_text(
        "[19-08-2026 10:30:00] INFO: Sincronismo efetuado\n"
        "[19-08-2026 11:00:00] INFO: Fim do lote\n",
        encoding="utf-8"
    )
    (sub_integrador / "old.log").write_text(
        "[10-08-2026 08:00:00] INFO: Registro antigo\n",
        encoding="utf-8"
    )

    sub_server = ticket_dir / "server"
    sub_server.mkdir()
    (sub_server / "server.log").write_text(
        "[19-08-2026 10:45:00] ERROR: Request timeout\n"
        "\tat server.handle(server.java:10)\n",
        encoding="utf-8"
    )

    start_dt = datetime(2026, 8, 19, 10, 0, 0)
    end_dt = datetime(2026, 8, 19, 12, 0, 0)

    summary = process_ticket_logs(
        ticket_dir=ticket_dir,
        selected_subdirs=["integrador", "server"],
        start_dt=start_dt,
        end_dt=end_dt
    )

    assert summary["total_files_scanned"] == 3
    assert summary["total_files_written"] == 2
    assert summary["total_blocks_kept"] == 3

    # Verifica estrutura de diretórios criada
    out_dir = ticket_dir / "logs_filtrados"
    assert out_dir.exists()
    assert (out_dir / "integrador" / "sync.log").exists()
    assert not (out_dir / "integrador" / "old.log").exists()
    assert (out_dir / "server" / "server.log").exists()