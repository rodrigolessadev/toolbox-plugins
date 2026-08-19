"""
Módulo de regras de negócio para o plugin Novo Ticket.
Contém funções puras e testáveis para:
1. Sanitização, validação e criação de diretórios de tickets (CLIENTE_TICKET).
2. Detecção e listagem recursiva (multinível) de subpastas do ticket.
3. Parsing de timestamps e blocos de arquivos de log.
4. Filtragem temporal e cópia espelhada para pasta logs_filtrados.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Caracteres inválidos para nomes de arquivos e pastas no Windows: \ / : * ? " < > |
INVALID_CHARS_REGEX = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

# Expressões regulares para captura de timestamps em arquivos de log
# 1. Padrão colchetes: [DD-MM-YYYY HH:MM:SS] ou [DD/MM/YYYY HH:MM:SS] ou [YYYY-MM-DD HH:MM:SS]
RE_BRACKETS_TS = re.compile(
    r"\[(\d{2,4}[-/]\d{2}[-/]\d{2,4}[\sT]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]"
)

# 2. Padrão ISO 8601: 2026-08-19 10:15:30 ou 2026-08-19T10:15:30
RE_ISO_TS = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b"
)

# 3. Padrão Brasileiro/Europeu: 19/08/2026 10:15:30 ou 19-08-2026 10:15:30
RE_BR_TS = re.compile(
    r"\b(\d{2}[-/]\d{2}[-/]\d{4}\s+\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\b"
)


# ---------------------------------------------------------------------------
# 1. Gestão de Nomes e Pastas de Ticket
# ---------------------------------------------------------------------------

def sanitize_component(name: str) -> str:
    """
    Sanitiza uma parte do nome (Cliente ou Ticket):
    - Substitui caracteres proibidos no Windows por '_'
    - Remove espaços ao redor de underscores
    - Substitui múltiplos espaços por um espaço simples
    - Compacta múltiplos underscores consecutivos
    - Remove pontos, espaços e underscores das pontas
    - Converte para maiúsculas (UPPERCASE)
    """
    if not name:
        return ""

    cleaned = INVALID_CHARS_REGEX.sub("_", name)
    cleaned = re.sub(r"\s*_\s*", "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip(". _")

    return cleaned.upper()


def format_ticket_folder_name(cliente: str, ticket: str) -> str:
    """
    Formata o nome da pasta do ticket no padrão CLIENTE_TICKET em maiúsculas.
    Gera ValueError se cliente ou ticket forem vazios após sanitização.
    """
    clean_cliente = sanitize_component(cliente)
    clean_ticket = sanitize_component(ticket)

    if not clean_cliente:
        raise ValueError("O campo 'Cliente' é obrigatório e deve conter caracteres válidos.")
    if not clean_ticket:
        raise ValueError("O campo 'Ticket' é obrigatório e deve conter caracteres válidos.")

    return f"{clean_cliente}_{clean_ticket}"


def validate_base_dir(base_dir_str: str) -> Tuple[bool, str, Optional[Path]]:
    """
    Valida a existência e permissão de escrita do diretório inicial.
    """
    if not base_dir_str or not base_dir_str.strip():
        return False, "O diretório inicial deve ser especificado.", None

    base_path = Path(base_dir_str.strip()).resolve()

    if not base_path.exists():
        return False, f"O diretório inicial não existe: {base_path}", None

    if not base_path.is_dir():
        return False, f"O caminho especificado não é um diretório: {base_path}", None

    if not os.access(str(base_path), os.W_OK):
        return False, f"Sem permissão de escrita no diretório: {base_path}", None

    return True, "", base_path


def validate_inputs(
    base_dir_str: str, cliente: str, ticket: str
) -> Tuple[bool, str, Optional[Path]]:
    """
    Valida todos os campos necessários e verifica se a pasta de destino já existe.
    Retorna (is_valid, mensagem_erro_ou_ok, target_path).
    """
    is_valid_dir, dir_err, base_path = validate_base_dir(base_dir_str)
    if not is_valid_dir or base_path is None:
        return False, dir_err, None

    try:
        folder_name = format_ticket_folder_name(cliente, ticket)
    except ValueError as ex:
        return False, str(ex), None

    target_path = base_path / folder_name

    if target_path.exists():
        return False, f"O diretório de destino já existe: {folder_name}", target_path

    return True, "", target_path


def create_ticket_directory(
    base_dir_str: str, cliente: str, ticket: str
) -> Tuple[bool, str, Optional[Path]]:
    """
    Executa a criação segura do diretório do ticket.
    Retorna (sucesso, mensagem, target_path).
    """
    is_valid, err_msg, target_path = validate_inputs(base_dir_str, cliente, ticket)
    if not is_valid or target_path is None:
        return False, err_msg, target_path

    try:
        target_path.mkdir(parents=False, exist_ok=False)
        return True, f"Diretório '{target_path.name}' criado com sucesso!", target_path
    except FileExistsError:
        return False, f"O diretório já existe: {target_path.name}", target_path
    except PermissionError:
        return False, f"Permissão negada ao criar o diretório: {target_path}", None
    except OSError as ex:
        return False, f"Erro ao criar o diretório: {ex}", None


def get_ticket_subdirectories(ticket_dir: Path, output_folder_name: str = "logs_filtrados") -> List[str]:
    """
    Retorna recursivamente a lista de caminhos relativos de TODOS os níveis de subdiretórios
    presentes dentro da pasta do ticket.
    Ignora a pasta de saída de logs filtrados e pastas ocultas em qualquer nível.
    """
    if not ticket_dir.exists() or not ticket_dir.is_dir():
        return []

    subdirs = []
    ticket_resolved = ticket_dir.resolve()

    for root, dirs, _ in os.walk(str(ticket_resolved)):
        # Filtra diretórios ocultos e a pasta output_folder_name in-place para não descer nelas
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d.lower() != output_folder_name.lower()
        ]

        current_path = Path(root).resolve()
        if current_path == ticket_resolved:
            continue

        try:
            rel_path = current_path.relative_to(ticket_resolved)
            # Usa barras normais para apresentação consistente
            rel_str = str(rel_path).replace("\\", "/")
            if output_folder_name not in rel_str.split("/"):
                subdirs.append(rel_str)
        except Exception:
            continue

    return sorted(subdirs, key=lambda s: s.lower())


def get_ticket_subdirectories_info(ticket_dir: Path, output_folder_name: str = "logs_filtrados") -> List[Dict[str, Any]]:
    """
    Retorna a lista estruturada de subpastas com metadados:
    [
        {
            "path": "servicos/integrador",
            "log_count": 3,
            "has_logs": True
        }, ...
    ]
    """
    subdirs = get_ticket_subdirectories(ticket_dir, output_folder_name)
    results = []

    for rel_path in subdirs:
        full_path = ticket_dir / Path(rel_path)
        log_count = 0
        try:
            if full_path.exists() and full_path.is_dir():
                log_count = sum(1 for f in full_path.iterdir() if f.is_file() and f.suffix.lower() == ".log")
        except Exception:
            pass

        results.append({
            "path": rel_path,
            "log_count": log_count,
            "has_logs": log_count > 0,
        })

    return results


# ---------------------------------------------------------------------------
# 2. Parsing de Datas e Timestamps de Log
# ---------------------------------------------------------------------------

def parse_datetime_str(date_str: str, time_str: str = "00:00:00") -> datetime:
    """
    Converte pares de strings (data e hora) para objeto datetime.
    Formatos aceitos de data: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY.
    Formatos aceitos de hora: HH:MM, HH:MM:SS.
    """
    d_clean = date_str.strip()
    t_clean = time_str.strip() if time_str else "00:00:00"

    if len(t_clean.split(":")) == 2:
        t_clean += ":00"

    for fmt_d in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(f"{d_clean} {t_clean}", f"{fmt_d} %H:%M:%S")
        except ValueError:
            continue

    raise ValueError(f"Formato de data inválido: '{date_str}'. Use AAAA-MM-DD ou DD/MM/AAAA.")


def parse_datetime_range(
    dt_ini_str: str, tm_ini_str: str, dt_fim_str: str, tm_fim_str: str
) -> Tuple[datetime, datetime]:
    """
    Valida e converte o intervalo inicial e final.
    Garante que dt_inicio <= dt_fim.
    """
    if not dt_ini_str or not dt_ini_str.strip():
        raise ValueError("A Data Inicial é obrigatória.")
    if not dt_fim_str or not dt_fim_str.strip():
        raise ValueError("A Data Final é obrigatória.")

    start_dt = parse_datetime_str(dt_ini_str, tm_ini_str or "00:00")
    end_dt = parse_datetime_str(dt_fim_str, tm_fim_str or "23:59:59")

    if tm_fim_str and len(tm_fim_str.strip().split(":")) == 2:
        end_dt = end_dt.replace(second=59, microsecond=999999)

    if start_dt > end_dt:
        raise ValueError(
            f"Data/hora inicial ({start_dt.strftime('%d/%m/%Y %H:%M')}) não pode ser maior que a final ({end_dt.strftime('%d/%m/%Y %H:%M')})."
        )

    return start_dt, end_dt


def extract_timestamp_from_string(raw_ts: str) -> Optional[datetime]:
    """
    Converte uma string contendo timestamp para datetime.
    """
    clean_ts = raw_ts.strip().replace("T", " ")
    clean_ts = re.sub(r"(?:Z|[+-]\d{2}:?\d{2})$", "", clean_ts).strip()
    clean_ts = re.sub(r"[.,]\d+", "", clean_ts).strip()

    for fmt in (
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(clean_ts, fmt)
        except ValueError:
            continue

    return None


def extract_log_line_timestamp(line: str) -> Optional[datetime]:
    """
    Detecta e extrai o timestamp de uma linha de log.
    Retorna datetime se encontrado, ou None.
    """
    if not line:
        return None

    m_bracket = RE_BRACKETS_TS.search(line)
    if m_bracket:
        dt = extract_timestamp_from_string(m_bracket.group(1))
        if dt:
            return dt

    m_iso = RE_ISO_TS.search(line)
    if m_iso:
        dt = extract_timestamp_from_string(m_iso.group(1))
        if dt:
            return dt

    m_br = RE_BR_TS.search(line)
    if m_br:
        dt = extract_timestamp_from_string(m_br.group(1))
        if dt:
            return dt

    return None


# ---------------------------------------------------------------------------
# 3. Processamento e Filtragem de Arquivos de Log
# ---------------------------------------------------------------------------

def read_file_safely(file_path: Path) -> str:
    """
    Lê o conteúdo de um arquivo de texto testando múltiplos encodings.
    """
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        except Exception:
            break
    return file_path.read_text(encoding="utf-8", errors="replace")


def parse_log_blocks(content: str) -> List[Dict[str, Any]]:
    """
    Divide o texto do log em blocos lógicos estruturados.
    Cada bloco contém o timestamp da linha de cabeçalho e todas as suas linhas de continuação.
    """
    lines = content.splitlines()
    blocks: List[Dict[str, Any]] = []
    current_block: Optional[Dict[str, Any]] = None

    for line in lines:
        ts = extract_log_line_timestamp(line)
        if ts is not None:
            if current_block is not None:
                blocks.append(current_block)
            current_block = {
                "timestamp": ts,
                "lines": [line],
            }
        else:
            if current_block is not None:
                current_block["lines"].append(line)
            else:
                current_block = {
                    "timestamp": None,
                    "lines": [line],
                }

    if current_block is not None:
        blocks.append(current_block)

    return blocks


def filter_log_file(
    source_file: Path, target_file: Path, start_dt: datetime, end_dt: datetime
) -> int:
    """
    Filtra os blocos do arquivo source_file dentro do intervalo [start_dt, end_dt].
    Se houver blocos no intervalo, grava em target_file e retorna a quantidade de blocos mantidos.
    Se NÃO houver nenhum bloco no intervalo, o arquivo NÃO é criado/gravado e retorna 0.
    """
    content = read_file_safely(source_file)
    if not content or not content.strip():
        return 0

    blocks = parse_log_blocks(content)
    kept_blocks: List[Dict[str, Any]] = []

    for block in blocks:
        ts = block.get("timestamp")
        if ts is not None:
            if start_dt <= ts <= end_dt:
                kept_blocks.append(block)

    if not kept_blocks:
        return 0

    target_file.parent.mkdir(parents=True, exist_ok=True)
    output_lines = []
    for b in kept_blocks:
        output_lines.extend(b["lines"])

    target_file.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return len(kept_blocks)


def process_ticket_logs(
    ticket_dir: Path,
    selected_subdirs: List[str],
    start_dt: datetime,
    end_dt: datetime,
    output_folder_name: str = "logs_filtrados",
) -> Dict[str, Any]:
    """
    Orquestra a leitura e filtragem de todas as subpastas selecionadas do ticket (em qualquer nível):
    - Cria a pasta 'logs_filtrados' dentro de ticket_dir.
    - Para cada subpasta selecionada, lê os arquivos .log e salva os blocos no intervalo.
    - Se o arquivo não contiver logs no intervalo, ele é ignorado.
    Retorna sumário estatístico da operação.
    """
    if not ticket_dir.exists() or not ticket_dir.is_dir():
        raise ValueError(f"A pasta do ticket não existe: {ticket_dir}")

    output_base_dir = ticket_dir / output_folder_name

    total_scanned = 0
    total_written = 0
    total_blocks_kept = 0
    files_summary: List[Dict[str, Any]] = []

    for subdir_rel in selected_subdirs:
        # Suporta caminhos relativos multinível (ex: "integrador/sub1")
        subdir_path = ticket_dir / Path(subdir_rel)
        if not subdir_path.exists() or not subdir_path.is_dir():
            continue

        target_subdir = output_base_dir / Path(subdir_rel)

        log_files = [f for f in subdir_path.iterdir() if f.is_file() and f.suffix.lower() == ".log"]

        for log_file in log_files:
            total_scanned += 1
            target_log_path = target_subdir / log_file.name

            blocks_count = filter_log_file(log_file, target_log_path, start_dt, end_dt)

            if blocks_count > 0:
                total_written += 1
                total_blocks_kept += blocks_count
                files_summary.append({
                    "source": str(log_file),
                    "target": str(target_log_path),
                    "subfolder": subdir_rel,
                    "filename": log_file.name,
                    "blocks": blocks_count,
                })

    if total_written > 0:
        output_base_dir.mkdir(parents=True, exist_ok=True)

    return {
        "ticket_dir": ticket_dir,
        "output_dir": output_base_dir,
        "total_files_scanned": total_scanned,
        "total_files_written": total_written,
        "total_blocks_kept": total_blocks_kept,
        "files": files_summary,
    }
