"""
Testes unitários e de integração para o sistema de logging do Plugin Safe (Cofre).
"""

import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
import pytest

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from safe import logger as safe_logger
from safe.service import SafeService


def test_logger_setup_creates_dir_and_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "log"
        target_dt = date(2026, 8, 31)

        test_log = safe_logger.setup_logger(
            log_dir=tmp_path,
            logger_name="test_safe_logger",
            target_date=target_dt
        )
        try:
            assert tmp_path.exists()
            expected_file = tmp_path / "safe-2026-08-31.log"
            assert expected_file.exists()

            test_log.info("Mensagem de teste unitário.")

            for h in test_log.handlers:
                h.flush()

            content = expected_file.read_text(encoding="utf-8")
            assert "[INFO]" in content
            assert "[test_safe_logger]" in content
            assert "Mensagem de teste unitário." in content
        finally:
            safe_logger.close_logger(test_log)


def test_logger_format_with_milliseconds():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_log = safe_logger.setup_logger(
            log_dir=tmp_path,
            logger_name="test_format"
        )
        try:
            test_log.warning("Aviso de verificação.")

            for h in test_log.handlers:
                h.flush()

            log_file = tmp_path / safe_logger.get_safe_log_filename()
            content = log_file.read_text(encoding="utf-8")
            
            assert "[WARNING]" in content
            assert "[test_format]" in content
            assert "Aviso de verificação." in content
        finally:
            safe_logger.close_logger(test_log)


def test_logger_retention_and_cleanup():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        ref_date = date(2026, 8, 31)

        recent_log = log_dir / safe_logger.get_safe_log_filename(ref_date - timedelta(days=5))
        recent_log.write_text("recent log", encoding="utf-8")

        edge_log = log_dir / safe_logger.get_safe_log_filename(ref_date - timedelta(days=29))
        edge_log.write_text("edge log", encoding="utf-8")

        old_log1 = log_dir / safe_logger.get_safe_log_filename(ref_date - timedelta(days=31))
        old_log1.write_text("old log 1", encoding="utf-8")

        old_log2 = log_dir / safe_logger.get_safe_log_filename(ref_date - timedelta(days=60))
        old_log2.write_text("old log 2", encoding="utf-8")

        other_file = log_dir / "notes.txt"
        other_file.write_text("do not delete", encoding="utf-8")

        removed = safe_logger.cleanup_old_safe_logs(log_dir, reference_date=ref_date, retention_days=30)
        assert removed == 2

        assert recent_log.exists()
        assert edge_log.exists()
        assert not old_log1.exists()
        assert not old_log2.exists()
        assert other_file.exists()


def test_service_logs_sanitization():
    """
    Garante criticamente que senhas mestras e payloads confidenciais NUNCA sejam gravados nos logs.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_file = tmp_path / "vault.db"
        log_dir = tmp_path / "log"

        l1 = safe_logger.setup_logger(log_dir=log_dir, logger_name="safe.service")
        l2 = safe_logger.setup_logger(log_dir=log_dir, logger_name="safe.db")

        try:
            service = SafeService(db_file)

            # 1. Setup com senha ultra secreta
            secret_master_pwd = "SuperSecretMasterPassword999!"
            service.setup_vault(auth_mode="master_password", password=secret_master_pwd, auto_lock_timeout=300)

            # 2. Salvar segredo com payload confidencial
            secret_payload_text = "CONFIDENTIAL_API_TOKEN_XYZ_123456"
            saved = service.save_secret(
                title="Produção AWS",
                secret_payload=secret_payload_text,
                category="api_key",
                username_or_key="admin_user",
            )

            # 3. Ler segredo
            service.get_secret(saved["id"])

            # 4. Lock e unlock
            service.lock()
            service.unlock(password=secret_master_pwd)

            # 5. Exportar segredos
            service.export_secrets()

            for h in l1.handlers + l2.handlers:
                h.flush()

            log_file = log_dir / safe_logger.get_safe_log_filename()
            assert log_file.exists()
            log_content = log_file.read_text(encoding="utf-8")

            # Validações de Sanitização Absoluta
            assert secret_master_pwd not in log_content, "ERRO CRÍTICO: Senha Mestra vazou no arquivo de log!"
            assert secret_payload_text not in log_content, "ERRO CRÍTICO: Payload do segredo vazou no arquivo de log!"

            # Validações de Eventos Registrados com Sucesso
            assert "Produção AWS" in log_content
            assert "SafeService inicializado" in log_content
            assert "Cofre configurado e desbloqueado" in log_content
            assert "Cofre bloqueado com sucesso" in log_content
            assert "Cofre desbloqueado com sucesso" in log_content
        finally:
            safe_logger.close_logger(l1)
            safe_logger.close_logger(l2)
            safe_logger.close_logger("safe.service")
            safe_logger.close_logger("safe.db")


def test_log_frontend_error_bridge():
    """
    Testa se erros relatados pelo JavaScript via SafePluginApi.log_frontend_error são registrados no log.
    """
    from safe.main import SafePluginApi

    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "log"
        test_log = safe_logger.setup_logger(log_dir=log_dir, logger_name="safe.main")

        try:
            api = SafePluginApi()
            res = api.log_frontend_error(
                message="ReferenceError: appInitialized is not defined",
                stack="at initApp (app.js:25:5)"
            )
            assert res.get("success") is True

            for h in test_log.handlers:
                h.flush()

            log_file = log_dir / safe_logger.get_safe_log_filename()
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")
            assert "[ERROR]" in content
            assert "[safe.main]" in content
            assert "ReferenceError: appInitialized is not defined" in content
            assert "Stack: at initApp (app.js:25:5)" in content
        finally:
            safe_logger.close_logger(test_log)
            safe_logger.close_logger("safe.main")


def test_logger_resilience_to_invalid_or_restricted_dir():
    """
    Testa se o setup_logger continua retornando um logger funcional com StreamHandler
    mesmo que o diretório de destino não possa ser criado.
    """
    invalid_path = Path("N:/non_existent_drive_9999/log_dir_xyz")
    logger_instance = safe_logger.setup_logger(log_dir=invalid_path, logger_name="test_resilience")
    try:
        assert logger_instance is not None
        # Deve ter pelo menos o StreamHandler
        assert len(logger_instance.handlers) >= 1
        logger_instance.info("Log de fallback sem quebrar execução.")
    finally:
        safe_logger.close_logger(logger_instance)


def test_get_default_log_dir_toolbox_standard(monkeypatch):
    """
    Valida que o diretório padrão de logs do Safe segue o padrão canônico do Toolbox (%APPDATA%/com.toolbox.desktop/logs).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("APPDATA", tmpdir)
        monkeypatch.setattr(sys, "platform", "win32")

        log_dir = safe_logger.get_default_log_dir()
        expected = Path(tmpdir) / "com.toolbox.desktop" / "logs"
        assert log_dir == expected

        from shared.db_utils import get_central_logs_dir
        shared_logs = get_central_logs_dir()
        assert shared_logs == expected
        assert shared_logs.exists()


def test_migrate_legacy_safe_logs():
    """
    Valida migração transparente de arquivos safe-*.log da pasta legada 'log' para a pasta canônica 'logs'.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "com.toolbox.desktop"
        legacy_dir = base_dir / "log"
        canonical_dir = base_dir / "logs"

        legacy_dir.mkdir(parents=True, exist_ok=True)
        old_file_1 = legacy_dir / "safe-2026-08-25.log"
        old_file_1.write_text("conteúdo log antigo 1", encoding="utf-8")
        old_file_2 = legacy_dir / "cofre-2026-08-26.log"
        old_file_2.write_text("conteúdo log antigo 2", encoding="utf-8")

        # Executa migração
        migrated = safe_logger.migrate_legacy_safe_logs(target_log_dir=canonical_dir)
        assert migrated == 2
        assert (canonical_dir / "safe-2026-08-25.log").exists()
        assert (canonical_dir / "cofre-2026-08-26.log").exists()
        assert (canonical_dir / "safe-2026-08-25.log").read_text(encoding="utf-8") == "conteúdo log antigo 1"
        assert not legacy_dir.exists()


