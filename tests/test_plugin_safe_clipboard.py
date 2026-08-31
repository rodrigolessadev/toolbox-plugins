"""
Testes unitários para o módulo de Área de Transferência Segura (Secure Clipboard) do plugin Safe.
"""

import sys
import time
from pathlib import Path
import pytest

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from safe.clipboard import (
    copy_to_clipboard_secure,
    get_clipboard_text,
    clear_clipboard,
)
from safe import main as safe_main


def test_copy_to_clipboard_secure_basic():
    """Valida a gravação e leitura básica no clipboard seguro."""
    test_secret = "SafePass#Test2026!Basic"
    ok = copy_to_clipboard_secure(test_secret, auto_clear_seconds=0)
    assert ok is True

    copied = get_clipboard_text()
    assert copied == test_secret

    # Limpeza manual
    assert clear_clipboard() is True
    assert get_clipboard_text() in (None, "")


def test_copy_to_clipboard_auto_clear():
    """Valida a higienização automática do clipboard após o tempo configurado."""
    test_secret = "TemporaryP@sswordToClear#999"
    ok = copy_to_clipboard_secure(test_secret, auto_clear_seconds=1)
    assert ok is True

    # Verifica que imediatamente após copiar o texto está presente
    assert get_clipboard_text() == test_secret

    # Aguarda o timer de 1s disparar
    time.sleep(1.3)

    # O clipboard deve ter sido limpo automaticamente
    assert get_clipboard_text() in (None, "")


def test_auto_clear_does_not_overwrite_if_user_copied_something_else():
    """Valida que o auto-clear não limpa o clipboard se o usuário copiou outro texto depois."""
    secret_a = "SecretA#First"
    secret_b = "SecretB#UserCopiedAfter"

    # Agenda clear para o secret_a em 1 segundo
    copy_to_clipboard_secure(secret_a, auto_clear_seconds=1)
    assert get_clipboard_text() == secret_a

    # Usuário copia secret_b (sem timer ou com timer mais longo)
    time.sleep(0.2)
    copy_to_clipboard_secure(secret_b, auto_clear_seconds=0)
    assert get_clipboard_text() == secret_b

    # Aguarda o primeiro timer expirar
    time.sleep(1.2)

    # O secret_b deve continuar intacto porque não corresponde ao hash do secret_a
    assert get_clipboard_text() == secret_b

    # Limpeza final
    clear_clipboard()


def test_safe_plugin_api_copy_secret_to_clipboard(tmp_path):
    """Valida o método RPC copy_secret_to_clipboard exposto para o frontend."""
    from safe.service import SafeService

    svc = SafeService(db_path=tmp_path / "test_cb_vault.db")
    api = safe_main.SafePluginApi(service=svc)

    res = api.copy_secret_to_clipboard("TokenFromApi#123", auto_clear_seconds=0)
    assert res["success"] is True
    assert "30s" in res["message"] or "Copiado" in res["message"]
    assert get_clipboard_text() == "TokenFromApi#123"

    clear_clipboard()
