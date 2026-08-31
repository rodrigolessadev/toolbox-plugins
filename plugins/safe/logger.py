"""
Sistema de Logging Padronizado para o Plugin Safe (Cofre).

Gravação diária de arquivos em log/ com rotação, expurgo automático
por política de retenção (30 dias) e sanitização estrita de dados confidenciais.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# Retenção padrão dos logs em dias
DEFAULT_LOG_RETENTION_DAYS = 30


def get_default_log_dir() -> Path:
    """
    Retorna o diretório canônico de logs do ecossistema Toolbox.
    No Windows: %APPDATA%/com.toolbox.desktop/log
    Fallback: ~/.toolbox/log
    """
    if sys.platform == "win32" and "APPDATA" in os.environ:
        base_dir = Path(os.environ["APPDATA"]) / "com.toolbox.desktop" / "log"
    else:
        base_dir = Path.home() / ".toolbox" / "log"
    return base_dir


def get_safe_log_filename(target_date: Optional[date] = None) -> str:
    """
    Formata o nome do arquivo diário de log: safe-YYYY-MM-DD.log
    """
    dt = target_date or datetime.now().date()
    return f"safe-{dt.strftime('%Y-%m-%d')}.log"


def cleanup_old_safe_logs(
    log_dir: Path,
    reference_date: Optional[date] = None,
    retention_days: int = DEFAULT_LOG_RETENTION_DAYS
) -> int:
    """
    Exclui logs do cofre com idade igual ou superior a retention_days (padrão 30 dias).
    """
    ref_date = reference_date or datetime.now().date()
    target_dir = Path(log_dir)
    if not target_dir.exists():
        return 0

    removed_count = 0
    # Padrão safe-YYYY-MM-DD.log e cofre-YYYY-MM-DD.log
    date_regex = re.compile(r"^(?:safe|cofre)-(\d{4})-(\d{2})-(\d{2})(?:\.\d+)?\.log$")

    for file_path in target_dir.iterdir():
        if not file_path.is_file():
            continue

        match = date_regex.match(file_path.name)
        if match:
            year, month, day = match.groups()
            try:
                log_dt = date(int(year), int(month), int(day))
                age_days = (ref_date - log_dt).days
                if age_days >= retention_days:
                    try:
                        file_path.unlink()
                        removed_count += 1
                    except Exception:
                        pass
            except ValueError:
                continue

    return removed_count


def setup_logger(
    log_dir: Optional[Path] = None,
    logger_name: str = "safe",
    target_date: Optional[date] = None,
    retention_days: int = DEFAULT_LOG_RETENTION_DAYS
) -> logging.Logger:
    """
    Inicializa e configura o logger do Safe com arquivo diário e expurgo de retenção.
    """
    target_dir = (Path(log_dir) if log_dir else get_default_log_dir()).resolve()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    log_file = target_dir / get_safe_log_filename(target_date)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Limpa handlers anteriores para permitir reconfiguração segura
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:
            pass
        logger.removeHandler(h)

    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler com Rotação (5MB por arquivo, até 5 backups caso o dia exceda)
    try:
        fh = RotatingFileHandler(
            str(log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        # Falha de permissão de escrita em arquivo não quebra a execução do app
        sys.stderr.write(f"[SafeLogger] Erro ao criar FileHandler: {e}\n")

    # Console Stream Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Executa a limpeza automática de logs antigos
    try:
        cleanup_old_safe_logs(target_dir, reference_date=target_date, retention_days=retention_days)
    except Exception:
        pass

    return logger


def close_logger(logger_or_name: Union[logging.Logger, str] = "safe") -> None:
    """
    Fecha e remove todos os handlers do logger especificado, liberando file handles no Windows.
    """
    logger = logging.getLogger(logger_or_name) if isinstance(logger_or_name, str) else logger_or_name
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:
            pass
        logger.removeHandler(h)


_global_logger: Optional[logging.Logger] = None


def get_logger(name: str = "safe") -> logging.Logger:
    """
    Obtém uma instância de logger (inicializa o logger central se ainda não foi criado).
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = setup_logger()
    
    if name == "safe" or not name:
        return _global_logger
    
    return logging.getLogger(name)
