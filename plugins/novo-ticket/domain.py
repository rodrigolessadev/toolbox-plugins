"""
Módulo de regras de negócio para o plugin Novo Ticket.
Contém funções puras e testáveis para sanitização, validação e criação de diretórios de tickets.
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

# Caracteres inválidos para nomes de arquivos e pastas no Windows: \ / : * ? " < > |
INVALID_CHARS_REGEX = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


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

    # Substitui caracteres inválidos por underscore
    cleaned = INVALID_CHARS_REGEX.sub("_", name)

    # Remove espaços ao redor de underscores (ex: "empresa: filial" -> "empresa_filial")
    cleaned = re.sub(r"\s*_\s*", "_", cleaned)

    # Substitui múltiplos espaços por um espaço simples
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Compacta múltiplos underscores resultantes
    cleaned = re.sub(r"_+", "_", cleaned)

    # Remove pontos, espaços e underscores das pontas (requisito Windows)
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
    # Valida diretório inicial
    is_valid_dir, dir_err, base_path = validate_base_dir(base_dir_str)
    if not is_valid_dir or base_path is None:
        return False, dir_err, None

    # Valida cliente e ticket
    try:
        folder_name = format_ticket_folder_name(cliente, ticket)
    except ValueError as ex:
        return False, str(ex), None

    target_path = base_path / folder_name

    # Verifica conflito com diretório/arquivo existente
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