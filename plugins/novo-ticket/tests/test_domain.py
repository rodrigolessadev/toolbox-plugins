import sys
from datetime import date, datetime
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
    get_ticket_subdirectories_info,
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
    # Padrão Senior colchetes
    line_senior = "[19-08-2026 10:15:30] INFO: Processo iniciado"
    dt = extract_log_line_timestamp(line_senior)
    assert dt == datetime(2026, 8, 19, 10, 15, 30)

    # Padrão ISO
    line_iso = "2026-08-19 14:20:00.123 [main] ERROR - Falha de conexao"
    dt_iso = extract_log_line_timestamp(line_iso)
    assert dt_iso == datetime(2026, 8, 19, 14, 20, 0)

    # Padrão BR
    line_br = "19/08/2026 09:00:00 WARN Mensagem de aviso"
    dt_br = extract_log_line_timestamp(line_br)
    assert dt_br == datetime(2026, 8, 19, 9, 0, 0)

    # Linha sem timestamp
    assert extract_log_line_timestamp("   at org.hibernate.Session.close(Session.java:123)") is None


def test_extract_log_line_timestamp_wildfly():
    # Log Wildfly (apenas horário no início da linha)
    ref_d = date(2026, 8, 19)
    line_wild = "15:26:53,544 INFO  [br.com.senior.services.mdw.ServiceApplication] Executando serviço..."
    dt_wild = extract_log_line_timestamp(line_wild, reference_date=ref_d)
    assert dt_wild == datetime(2026, 8, 19, 15, 26, 53)

    line_wild_err = "15:26:54,895 ERROR [br.com.senior.services.mdw.ServiceApplication] Ocorreu um erro"
    dt_err = extract_log_line_timestamp(line_wild_err, reference_date=ref_d)
    assert dt_err == datetime(2026, 8, 19, 15, 26, 54)


def test_parse_log_blocks_wildfly():
    ref_d = date(2026, 8, 19)
    sample_log = (
        "15:26:53,544 INFO  [com.senior] Conectado com sucesso.\n"
        "15:26:54,895 ERROR [com.senior] Ocorreu um erro na aplicação servidora\n"
        "Resposta da aplicação: $51=Problemas na inclusão.\n"
    )
    blocks = parse_log_blocks(sample_log, reference_date=ref_d)
    assert len(blocks) == 2
    assert blocks[0]["timestamp"] == datetime(2026, 8, 19, 15, 26, 53)
    assert blocks[1]["timestamp"] == datetime(2026, 8, 19, 15, 26, 54)
    assert len(blocks[1]["lines"]) == 2


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

    count, status = filter_log_file(source, target, start_dt, end_dt)
    assert count == 2
    assert status == "written"
    assert target.exists()

    filtered_content = target.read_text(encoding="utf-8")
    assert "Dentro do range" in filtered_content
    assert "Outro log dentro" in filtered_content
    assert "Fora do range" not in filtered_content


def test_filter_log_file_incremental_skip(tmp_path: Path):
    source = tmp_path / "app.log"
    source.write_text("[19-08-2026 10:15:00] INFO: Log teste\n", encoding="utf-8")

    target = tmp_path / "filtered" / "app.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("conteudo anterior ja processado", encoding="utf-8")

    start_dt = datetime(2026, 8, 19, 10, 0, 0)
    end_dt = datetime(2026, 8, 19, 12, 0, 0)

    # Se overwrite for False, deve ignorar o arquivo
    count, status = filter_log_file(source, target, start_dt, end_dt, overwrite=False)
    assert count == 0
    assert status == "skipped_existing"
    assert target.read_text(encoding="utf-8") == "conteudo anterior ja processado"


def test_get_ticket_subdirectories_info_hierarchy(tmp_path: Path):
    (tmp_path / "LogsSenior_COMPLETO_20260817" / "logs_brutos").mkdir(parents=True)
    (tmp_path / "servicos").mkdir()

    infos = get_ticket_subdirectories_info(tmp_path)
    assert len(infos) == 3

    info_parent = next(i for i in infos if i["path"] == "LogsSenior_COMPLETO_20260817")
    assert info_parent["name"] == "LogsSenior_COMPLETO_20260817"
    assert info_parent["depth"] == 0

    info_child = next(i for i in infos if i["path"] == "LogsSenior_COMPLETO_20260817/logs_brutos")
    assert info_child["name"] == "logs_brutos"
    assert info_child["depth"] == 1
    assert info_child["parent"] == "LogsSenior_COMPLETO_20260817"


def test_process_ticket_logs_incremental_flow(tmp_path: Path):
    ticket_dir = tmp_path / "CLIENTE_TICKET123"
    ticket_dir.mkdir()

    sub_dir = ticket_dir / "LogsSenior" / "logs_brutos"
    sub_dir.mkdir(parents=True)

    # 1. Cria primeiro arquivo
    (sub_dir / "app1.log").write_text(
        "[19-08-2026 10:30:00] INFO: Primeiro arquivo\n", encoding="utf-8"
    )

    start_dt = datetime(2026, 8, 19, 10, 0, 0)
    end_dt = datetime(2026, 8, 19, 12, 0, 0)

    # Primeira execução
    summary1 = process_ticket_logs(
        ticket_dir=ticket_dir,
        selected_subdirs=["LogsSenior/logs_brutos"],
        start_dt=start_dt,
        end_dt=end_dt,
        overwrite=False
    )
    assert summary1["total_files_scanned"] == 1
    assert summary1["total_files_written"] == 1
    assert summary1["total_files_skipped_existing"] == 0

    # 2. Adiciona um segundo arquivo novo na mesma pasta
    (sub_dir / "app2_novo.log").write_text(
        "[19-08-2026 11:00:00] INFO: Segundo arquivo novo\n", encoding="utf-8"
    )

    # Segunda execução: app1.log já existe e deve ser ignorado; apenas app2_novo.log deve ser processado
    summary2 = process_ticket_logs(
        ticket_dir=ticket_dir,
        selected_subdirs=["LogsSenior/logs_brutos"],
        start_dt=start_dt,
        end_dt=end_dt,
        overwrite=False
    )
    assert summary2["total_files_scanned"] == 2
    assert summary2["total_files_written"] == 1
    assert summary2["total_files_skipped_existing"] == 1
    assert (ticket_dir / "logs_filtrados" / "LogsSenior" / "logs_brutos" / "app2_novo.log").exists()
