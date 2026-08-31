"""Testes unitários para inicialização assíncrona e otimização de performance do Cofre (Issue #187).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
SAFE_DIR = PLUGINS_DIR / "safe"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))
if str(SAFE_DIR) not in sys.path:
    sys.path.insert(0, str(SAFE_DIR))

from safe.service import SafeService
from safe.main import SafePluginApi
from safe.db import SafeDatabase
import safe.windows_hello as windows_hello


def test_safe_get_status_response_time_under_100ms(tmp_path: Path):
    """Garante que get_status responda instantaneamente (< 100ms) sem travar no PowerShell."""
    db_path = tmp_path / "fast_startup.db"
    service = SafeService(db_path)

    start = time.time()
    status = service.get_status()
    duration = time.time() - start

    assert isinstance(status, dict)
    assert "status" in status
    assert duration < 0.1, f"get_status demorou {duration:.3f}s (esperado < 0.1s)"


def test_windows_hello_async_prewarm_and_cache():
    """Valida que is_windows_hello_available retorna de forma não-bloqueante com fallback assíncrono."""
    with patch("safe.windows_hello._is_windows", return_value=True), \
         patch("safe.windows_hello.start_background_prewarm") as mock_prewarm:
        
        # Limpa cache temporariamente
        windows_hello._hello_cache_result = None
        windows_hello._hello_cache_timestamp = 0.0

        res = windows_hello.is_windows_hello_available(allow_async_fallback=True)
        assert res is True
        mock_prewarm.assert_called_once()


def test_api_check_windows_hello_availability(tmp_path: Path):
    """Valida que SafePluginApi.check_windows_hello_availability responde com sucesso."""
    db_path = tmp_path / "api_test.db"
    service = SafeService(db_path)
    api = SafePluginApi(service=service)

    with patch("safe.windows_hello.is_windows_hello_available", return_value=True):
        res = api.check_windows_hello_availability(force_refresh=True)
        assert res["success"] is True
        assert res["available"] is True


def test_db_legacy_migration_flag_persisted(tmp_path: Path):
    """Garante que a flag legacy_migration_checked é persistida e evita varreduras redundantes."""
    db_path = tmp_path / "migration_test.db"
    
    with patch("safe.db.get_default_db_path", return_value=db_path):
        # Primeira inicialização: executa migração e grava flag
        db1 = SafeDatabase(db_path)
        assert db1.get_setting("legacy_migration_checked") == "1"

        # Segunda inicialização: não deve reexecutar migrate_legacy_vault_if_exists
        with patch.object(SafeDatabase, "migrate_legacy_vault_if_exists") as mock_migrate:
            db2 = SafeDatabase(db_path)
            mock_migrate.assert_not_called()
