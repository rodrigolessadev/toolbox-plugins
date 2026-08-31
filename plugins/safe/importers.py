"""
Módulo de Importação de Credenciais e Segredos do Microsoft Safe e outros formatos.
Suporta XML (.xml), CSV (.csv), TXT (.txt) e JSON (.json), com auto-detecção de encoding.
"""

from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from logger import get_logger
except ImportError:
    try:
        from .logger import get_logger
    except ImportError:
        import logging
        def get_logger(name="safe"):
            return logging.getLogger(name)

logger = get_logger("safe.importers")


def decode_file_bytes(raw_bytes: bytes) -> str:
    """
    Decodifica bytes brutos tentando os encodings mais comuns em exportações do Windows:
    UTF-8-SIG (com BOM), UTF-8, Windows-1252 (CP1252) e ISO-8859-1.
    """
    encodings = ["utf-8-sig", "utf-8", "windows-1252", "cp1252", "iso-8859-1"]
    for enc in encodings:
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    # Fallback seguro com substituição de caracteres inválidos
    return raw_bytes.decode("utf-8", errors="replace")


def normalize_secret_entry(
    title: Optional[str],
    payload: Optional[str],
    username: Optional[str] = None,
    category: Optional[str] = None,
    url: Optional[str] = None,
    notes: Optional[str] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Valida e normaliza um item para o schema padrão do Cofre Seguro.
    """
    clean_title = (title or "").strip()
    if not clean_title:
        clean_title = "Item Sem Título"

    clean_payload = (payload or "").strip()
    clean_username = (username or "").strip()
    clean_category = (category or "").strip().lower()

    if not clean_category:
        clean_category = "password"

    # Mapeamento semântico de categorias para as padrões do cofre
    category_map = {
        "senhas": "password",
        "senha": "password",
        "passwords": "password",
        "web": "password",
        "login": "password",
        "logins": "password",
        "cartões": "card",
        "cartao": "card",
        "cartão": "card",
        "cards": "card",
        "banco de dados": "database",
        "database": "database",
        "banco": "database",
        "servidor": "server",
        "servers": "server",
        "servidores": "server",
        "host": "server",
        "ssh": "server",
        "notas": "note",
        "nota": "note",
        "notes": "note",
        "anotações": "note",
        "anotação": "note",
        "chave": "api_key",
        "api": "api_key",
        "token": "api_key",
    }
    final_category = category_map.get(clean_category, clean_category if clean_category in ("password", "api_key", "note", "database", "server", "card") else "password")

    metadata: Dict[str, Any] = {
        "imported_from": "microsoft_safe",
    }
    if url:
        metadata["url"] = url.strip()
    if notes:
        metadata["notes"] = notes.strip()
    if custom_fields:
        metadata["custom_fields"] = custom_fields

    final_tags = list(tags) if tags else []
    if final_category not in final_tags:
        final_tags.append(final_category)

    return {
        "title": clean_title,
        "category": final_category,
        "username_or_key": clean_username,
        "payload": clean_payload,
        "tags": final_tags,
        "metadata": metadata,
    }


def parse_safe_xml(content: str) -> List[Dict[str, Any]]:
    """
    Parser para arquivos XML exportados do Microsoft Safe ou formatos hierárquicos compatíveis.
    Suporta nós <Card>, <Item>, <Entry>, <Account> e campos <Field name="..."> ou tags diretas.
    """
    items: List[Dict[str, Any]] = []
    if not content or not content.strip():
        return items

    try:
        # Parsing do XML com proteção básica
        root = ET.fromstring(content)
    except Exception as e:
        logger.debug(f"XML parse error: {e}")
        return items

    # Encontra nós de cartões/itens
    card_nodes = []
    # Verifica se os nós estão diretamente na raiz ou aninhados
    for tag in ("Card", "card", "Item", "item", "Entry", "entry", "Account", "account", "Record", "record"):
        found = root.findall(f".//{tag}")
        if found:
            card_nodes.extend(found)

    # Se não encontrou por tags conhecidas, tenta os filhos diretos da raiz
    if not card_nodes:
        card_nodes = list(root)

    for card in card_nodes:
        title = card.attrib.get("title") or card.attrib.get("name") or card.attrib.get("label") or card.attrib.get("Title") or card.attrib.get("Name")
        category = card.attrib.get("category") or card.attrib.get("Category") or card.attrib.get("folder") or card.attrib.get("Group")
        username = None
        password = None
        url = None
        notes = None
        custom_fields: Dict[str, Any] = {}

        # 1. Varre campos <Field name="UserName">valor</Field> ou <Field label="...">
        for field in card.findall("Field") + card.findall("field") + card.findall("Property") + card.findall("property"):
            field_name = (field.attrib.get("name") or field.attrib.get("Name") or field.attrib.get("label") or field.attrib.get("Label") or "").lower()
            field_val = (field.text or "").strip()

            if not field_name:
                continue

            if field_name in ("username", "user", "login", "usuario", "usuário", "user name", "user_name", "email", "account"):
                username = field_val
            elif field_name in ("password", "pwd", "senha", "pass", "secret", "chave"):
                password = field_val
            elif field_name in ("url", "link", "website", "site", "host", "endereco", "endereço"):
                url = field_val
            elif field_name in ("notes", "note", "comments", "observacoes", "observações", "obs", "descricao", "descrição"):
                notes = field_val
            elif field_name in ("title", "name", "cardname", "card_name", "label") and not title:
                title = field_val
            elif field_name in ("category", "folder", "group", "tipo", "categoria") and not category:
                category = field_val
            else:
                custom_fields[field.attrib.get("name") or field.attrib.get("label") or field_name] = field_val

        # 2. Varre sub-tags diretas (ex: <UserName>admin</UserName>, <Password>123</Password>)
        for child in list(card):
            tag_name = child.tag.lower()
            child_text = (child.text or "").strip()
            if not child_text or tag_name in ("field", "property"):
                continue

            if tag_name in ("title", "name", "cardname", "card_name", "label"):
                title = child_text
            elif tag_name in ("category", "folder", "group", "tipo", "categoria"):
                category = child_text
            elif tag_name in ("username", "user", "login", "usuario", "usuário", "user_name", "email", "account") and not username:
                username = child_text
            elif tag_name in ("password", "pwd", "senha", "pass", "secret", "chave") and not password:
                password = child_text
            elif tag_name in ("url", "link", "website", "site", "host", "endereco", "endereço") and not url:
                url = child_text
            elif tag_name in ("notes", "note", "comments", "observacoes", "observações", "obs", "descricao", "descrição") and not notes:
                notes = child_text
            elif tag_name not in ("id", "guid", "card", "item", "entry"):
                custom_fields[child.tag] = child_text

        # Extrai nós de notas ou textos diretos do cartão se houver
        if not notes and card.text and card.text.strip():
            notes = card.text.strip()

        normalized = normalize_secret_entry(
            title=title,
            payload=password or notes or "",
            username=username,
            category=category,
            url=url,
            notes=notes,
            custom_fields=custom_fields if custom_fields else None,
        )
        if normalized:
            items.append(normalized)

    logger.debug(f"Parser XML processou {len(items)} itens.")
    return items


def parse_safe_csv(content: str) -> List[Dict[str, Any]]:
    """
    Parser para arquivos CSV exportados do Microsoft Safe ou planilhas de credenciais.
    Detecta automaticamente delimitadores (, ou ;) e mapeia colunas semanticamente.
    """
    items: List[Dict[str, Any]] = []
    if not content or not content.strip():
        return items

    # Detecta delimitador
    sample = content[:4096]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except Exception:
        # Fallback de contagem
        if sample.count(";") > sample.count(","):
            delimiter = ";"
        elif sample.count("\t") > sample.count(","):
            delimiter = "\t"

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    header: Optional[List[str]] = None
    header_map: Dict[str, int] = {}

    for row in reader:
        if not row or all(not cell.strip() for cell in row):
            continue

        if header is None:
            header = [col.strip().lower() for col in row]
            for idx, col_name in enumerate(header):
                # Normaliza caracteres do cabeçalho
                clean_name = re.sub(r"[^a-z0-9_áéíóúãõç]", "", col_name)
                header_map[clean_name] = idx
            continue

        def get_col(*aliases: str) -> Optional[str]:
            for alias in aliases:
                for h_name, h_idx in header_map.items():
                    if alias in h_name:
                        if h_idx < len(row):
                            val = row[h_idx].strip()
                            if val:
                                return val
            return None

        title = get_col("title", "titulo", "name", "nome", "card", "account", "descricao", "descrição", "rotulo", "rótulo")
        username = get_col("username", "user", "login", "usuario", "usuário", "email", "conta")
        password = get_col("password", "pwd", "senha", "pass", "secret", "chave")
        category = get_col("category", "categoria", "folder", "pasta", "group", "grupo", "tipo", "type")
        url = get_col("url", "link", "website", "site", "host", "endereco", "endereço")
        notes = get_col("notes", "note", "comments", "comentarios", "comentários", "observacoes", "observações", "obs")

        custom_fields: Dict[str, Any] = {}
        for h_name, h_idx in header_map.items():
            if h_idx < len(row) and row[h_idx].strip():
                # Se a coluna não for uma das principais, coloca em custom_fields
                if not any(k in h_name for k in ("title", "titulo", "name", "nome", "user", "login", "pwd", "pass", "senha", "category", "categoria", "url", "note", "obs")):
                    custom_fields[header[h_idx]] = row[h_idx].strip()

        # Se não encontrou coluna de título específica mas tem colunas, usa a primeira
        if not title and len(row) > 0 and row[0].strip():
            title = row[0].strip()

        normalized = normalize_secret_entry(
            title=title,
            payload=password or notes or "",
            username=username,
            category=category,
            url=url,
            notes=notes,
            custom_fields=custom_fields if custom_fields else None,
        )
        if normalized:
            items.append(normalized)

    logger.debug(f"Parser CSV processou {len(items)} itens (delimitador: '{delimiter}').")
    return items


def parse_safe_txt(content: str) -> List[Dict[str, Any]]:
    """
    Parser para arquivos TXT de texto simples do Microsoft Safe estruturados por blocos.
    Blocos separados por linhas em branco ou separadores de linha (---, ===).
    """
    items: List[Dict[str, Any]] = []
    if not content or not content.strip():
        return items

    # Normaliza quebras de linha
    normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Divide blocos por linhas em branco duplas ou separadores
    raw_blocks = re.split(r"\n\s*(?:[-=_]{3,}\s*|\n)+", normalized_content)

    for block in raw_blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        title = None
        category = None
        username = None
        password = None
        url = None
        notes_lines: List[str] = []
        custom_fields: Dict[str, Any] = {}

        current_key: Optional[str] = None

        for line in lines:
            # Verifica cabeçalho de bloco no formato [Título]
            header_match = re.match(r"^\[(.+)\]$", line.strip())
            if header_match and not title:
                title = header_match.group(1).strip()
                continue

            # Verifica pares Chave: Valor ou Chave = Valor
            kv_match = re.match(r"^([^:=]+)\s*[:=]\s*(.*)$", line)
            if kv_match:
                key_raw = kv_match.group(1).strip().lower()
                val_raw = kv_match.group(2).strip()

                if key_raw in ("title", "título", "titulo", "name", "nome", "cartão", "card", "card name", "conta", "account"):
                    title = val_raw
                    current_key = "title"
                elif key_raw in ("category", "categoria", "folder", "pasta", "group", "grupo", "tipo", "type"):
                    category = val_raw
                    current_key = "category"
                elif key_raw in ("username", "user", "login", "usuario", "usuário", "user name", "user_name", "email"):
                    username = val_raw
                    current_key = "username"
                elif key_raw in ("password", "pwd", "senha", "pass", "secret", "chave"):
                    password = val_raw
                    current_key = "password"
                elif key_raw in ("url", "link", "website", "site", "host", "endereco", "endereço"):
                    url = val_raw
                    current_key = "url"
                elif key_raw in ("notes", "note", "comments", "observacoes", "observações", "obs", "descricao", "descrição"):
                    notes_lines.append(val_raw)
                    current_key = "notes"
                else:
                    custom_fields[kv_match.group(1).strip()] = val_raw
                    current_key = "custom"
            else:
                # Linha de continuação
                if current_key == "notes":
                    notes_lines.append(line.strip())
                elif not title:
                    title = line.strip()

        notes = "\n".join(notes_lines).strip() if notes_lines else None

        normalized = normalize_secret_entry(
            title=title,
            payload=password or notes or "",
            username=username,
            category=category,
            url=url,
            notes=notes,
            custom_fields=custom_fields if custom_fields else None,
        )
        if normalized:
            items.append(normalized)

    logger.debug(f"Parser TXT processou {len(items)} itens.")
    return items


def parse_safe_json(content: str) -> List[Dict[str, Any]]:
    """
    Parser para arquivos JSON (Save in Cloud, backups de cofre ou listas diretas).
    """
    items: List[Dict[str, Any]] = []
    if not content or not content.strip():
        return items

    try:
        data = json.loads(content)
    except Exception as e:
        logger.debug(f"JSON parse error: {e}")
        return items

    raw_list: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        if "entries" in data and isinstance(data["entries"], list):
            raw_list = data["entries"]
        elif "secrets" in data and isinstance(data["secrets"], list):
            raw_list = data["secrets"]
        elif "items" in data and isinstance(data["items"], list):
            raw_list = data["items"]
        else:
            raw_list = [data]
    elif isinstance(data, list):
        raw_list = data

    for raw in raw_list:
        if not isinstance(raw, dict):
            continue

        normalized = normalize_secret_entry(
            title=raw.get("title") or raw.get("name"),
            payload=raw.get("payload") or raw.get("password") or raw.get("secret"),
            username=raw.get("username_or_key") or raw.get("username") or raw.get("user"),
            category=raw.get("category"),
            url=(raw.get("metadata") or {}).get("url") if isinstance(raw.get("metadata"), dict) else raw.get("url"),
            notes=(raw.get("metadata") or {}).get("notes") if isinstance(raw.get("metadata"), dict) else raw.get("notes"),
            custom_fields=(raw.get("metadata") or {}).get("custom_fields") if isinstance(raw.get("metadata"), dict) else None,
            tags=raw.get("tags"),
        )
        if normalized:
            items.append(normalized)

    logger.debug(f"Parser JSON processou {len(items)} itens.")
    return items


def detect_and_parse_secrets(
    content_or_bytes: Union[str, bytes],
    filename: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Detecta automaticamente o formato (XML, CSV, TXT ou JSON), realiza o parsing
    e retorna uma tupla (lista_de_itens_normalizados, formato_detectado).
    """
    if isinstance(content_or_bytes, bytes):
        text = decode_file_bytes(content_or_bytes)
    else:
        text = content_or_bytes

    clean_text = text.strip()
    if not clean_text:
        return [], "unknown"

    lower_fn = (filename or "").lower()

    # 1. Detecção por extensão explícita
    if lower_fn.endswith(".xml"):
        items = parse_safe_xml(clean_text)
        if items:
            return items, "xml"

    if lower_fn.endswith(".json"):
        items = parse_safe_json(clean_text)
        if items:
            return items, "json"

    if lower_fn.endswith(".csv"):
        items = parse_safe_csv(clean_text)
        if items:
            return items, "csv"

    if lower_fn.endswith(".txt"):
        items = parse_safe_txt(clean_text)
        if items:
            return items, "txt"

    # 2. Heurística pelo conteúdo do texto
    if clean_text.startswith("<?xml") or clean_text.startswith("<Safe") or clean_text.startswith("<root") or clean_text.startswith("<cards"):
        items = parse_safe_xml(clean_text)
        if items:
            return items, "xml"

    if clean_text.startswith("{") or clean_text.startswith("["):
        items = parse_safe_json(clean_text)
        if items:
            return items, "json"

    # Testa CSV (se houver vírgula ou ponto e vírgula nas primeiras linhas)
    first_lines = clean_text.splitlines()[:5]
    if any("," in l or ";" in l for l in first_lines):
        items = parse_safe_csv(clean_text)
        if len(items) >= 1:
            return items, "csv"

    # Fallback para TXT
    items = parse_safe_txt(clean_text)
    if items:
        return items, "txt"

    return [], "unknown"
