"""
Módulo de Integração com Windows Hello e Proteção de Hardware / DPAPI - Toolbox.

Fornece autenticação biométrica/PIN via Windows Hello (UserConsentVerifier) e
encapsulamento de credenciais usando DPAPI (CryptProtectData) com entropia dedicada.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional, Tuple

# Flags DPAPI
CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _is_windows() -> bool:
    return sys.platform == "win32"


def is_windows_hello_available() -> bool:
    """
    Verifica se o Windows Hello (biometria ou PIN) está disponível e configurado no dispositivo.
    """
    if not _is_windows():
        return False

    # Testa via PowerShell usando Windows.Security.Credentials.UI.UserConsentVerifier com reflexão para AsTask
    ps_cmd = (
        "try { "
        "  Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop; "
        "  [Windows.Security.Credentials.UI.UserConsentVerifier, Windows.Security.Credentials.UI, ContentType=WindowsRuntime] | Out-Null; "
        "  $asTaskGen = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { "
        "    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 "
        "  } | Select-Object -First 1; "
        "  $op = [Windows.Security.Credentials.UI.UserConsentVerifier]::CheckAvailabilityAsync(); "
        "  $asTask = $asTaskGen.MakeGenericMethod([Windows.Security.Credentials.UI.UserConsentVerifierAvailability]); "
        "  $task = $asTask.Invoke($null, @($op)); "
        "  $task.Wait(); "
        "  Write-Output $task.Result.ToString(); "
        "} catch { Write-Output 'Unavailable' }"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        out = (res.stdout or "").strip()
        # Valores possíveis: 'Available', 'DeviceNotPresent', 'NotConfiguredForUser', 'DisabledByPolicy', 'DeviceBusy'
        return "Available" in out
    except Exception:
        return False


def verify_windows_hello(prompt_message: str = "Confirme sua identidade para acessar o Cofre Seguro") -> Tuple[bool, str]:
    """
    Dispara o prompt oficial do Windows Hello para autenticação biométrica ou PIN.
    Retorna (sucesso, mensagem_status).
    """
    if not _is_windows():
        return False, "Windows Hello só é suportado no ambiente Windows."

    # Escapa aspas simples na mensagem do prompt
    safe_msg = prompt_message.replace("'", "''")

    # Script PowerShell para invocar RequestVerificationAsync
    ps_cmd = (
        "try { "
        "  Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop; "
        "  [Windows.Security.Credentials.UI.UserConsentVerifier, Windows.Security.Credentials.UI, ContentType=WindowsRuntime] | Out-Null; "
        "  $asTaskGen = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { "
        "    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 "
        "  } | Select-Object -First 1; "
        f"  $op = [Windows.Security.Credentials.UI.UserConsentVerifier]::RequestVerificationAsync('{safe_msg}'); "
        "  $asTask = $asTaskGen.MakeGenericMethod([Windows.Security.Credentials.UI.UserConsentVerificationResult]); "
        "  $task = $asTask.Invoke($null, @($op)); "
        "  $task.Wait(); "
        "  Write-Output $task.Result.ToString(); "
        "} catch { Write-Output ('Error: ' + $_.Exception.Message) }"
    )

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        out = (res.stdout or "").strip()
        if "Verified" in out:
            return True, "Autenticação biométrica/PIN confirmada com sucesso."
        elif "Canceled" in out:
            return False, "Autenticação cancelada pelo usuário."
        elif "DeviceNotPresent" in out or "NotConfiguredForUser" in out:
            return False, "Windows Hello não está configurado neste computador."
        elif "RetriesExhausted" in out:
            return False, "Tentativas biométricas esgotadas. Utilize o PIN ou senha."
        elif "DisabledByPolicy" in out:
            return False, "Windows Hello desabilitado pelas diretivas do sistema."
        elif "DeviceBusy" in out:
            return False, "O dispositivo de autenticação biométrica está ocupado."
        else:
            return False, f"Autenticação não confirmada pelo Windows Hello ({out or 'Falha'})."
    except Exception as e:
        return False, f"Erro ao solicitar verificação do Windows Hello: {e}"


# ============================================================================
#  Proteção via DPAPI (Data Protection API do Windows)
# ============================================================================

def protect_data_dpapi(data: bytes, entropy: Optional[bytes] = None) -> bytes:
    """
    Criptografa dados usando a chave do usuário atual do Windows via DPAPI (CryptProtectData).
    """
    if not _is_windows():
        raise RuntimeError("DPAPI só é suportado no Windows.")

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    # Prepara input blob
    data_bytes = (ctypes.c_byte * len(data))(*data)
    in_blob = DATA_BLOB(len(data), data_bytes)

    # Entropia opcional (sal adicional)
    entropy_blob_ptr = None
    if entropy:
        ent_bytes = (ctypes.c_byte * len(entropy))(*entropy)
        entropy_blob = DATA_BLOB(len(entropy), ent_bytes)
        entropy_blob_ptr = ctypes.byref(entropy_blob)

    out_blob = DATA_BLOB()

    # Chama CryptProtectData
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "ToolboxSafeMasterKey",
        entropy_blob_ptr,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )

    if not ok:
        err = kernel32.GetLastError()
        raise RuntimeError(f"CryptProtectData falhou com código de erro {err}")

    try:
        res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return res
    finally:
        kernel32.LocalFree(out_blob.pbData)


def unprotect_data_dpapi(encrypted_data: bytes, entropy: Optional[bytes] = None) -> bytes:
    """
    Decriptografa dados protegidos por DPAPI para o usuário atual do Windows (CryptUnprotectData).
    """
    if not _is_windows():
        raise RuntimeError("DPAPI só é suportado no Windows.")

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    enc_bytes = (ctypes.c_byte * len(encrypted_data))(*encrypted_data)
    in_blob = DATA_BLOB(len(encrypted_data), enc_bytes)

    entropy_blob_ptr = None
    if entropy:
        ent_bytes = (ctypes.c_byte * len(entropy))(*entropy)
        entropy_blob = DATA_BLOB(len(entropy), ent_bytes)
        entropy_blob_ptr = ctypes.byref(entropy_blob)

    out_blob = DATA_BLOB()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        entropy_blob_ptr,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )

    if not ok:
        err = kernel32.GetLastError()
        raise RuntimeError(f"CryptUnprotectData falhou com código de erro {err}")

    try:
        res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return res
    finally:
        kernel32.LocalFree(out_blob.pbData)
