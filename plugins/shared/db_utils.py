"""
Utilitários de Banco de Dados Central para Plugins do Toolbox.
Garante resolução padronizada do caminho do SQLite Central (%APPDATA%\\com.toolbox.desktop\\toolbox.db).
"""

import os
import sys
from pathlib import Path


def get_central_db_path() -> Path:
    """
    Retorna o caminho canônico do banco SQLite central do Toolbox (toolbox.db).
    - Windows: %APPDATA%\\com.toolbox.desktop\\toolbox.db
    - Linux / macOS (fallback): ~/.toolbox/toolbox.db
    """
    if sys.platform == "win32" and "APPDATA" in os.environ:
        base_dir = Path(os.environ["APPDATA"]) / "com.toolbox.desktop"
    else:
        base_dir = Path.home() / ".toolbox"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "toolbox.db"


def get_central_logs_dir() -> Path:
    """
    Retorna o caminho canônico do diretório de logs do Toolbox.
    - Windows: %APPDATA%\\com.toolbox.desktop\\logs
    - Linux / macOS (fallback): ~/.toolbox/logs
    """
    if sys.platform == "win32" and "APPDATA" in os.environ:
        base_dir = Path(os.environ["APPDATA"]) / "com.toolbox.desktop" / "logs"
    else:
        base_dir = Path.home() / ".toolbox" / "logs"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

