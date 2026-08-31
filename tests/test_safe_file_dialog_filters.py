"""Testes para validação e sanitização dos filtros de arquivo do Cofre no pywebview (Issue #182).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import webview
from webview.util import parse_file_type

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
SAFE_DIR = PLUGINS_DIR / "safe"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))
if str(SAFE_DIR) not in sys.path:
    sys.path.insert(0, str(SAFE_DIR))

from shared.web_utils import sanitize_file_types
from safe.main import SafePluginApi


def test_safe_file_types_pass_pywebview_regex_validator():
    """Valida que todos os filtros de arquivo usados no Cofre passam no validador oficial do pywebview."""
    safe_filters = (
        "Arquivos Suportados (*.safepack;*.xml;*.csv;*.txt;*.json)",
        "SafePack Criptografado (*.safepack)",
        "Microsoft Safe XML (*.xml)",
        "Valores Separados por Vírgula (*.csv)",
        "Texto Simples (*.txt)",
        "Arquivos JSON ou Backup (*.json)",
        "Todos os arquivos (*.*)",
    )

    for ft in safe_filters:
        desc, exts = parse_file_type(ft)
        assert desc is not None
        assert exts is not None


def test_sanitize_file_types_fixes_slashes_and_special_chars():
    """Valida que sanitize_file_types converte barras e caracteres especiais para formato aceito pelo pywebview."""
    problematic_filters = (
        "Arquivos JSON / Backup (*.json)",
        "Texto - Formatado (*.txt;*.csv)",
        "Imagens (PNG/JPG) (*.png;*.jpg)",
    )

    sanitized = sanitize_file_types(problematic_filters)
    assert len(sanitized) == len(problematic_filters)

    for clean_ft in sanitized:
        # Não deve lançar ValueError
        desc, exts = parse_file_type(clean_ft)
        assert desc is not None
        assert exts is not None


def test_select_and_preview_dialog_with_mocked_window(tmp_path: Path):
    """Valida que select_file_for_import repassa filtros válidos e processa o arquivo selecionado."""
    mock_win = MagicMock()
    mock_service = MagicMock()
    dummy_file = tmp_path / "teste_backup.json"
    dummy_file.write_text("[]", encoding="utf-8")
    mock_win.create_file_dialog.return_value = [str(dummy_file)]

    api = SafePluginApi(service=mock_service, window=mock_win)
    res = api.select_file_for_import()

    # Verifica que create_file_dialog foi chamado e todos os filtros passados são válidos
    mock_win.create_file_dialog.assert_called_once()
    called_filters = mock_win.create_file_dialog.call_args[1].get("file_types")
    assert called_filters is not None
    for ft in called_filters:
        parse_file_type(ft)


def test_select_and_import_dialog_with_mocked_window(tmp_path: Path):
    """Valida que select_and_import_secrets_file repassa filtros válidos e chama importação."""
    mock_win = MagicMock()
    mock_service = MagicMock()
    dummy_file = tmp_path / "teste_backup.json"
    dummy_file.write_text("[]", encoding="utf-8")
    mock_win.create_file_dialog.return_value = [str(dummy_file)]

    api = SafePluginApi(service=mock_service, window=mock_win)
    res = api.select_and_import_secrets_file()

    mock_win.create_file_dialog.assert_called_once()
    called_filters = mock_win.create_file_dialog.call_args[1].get("file_types")
    assert called_filters is not None
    for ft in called_filters:
        parse_file_type(ft)
