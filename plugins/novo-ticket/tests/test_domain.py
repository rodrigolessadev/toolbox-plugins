import sys
import importlib.util
from datetime import date, datetime
from pathlib import Path
import pytest

_domain_path = Path(__file__).parent.parent / "domain.py"
_spec = importlib.util.spec_from_file_location("novo_ticket_domain", _domain_path)
domain = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(domain)

sanitize_component = domain.sanitize_component
format_ticket_folder_name = domain.format_ticket_folder_name
validate_base_dir = domain.validate_base_dir
validate_inputs = domain.validate_inputs
create_ticket_directory = domain.create_ticket_directory
get_ticket_subdirectories = domain.get_ticket_subdirectories
get_ticket_subdirectories_info = domain.get_ticket_subdirectories_info
parse_datetime_str = domain.parse_datetime_str
parse_datetime_range = domain.parse_datetime_range
extract_date_from_path = domain.extract_date_from_path
get_file_reference_date = domain.get_file_reference_date
extract_log_line_timestamp = domain.extract_log_line_timestamp
parse_log_blocks = domain.parse_log_blocks
filter_log_file = domain.filter_log_file
process_ticket_logs = domain.process_ticket_logs



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


def test_extract_date_from_path_variations():
    # Padrão YYYYMMDD em pasta pai (exatamente o caso do usuário)
    p1 = Path(r"C:\Downloads\LogsSenior_COMPLETO_20260817\logs_brutos\server.log")
    assert extract_date_from_path(p1) == date(2026, 8, 17)

    # Padrão ISO no nome do arquivo
    p2 = Path(r"C:\logs\server_2026-08-15.log")
    assert extract_date_from_path(p2) == date(2026, 8, 15)

    # Padrão BR no nome do arquivo
    p3 = Path(r"C:\logs\app_19-08-2026.log")
    assert extract_date_from_path(p3) == date(2026, 8, 19)

    # Sem data no caminho
    p4 = Path(r"C:\logs\server.log")
    assert extract_date_from_path(p4) is None


def test_get_file_reference_date_cascade(tmp_path: Path):
    # 1. Caminho tem data
    file_with_date = tmp_path / "Logs_20260817" / "server.log"
    file_with_date.parent.mkdir(parents=True)
    file_with_date.write_text("log", encoding="utf-8")

    assert get_file_reference_date(file_with_date) == date(2026, 8, 17)

    # 2. Caminho sem data, mas passa fallback_date
    file_no_date = tmp_path / "server.log"
    file_no_date.write_text("log", encoding="utf-8")

    # Passando fallback explícito
    fb = date(2026, 8, 10)
    # Quando não há data no caminho, usa mtime se disponível ou fallback
    ref_d = get_file_reference_date(file_no_date, fallback_date=fb)
    assert isinstance(ref_d, date)


def test_extract_log_line_timestamp():
    line_senior = "[19-08-2026 10:15:30] INFO: Processo iniciado"
    dt = extract_log_line_timestamp(line_senior)
    assert dt == datetime(2026, 8, 19, 10, 15, 30)

    line_iso = "2026-08-19 14:20:00.123 [main] ERROR - Falha de conexao"
    dt_iso = extract_log_line_timestamp(line_iso)
    assert dt_iso == datetime(2026, 8, 19, 14, 20, 0)

    line_br = "19/08/2026 09:00:00 WARN Mensagem de aviso"
    dt_br = extract_log_line_timestamp(line_br)
    assert dt_br == datetime(2026, 8, 19, 9, 0, 0)

    assert extract_log_line_timestamp("   at org.hibernate.Session.close(Session.java:123)") is None


def test_extract_log_line_timestamp_wildfly():
    ref_d = date(2026, 8, 17)
    line_wild = "15:26:53,544 INFO  [br.com.senior.services.mdw.ServiceApplication] Executando serviço..."
    dt_wild = extract_log_line_timestamp(line_wild, reference_date=ref_d)
    assert dt_wild == datetime(2026, 8, 17, 15, 26, 53)

    line_wild_err = "15:26:54,895 ERROR [br.com.senior.services.mdw.ServiceApplication] Ocorreu um erro"
    dt_err = extract_log_line_timestamp(line_wild_err, reference_date=ref_d)
    assert dt_err == datetime(2026, 8, 17, 15, 26, 54)


def test_filter_log_file_wildfly_with_path_date(tmp_path: Path):
    # Simula exatamente a estrutura do usuário extraída de ZIP
    wild_dir = tmp_path / "LogsSenior_COMPLETO_20260817" / "logs_brutos" / "VOLANS400-WildFly"
    wild_dir.mkdir(parents=True)
    source = wild_dir / "server.log"

    source.write_text(
        "15:26:53,544 INFO  [br.com.senior.services] Executando servico A\n"
        "15:26:54,895 ERROR [br.com.senior.services] Ocorreu um erro\n"
        "16:30:00,000 INFO  [br.com.senior.services] Fora do horario\n",
        encoding="utf-8"
    )

    target = tmp_path / "filtered" / "server.log"
    # Filtro para o dia 17/08/2026 entre 15:00 e 16:00
    start_dt = datetime(2026, 8, 17, 15, 0, 0)
    end_dt = datetime(2026, 8, 17, 16, 0, 0)

    count, status = filter_log_file(source, target, start_dt, end_dt)
    assert count == 2
    assert status == "written"
    assert target.exists()

    filtered_content = target.read_text(encoding="utf-8")
    assert "Executando servico A" in filtered_content
    assert "Ocorreu um erro" in filtered_content
    assert "Fora do horario" not in filtered_content


def test_filter_log_file_incremental_skip(tmp_path: Path):
    source = tmp_path / "app.log"
    source.write_text("[19-08-2026 10:15:00] INFO: Log teste\n", encoding="utf-8")

    target = tmp_path / "filtered" / "app.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("conteudo anterior ja processado", encoding="utf-8")

    start_dt = datetime(2026, 8, 19, 10, 0, 0)
    end_dt = datetime(2026, 8, 19, 12, 0, 0)

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
