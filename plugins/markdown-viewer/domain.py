import html
import os
import re
import sys
from pathlib import Path
from typing import Optional, Any, Dict


def read_markdown_file(file_path: str) -> dict:
    """Lê um arquivo Markdown local e extrai estatísticas básicas."""
    if not file_path:
        return {"success": False, "error": "Caminho de arquivo não fornecido."}

    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"Arquivo '{file_path}' não encontrado."}

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        mtime = path.stat().st_mtime
        stats = analyze_markdown(content)
        return {
            "success": True,
            "path": str(path.resolve()),
            "filename": path.name,
            "content": content,
            "mtime": mtime,
            "stats": stats
        }
    except Exception as exc:
        return {"success": False, "error": f"Falha ao ler arquivo: {str(exc)}"}


def get_file_info(file_path: str) -> dict:
    """Retorna metadados de modificação do arquivo para Live Watcher/Hot-Reload."""
    if not file_path:
        return {"success": False, "error": "Caminho não fornecido."}
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "exists": False}
    try:
        stat = path.stat()
        return {
            "success": True,
            "exists": True,
            "mtime": stat.st_mtime,
            "size": stat.st_size
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def save_markdown_file(file_path: str, content: str) -> dict:
    """Salva o conteúdo em um arquivo Markdown local."""
    if not file_path:
        return {"success": False, "error": "Caminho de arquivo não fornecido."}

    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or "", encoding="utf-8")
        stats = analyze_markdown(content or "")
        return {
            "success": True,
            "path": str(path.resolve()),
            "filename": path.name,
            "stats": stats
        }
    except Exception as exc:
        return {"success": False, "error": f"Falha ao salvar arquivo: {str(exc)}"}


def analyze_markdown(content: str) -> dict:
    """Calcula estatísticas de um documento Markdown."""
    text = content or ""
    lines = text.splitlines()
    words = re.findall(r"\b\w+\b", text)
    headings = re.findall(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE)
    # 1. Contar e isolar blocos cercados (fenced)
    fenced_blocks = len(re.findall(r"^\s*(?:`{3,}|~{3,})", text, flags=re.MULTILINE)) // 2
    clean_text_no_fences = re.sub(r"(?ms)^\s*(?:`{3,}|~{3,}).*?^\s*(?:`{3,}|~{3,})", "", text)

    # 2. Contar blocos puramente indentados (4 espaços ou 1 tab após linha em branco)
    indented_blocks = len(re.findall(r"(?:(?<=\n\n)|^\n*)((?:(?: {4}|\t)[^\n]*\n?)+)", clean_text_no_fences))
    code_blocks = fenced_blocks + indented_blocks

    # Tempo estimado de leitura (base média: 200 palavras/minuto)
    w_count = len(words)
    read_time_min = max(1, round(w_count / 200)) if w_count > 0 else 0

    return {
        "line_count": len(lines),
        "word_count": w_count,
        "char_count": len(text),
        "heading_count": len(headings),
        "code_block_count": code_blocks,
        "read_time_min": read_time_min
    }


def export_html_document(title: str, body_html: str) -> str:
    """Gera um documento HTML autônomo e estilizado pronto para visualização/impressão."""
    safe_title = html.escape(title or "Documento Markdown")
    return f"""<!DOCTYPE html>
<html lang="pt-BR" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <title>{safe_title}</title>
  <style>
    :root {{
      --bg: #0f172a;
      --bg-surface: #1e293b;
      --bg-card: #1e293b;
      --bg-input: #0f172a;
      --fg: #f8fafc;
      --fg-muted: #94a3b8;
      --border: #334155;
      --accent: #3b82f6;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-mono: 'Consolas', 'Courier New', monospace;
    }}
    body {{
      background: var(--bg);
      color: var(--fg);
      font-family: var(--font-sans);
      line-height: 1.6;
      padding: 40px 20px;
      margin: 0 auto;
      max-width: 900px;
    }}
    h1, h2, h3, h4, h5, h6 {{
      color: var(--fg);
      border-bottom: 1px solid var(--border);
      padding-bottom: 6px;
      margin-top: 24px;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    pre {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 14px;
      overflow-x: auto;
      font-family: var(--font-mono);
      font-size: 13px;
    }}
    code {{
      background: var(--bg-surface);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 13px;
    }}
    blockquote {{
      border-left: 4px solid var(--accent);
      margin: 16px 0;
      padding: 8px 16px;
      background: var(--bg-surface);
      border-radius: 0 6px 6px 0;
      color: var(--fg-muted);
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: 8px 12px;
      text-align: left;
    }}
    th {{ background: var(--bg-surface); }}
  </style>
</head>
<body>
  {body_html}
</body>
</html>"""


FILE_TEXT_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "file-text.ico"


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone de markdown/documento."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else FILE_TEXT_ICON_PATH
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


def get_session_dir() -> Path:
    """Retorna o diretório de snapshots e estado de sessão do Visualizador de Markdown."""
    if sys.platform == "win32" and "APPDATA" in os.environ:
        base_dir = Path(os.environ["APPDATA"]) / "com.toolbox.desktop" / "markdown_viewer_session"
    else:
        base_dir = Path.home() / ".toolbox" / "markdown_viewer_session"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def save_session(session_data: dict, snapshots: Optional[dict] = None) -> dict:
    """Salva os metadados de sessão em session.json e o conteúdo de cada aba em snapshots .tmp."""
    import json
    try:
        s_dir = get_session_dir()
        session_file = s_dir / "session.json"
        
        # Salva o arquivo de índice de sessão
        session_file.write_text(json.dumps(session_data or {}, indent=2, ensure_ascii=False), encoding="utf-8")

        # Salva os snapshots individuais das abas
        active_snapshot_files = set()
        if snapshots and isinstance(snapshots, dict):
            for tab_id, content in snapshots.items():
                clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(tab_id))
                tmp_file = s_dir / f"{clean_id}.tmp"
                tmp_file.write_text(content or "", encoding="utf-8")
                active_snapshot_files.add(tmp_file.name)

        # Remove arquivos temporários órfãos que não pertencem mais às abas abertas
        tabs = (session_data or {}).get("tabs", [])
        referenced_ids = {re.sub(r"[^a-zA-Z0-9_\-]", "_", str(t.get("id"))) for t in tabs if t.get("id")}
        for f in s_dir.glob("*.tmp"):
            tab_name_prefix = f.stem
            if tab_name_prefix not in referenced_ids:
                try:
                    f.unlink()
                except Exception:
                    pass

        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": f"Falha ao salvar sessão: {str(exc)}"}


def load_session() -> dict:
    """Carrega o estado prévio da sessão e o conteúdo restaurado de cada snapshot .tmp."""
    import json
    try:
        s_dir = get_session_dir()
        session_file = s_dir / "session.json"
        if not session_file.exists():
            return {"success": True, "hasSession": False, "data": None}

        raw_data = json.loads(session_file.read_text(encoding="utf-8"))
        tabs = raw_data.get("tabs", [])

        restored_tabs = []
        for tab in tabs:
            tab_id = tab.get("id", "")
            clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(tab_id))
            tmp_file = s_dir / f"{clean_id}.tmp"

            content = None
            if tmp_file.exists():
                content = tmp_file.read_text(encoding="utf-8", errors="replace")
            elif tab.get("path") and Path(tab.get("path")).exists():
                content = Path(tab.get("path")).read_text(encoding="utf-8", errors="replace")

            if content is not None:
                tab_copy = dict(tab)
                tab_copy["content"] = content
                restored_tabs.append(tab_copy)

        raw_data["tabs"] = restored_tabs
        has_session = len(restored_tabs) > 0

        return {"success": True, "hasSession": has_session, "data": raw_data}
    except Exception as exc:
        return {"success": False, "error": f"Falha ao carregar sessão: {str(exc)}", "hasSession": False}


def delete_tab_snapshot(tab_id: str) -> dict:
    """Remove o snapshot temporário de uma aba específica."""
    try:
        if not tab_id:
            return {"success": True}
        clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(tab_id))
        s_dir = get_session_dir()
        tmp_file = s_dir / f"{clean_id}.tmp"
        if tmp_file.exists():
            tmp_file.unlink()
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def clear_all_session() -> dict:
    """Limpa todo o histórico de sessão e snapshots temporários."""
    try:
        s_dir = get_session_dir()
        for f in s_dir.glob("*.*"):
            try:
                f.unlink()
            except Exception:
                pass
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}

