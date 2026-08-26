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
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone de arquivo JSON."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else FILE_JSON_ICON_PATH
    if not target_icon.exists():
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        h_icon_big = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            32,
            32,
            LR_LOADFROMFILE,
        )
        h_icon_small = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            16,
            16,
            LR_LOADFROMFILE,
        )

        if not h_icon_big and not h_icon_small:
            return False

        if hwnd:
            target_hwnds = [hwnd]
        else:
            current_pid = os.getpid()
            target_hwnds = []

            def _enum_windows_cb(handle: int, _: Any) -> bool:
                lpdw_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(handle, ctypes.byref(lpdw_pid))
                if lpdw_pid.value == current_pid:
                    if user32.IsWindowVisible(handle):
                        target_hwnds.append(handle)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(_enum_windows_cb), 0)

        success = False
        for target in target_hwnds:
            if h_icon_big:
                user32.SendMessageW(target, WM_SETICON, ICON_BIG, h_icon_big)
            if h_icon_small:
                user32.SendMessageW(target, WM_SETICON, ICON_SMALL, h_icon_small)
            success = True
        return success
    except Exception:
        pass
    return False
