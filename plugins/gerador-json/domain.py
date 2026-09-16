import json
import os
import sys
from pathlib import Path
from typing import Optional, Any, Dict


def format_json(raw_text: str, indent: int = 2, sort_keys: bool = False) -> dict:
    """Formata e indenta payload JSON com suporte a ordenação de chaves."""
    raw = (raw_text or "").strip()
    if not raw:
        return {"success": False, "message": "Texto vazio."}
    try:
        data = json.loads(raw)
        formatted = json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=sort_keys)
        stats = get_json_stats(data)
        return {
            "success": True,
            "result": formatted,
            "stats": stats
        }
    except json.JSONDecodeError as err:
        return {
            "success": False,
            "message": f"Erro de sintaxe JSON na linha {err.lineno}, coluna {err.colno}: {err.msg}",
            "lineno": err.lineno,
            "colno": err.colno
        }
    except Exception as e:
        return {"success": False, "message": f"Erro ao formatar JSON: {e}"}


def minify_json(raw_text: str) -> dict:
    """Remove todos os espaços em branco e quebras de linha desnecessárias."""
    raw = (raw_text or "").strip()
    if not raw:
        return {"success": False, "message": "Texto vazio."}
    try:
        data = json.loads(raw)
        minified = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        stats = get_json_stats(data)
        return {
            "success": True,
            "result": minified,
            "stats": stats
        }
    except json.JSONDecodeError as err:
        return {
            "success": False,
            "message": f"Erro de sintaxe JSON na linha {err.lineno}, coluna {err.colno}: {err.msg}",
            "lineno": err.lineno,
            "colno": err.colno
        }
    except Exception as e:
        return {"success": False, "message": f"Erro ao minificar JSON: {e}"}


def validate_json(raw_text: str) -> dict:
    """Valida a conformidade da sintaxe JSON e extrai metadados."""
    raw = (raw_text or "").strip()
    if not raw:
        return {"success": False, "valid": False, "message": "Texto vazio."}
    try:
        data = json.loads(raw)
        stats = get_json_stats(data)
        return {
            "success": True,
            "valid": True,
            "message": "JSON válido e estruturado.",
            "stats": stats
        }
    except json.JSONDecodeError as err:
        return {
            "success": True,
            "valid": False,
            "message": f"Linha {err.lineno}, Coluna {err.colno}: {err.msg}",
            "lineno": err.lineno,
            "colno": err.colno
        }
    except Exception as e:
        return {"success": False, "valid": False, "message": str(e)}


def get_json_stats(data: Any) -> dict:
    """Calcula estatísticas de chaves/elementos do JSON."""
    if isinstance(data, dict):
        return {"type": "Objeto (dict)", "keys_count": len(data), "is_array": False}
    elif isinstance(data, list):
        return {"type": "Lista (array)", "items_count": len(data), "is_array": True}
    else:
        return {"type": type(data).__name__, "is_primitive": True}


def generate_mock_json(template_type: str = "usuario") -> dict:
    """Gera dados mock JSON para testes rápidos."""
    templates = {
        "usuario": {
            "id": 1024,
            "nome": "Rodrigo Lessa",
            "email": "rodrigo.lessa@empresa.com.br",
            "cargo": "Engenheiro de Software",
            "ativo": True,
            "perfis": ["ADMIN", "DEVELOPER"],
            "preferencias": {
                "tema": "dark",
                "notificacoes": True,
                "idioma": "pt-BR"
            }
        },
        "lista_usuarios": [
            {"id": 1, "nome": "Ana Silva", "email": "ana.silva@exemplo.com", "ativo": True},
            {"id": 2, "nome": "Carlos Souza", "email": "carlos.souza@exemplo.com", "ativo": False},
            {"id": 3, "nome": "Mariana Costa", "email": "mariana.costa@exemplo.com", "ativo": True}
        ],
        "api_response": {
            "status": 200,
            "mensagem": "Operação realizada com sucesso",
            "timestamp": "2026-08-26T12:00:00Z",
            "paginacao": {
                "pagina_atual": 1,
                "total_paginas": 5,
                "total_registros": 48
            },
            "dados": [
                {"codigo": "PRD-01", "nome": "Licença Toolbox", "valor": 0.00, "disponivel": True}
            ]
        },
        "config": {
            "app_name": "Toolbox Ecosystem",
            "versao": "1.22.3",
            "ambiente": "producao",
            "features": {
                "marketplace": True,
                "hot_reload": True,
                "m3_theme": True
            },
            "timeout_segundos": 30
        }
    }

    selected = templates.get(template_type, templates["usuario"])
    return {
        "success": True,
        "result": json.dumps(selected, indent=2, ensure_ascii=False),
        "template": template_type
    }


FILE_JSON_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "file-json.ico"


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows (delega para shared.web_utils)."""
    try:
        from shared.web_utils import set_window_taskbar_icon as _set_icon
    except ImportError:
        from plugins.shared.web_utils import set_window_taskbar_icon as _set_icon
    return _set_icon(icon_path=icon_path or FILE_JSON_ICON_PATH, hwnd=hwnd)
