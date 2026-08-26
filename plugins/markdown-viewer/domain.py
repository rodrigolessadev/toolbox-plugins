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
        stats = analyze_markdown(content)
        return {
            "success": True,
            "path": str(path.resolve()),
            "filename": path.name,
            "content": content,
            "stats": stats
        }
    except Exception as exc:
        return {"success": False, "error": f"Falha ao ler arquivo: {str(exc)}"}


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
    code_blocks = len(re.findall(r"^```", text, flags=re.MULTILINE)) // 2

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
