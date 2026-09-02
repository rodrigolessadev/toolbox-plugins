"""Testes para garantir o foco em primeiro plano do prompt do Windows Hello no Cofre (Issue #185).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
SAFE_DIR = PLUGINS_DIR / "safe"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))
if str(SAFE_DIR) not in sys.path:
    sys.path.insert(0, str(SAFE_DIR))

from safe.windows_hello import allow_foreground_focus, verify_windows_hello


def test_allow_foreground_focus_execution():
    """Valida que allow_foreground_focus executa e retorna boolean em ambiente Windows."""
    with patch("safe.windows_hello._is_windows", return_value=True):
        res = allow_foreground_focus()
        assert isinstance(res, bool)


def test_allow_foreground_focus_on_non_windows():
    """Valida que allow_foreground_focus retorna False graciosamente em ambiente não-Windows."""
    with patch("safe.windows_hello._is_windows", return_value=False):
        res = allow_foreground_focus()
        assert res is False


def test_verify_windows_hello_calls_allow_foreground_focus():
    """Valida que verify_windows_hello invoca allow_foreground_focus antes de disparar o prompt."""
    with patch("safe.windows_hello._is_windows", return_value=True), \
         patch("safe.windows_hello.allow_foreground_focus") as mock_focus, \
         patch("subprocess.run") as mock_run:
        
        mock_proc = MagicMock()
        mock_proc.stdout = "Verified\n"
        mock_run.return_value = mock_proc

        ok, msg = verify_windows_hello("Acesso ao Cofre")
        assert ok is True
        mock_focus.assert_called_once()
        mock_run.assert_called_once()

        # Valida que o script PowerShell contém a chamada Win32 de foco
        called_cmd = mock_run.call_args[0][0]
        ps_script = called_cmd[4]
        assert "Win32Foreground" in ps_script
        assert "AllowSetForegroundWindow" in ps_script


def test_verify_windows_hello_handles_canceled_status():
    """Valida que quando o usuário cancela o prompt, o status Canceled é tratado perfeitamente."""
    with patch("safe.windows_hello._is_windows", return_value=True), \
         patch("subprocess.run") as mock_run:
        
        mock_proc = MagicMock()
        mock_proc.stdout = "Canceled\n"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        ok, msg = verify_windows_hello("Acesso ao Cofre")
        assert ok is False
        assert "cancelada pelo usuário" in msg


def test_verify_windows_hello_with_hwnd():
    """Valida que verify_windows_hello inclui o handle da janela no script PowerShell e tenta interop."""
    with patch("safe.windows_hello._is_windows", return_value=True), \
         patch("subprocess.run") as mock_run:
        
        mock_proc = MagicMock()
        mock_proc.stdout = "Verified\n"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        ok, msg = verify_windows_hello("Acesso ao Cofre", window_handle=123456)
        assert ok is True
        assert "sucesso" in msg

        called_cmd = mock_run.call_args[0][0]
        ps_script = called_cmd[4]
        assert "123456" in ps_script
        assert "IUserConsentVerifierInterop" in ps_script


def test_verify_windows_hello_handles_error_status():
    """Valida o tratamento de erros de runtime do PowerShell/WinRT."""
    with patch("safe.windows_hello._is_windows", return_value=True), \
         patch("subprocess.run") as mock_run:
        
        mock_proc = MagicMock()
        mock_proc.stdout = "Error: Falha no subsistema de segurança WinRT\n"
        mock_proc.stderr = "Exceção em System.Runtime.WindowsRuntime\n"
        mock_run.return_value = mock_proc

        ok, msg = verify_windows_hello("Acesso ao Cofre")
        assert ok is False
        assert "Falha na execução do Windows Hello" in msg

