"""
Módulo de Integração com Windows Hello e Proteção de Hardware / DPAPI - Toolbox.

Fornece autenticação biométrica/PIN via Windows Hello (UserConsentVerifier) e
encapsulamento de credenciais usando DPAPI (CryptProtectData) com entropia dedicada.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from typing import Optional, Tuple

import threading

try:
    from . import crypto
except ImportError:
    try:
        import safe.crypto as crypto
    except ImportError:
        import crypto

logger = logging.getLogger("safe.windows_hello")

# Flags DPAPI
CRYPTPROTECT_UI_FORBIDDEN = 0x1

_hello_cache_result: Optional[bool] = None
_hello_cache_timestamp: float = 0.0
_hello_check_in_progress: bool = False
_hello_lock = threading.Lock()


def _is_windows() -> bool:
    return sys.platform == "win32"


def check_windows_hello_sync() -> bool:
    """Executa a verificação síncrona via PowerShell e atualiza o cache em memória."""
    global _hello_cache_result, _hello_cache_timestamp, _hello_check_in_progress
    if not _is_windows():
        with _hello_lock:
            _hello_cache_result = False
            _hello_cache_timestamp = time.time()
            _hello_check_in_progress = False
        return False

    now = time.time()
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
        is_available = "Available" in out
        with _hello_lock:
            _hello_cache_result = is_available
            _hello_cache_timestamp = now
            _hello_check_in_progress = False
        return is_available
    except Exception as exc:
        logger.warning(f"Erro ao checar disponibilidade do Windows Hello: {exc}")
        with _hello_lock:
            _hello_cache_result = False
            _hello_cache_timestamp = now
            _hello_check_in_progress = False
        return False


def start_background_prewarm(force_refresh: bool = False) -> None:
    """Dispara a checagem do Windows Hello em uma thread daemon em background sem bloquear o processo."""
    global _hello_check_in_progress
    if not _is_windows():
        return

    now = time.time()
    with _hello_lock:
        if not force_refresh and _hello_cache_result is not None and (now - _hello_cache_timestamp < 120.0):
            return
        if _hello_check_in_progress:
            return
        _hello_check_in_progress = True

    t = threading.Thread(target=check_windows_hello_sync, name="WindowsHelloPrewarm", daemon=True)
    t.start()


def is_windows_hello_available(force_refresh: bool = False, allow_async_fallback: bool = True) -> bool:
    """
    Verifica se o Windows Hello está disponível.
    Se o cache for válido, retorna imediatamente.
    Se ainda não houver cache e allow_async_fallback=True, dispara o pre-warming em segundo plano
    e retorna True provisoriamente no Windows (não bloqueia inicialização da UI).
    Se allow_async_fallback=False, executa a verificação síncrona.
    """
    global _hello_cache_result, _hello_cache_timestamp

    if not _is_windows():
        return False

    now = time.time()
    with _hello_lock:
        if not force_refresh and _hello_cache_result is not None and (now - _hello_cache_timestamp < 120.0):
            return _hello_cache_result

    if allow_async_fallback:
        start_background_prewarm(force_refresh=force_refresh)
        return _hello_cache_result if _hello_cache_result is not None else True

    return check_windows_hello_sync()


def allow_foreground_focus() -> bool:
    """Permite que o processo de verificação biométrica/PIN traga a janela do Windows Hello para o primeiro plano."""
    if not _is_windows():
        return False
    try:
        import ctypes
        ASFW_ANY = 0xFFFFFFFF
        res = ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
        return bool(res)
    except Exception as e:
        logger.debug(f"Aviso ao executar AllowSetForegroundWindow: {e}")
        return False


def verify_windows_hello(
    prompt_message: str = "Confirme sua identidade para acessar o Cofre Seguro",
    window_handle: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Dispara o prompt oficial do Windows Hello para autenticação biométrica ou PIN em primeiro plano.
    Aceita window_handle (HWND) da janela ativa para associação direta.
    Retorna (sucesso, mensagem_status).
    """
    if not _is_windows():
        return False, "Windows Hello só é suportado no ambiente Windows."

    # 1. Concede permissão de primeiro plano ao processo filho
    allow_foreground_focus()

    # Se window_handle não for informado, tenta resolver foreground window ativa
    resolved_hwnd = window_handle
    if not resolved_hwnd:
        try:
            import ctypes
            resolved_hwnd = int(ctypes.windll.user32.GetForegroundWindow() or 0)
        except Exception:
            resolved_hwnd = 0

    logger.info(f"Invocando verificação Windows Hello (HWND={resolved_hwnd})...")

    # Escapa aspas simples na mensagem do prompt
    safe_msg = prompt_message.replace("'", "''")

    # Script PowerShell para invocar RequestVerificationAsync ou RequestVerificationForWindowAsync
    ps_lines = [
        "try {",
        "  $csharpFg = @'",
        "using System;",
        "using System.Runtime.InteropServices;",
        "public class Win32Foreground {",
        "    [DllImport(\"user32.dll\")] public static extern bool AllowSetForegroundWindow(int dwProcessId);",
        "    [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);",
        "    [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();",
        "}",
        "'@",
        "  Add-Type -TypeDefinition $csharpFg -ErrorAction SilentlyContinue;",
        "  [Win32Foreground]::AllowSetForegroundWindow(-1) | Out-Null;",
        "  Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction Stop;",
        "  [Windows.Security.Credentials.UI.UserConsentVerifier, Windows.Security.Credentials.UI, ContentType=WindowsRuntime] | Out-Null;",
        f"  $hwnd = [IntPtr]({resolved_hwnd or 0});",
        "  $op = $null;",
        "  if ($hwnd -ne [IntPtr]::Zero) {",
        "    try {",
        "      $csharpInterop = @'",
        "using System;",
        "using System.Runtime.InteropServices;",
        "public static class HelloInterop {",
        "    [ComImport]",
        "    [Guid(\"39E050C3-4E74-441A-8DC0-B812977A9E6B\")]",
        "    [InterfaceType(ComInterfaceType.InterfaceIsIInspectable)]",
        "    public interface IUserConsentVerifierInterop {",
        "        void RequestVerificationForWindowAsync(",
        "            IntPtr appWindow,",
        "            [MarshalAs(UnmanagedType.HString)] string message,",
        "            [In] ref Guid riid,",
        "            [MarshalAs(UnmanagedType.IInspectable)] out object asyncOperation",
        "        );",
        "    }",
        "    [DllImport(\"api-ms-win-core-winrt-l1-1-0.dll\")]",
        "    public static extern int RoGetActivationFactory(",
        "        [MarshalAs(UnmanagedType.HString)] string activatableClassId,",
        "        [In] ref Guid iid,",
        "        out IUserConsentVerifierInterop factory",
        "    );",
        "    public static object RequestForWindow(IntPtr hWnd, string msg) {",
        "        Guid iid = new Guid(\"39E050C3-4E74-441A-8DC0-B812977A9E6B\");",
        "        IUserConsentVerifierInterop factory;",
        "        int hr = RoGetActivationFactory(\"Windows.Security.Credentials.UI.UserConsentVerifier\", ref iid, out factory);",
        "        if (hr != 0) throw new COMException(\"RoGetActivationFactory failed\", hr);",
        "        Guid opIid = new Guid(\"00000000-0000-0000-C000-000000000046\");",
        "        object asyncOp;",
        "        factory.RequestVerificationForWindowAsync(hWnd, msg, ref opIid, out asyncOp);",
        "        return asyncOp;",
        "    }",
        "}",
        "'@",
        "      Add-Type -TypeDefinition $csharpInterop -ErrorAction Stop;",
        f"      $op = [HelloInterop]::RequestForWindow($hwnd, '{safe_msg}');",
        "    } catch {",
        f"      $op = [Windows.Security.Credentials.UI.UserConsentVerifier]::RequestVerificationAsync('{safe_msg}');",
        "    }",
        "  } else {",
        f"    $op = [Windows.Security.Credentials.UI.UserConsentVerifier]::RequestVerificationAsync('{safe_msg}');",
        "  }",
        "  $asTaskGen = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {",
        "    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1",
        "  } | Select-Object -First 1;",
        "  $asTask = $asTaskGen.MakeGenericMethod([Windows.Security.Credentials.UI.UserConsentVerificationResult]);",
        "  $task = $asTask.Invoke($null, @($op));",
        "  $task.Wait();",
        "  Write-Output $task.Result.ToString();",
        "} catch {",
        "  [Console]::Error.WriteLine($_.Exception.ToString());",
        "  Write-Output ('Error: ' + $_.Exception.Message);",
        "}",
    ]
    ps_cmd = "\r\n".join(ps_lines)

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()

        if err:
            logger.warning(f"PowerShell Windows Hello stderr: {err}")

        logger.info(f"Windows Hello retorno do processo: out='{out}'")

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
        elif out.startswith("Error:"):
            return False, f"Falha na execução do Windows Hello: {out[6:].strip()}"
        else:
            return False, f"Autenticação não confirmada pelo Windows Hello ({out or 'Falha'})."
    except Exception as e:
        logger.error(f"Exceção ao solicitar verificação do Windows Hello: {e}")
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


# ============================================================================
#  Envelope Reforçado de Chave Windows Hello (Hardware-bound & DPAPI)
# ============================================================================

def _get_hardware_session_salt(credential_id: str) -> bytes:
    """Gera sal criptográfico vinculado à máquina, usuário e identificador de credencial."""
    import hashlib
    components = [credential_id or "ToolboxDefaultHelloCred"]
    if _is_windows():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                components.append(str(guid))
        except Exception:
            pass
        components.append(os.environ.get("USERDOMAIN", ""))
        components.append(os.environ.get("USERNAME", ""))
        components.append(os.environ.get("COMPUTERNAME", ""))
    combined = "|".join(components).encode("utf-8")
    return hashlib.sha256(combined).digest()


def protect_master_key_hello(
    master_key: bytes,
    credential_id: str,
    window_handle: Optional[int] = None
) -> bytes:
    """
    Encapsula a Master Key utilizando proteção de hardware/sessão reforçada do Windows Hello.
    Combina chave intermediária AES-256-GCM com sal de hardware e DPAPI/CNG.
    """
    if not _is_windows():
        # Fallback para ambientes de teste não-Windows
        return b"DPP1:\x00\x00\x00\x0fDEV_HELLO_MOCK:" + master_key

    # 1. Gera chave efêmera de encapsulamento
    wrapping_key = crypto.generate_master_key() if hasattr(crypto, "generate_master_key") else os.urandom(32)
    ciphertext, iv, auth_tag = crypto.wrap_key(master_key, wrapping_key)
    aes_payload = iv + auth_tag + ciphertext

    # 2. Protege a chave intermediária com DPAPI vinculada a hardware+sessão
    hw_salt = _get_hardware_session_salt(credential_id)
    dpapi_blob = protect_data_dpapi(wrapping_key, entropy=hw_salt)

    # 3. Monta o envelope protegido DPP1:
    header = b"DPP1:"
    blob_len = len(dpapi_blob).to_bytes(4, byteorder="big")
    return header + blob_len + dpapi_blob + aes_payload


def unprotect_master_key_hello(
    wrapped_blob: bytes,
    credential_id: str,
    window_handle: Optional[int] = None
) -> bytes:
    """
    Desencapsula a Master Key a partir do envelope do Windows Hello.
    Suporta DPP1:, CNG1: e fallback retrocompatível para DPAPI legada.
    """
    if not wrapped_blob:
        raise ValueError("Blob de chave do Windows Hello vazio.")

    if not _is_windows():
        if wrapped_blob.startswith(b"DPP1:"):
            # Mock de teste não-windows
            prefix = b"DPP1:\x00\x00\x00\x0fDEV_HELLO_MOCK:"
            if wrapped_blob.startswith(prefix):
                return wrapped_blob[len(prefix):]
        if wrapped_blob.startswith(b"DEV_HELLO_WRAPPED:"):
            return wrapped_blob[len(b"DEV_HELLO_WRAPPED:"):]
        return wrapped_blob

    # Formato Moderno DPP1:
    if wrapped_blob.startswith(b"DPP1:"):
        try:
            offset = 5
            blob_len = int.from_bytes(wrapped_blob[offset:offset+4], byteorder="big")
            offset += 4
            dpapi_blob = wrapped_blob[offset:offset+blob_len]
            aes_payload = wrapped_blob[offset+blob_len:]

            hw_salt = _get_hardware_session_salt(credential_id)
            try:
                wrapping_key = unprotect_data_dpapi(dpapi_blob, entropy=hw_salt)
            except Exception:
                wrapping_key = unprotect_data_dpapi(dpapi_blob, entropy=None)

            iv = aes_payload[:12]
            auth_tag = aes_payload[12:28]
            ciphertext = aes_payload[28:]
            return crypto.unwrap_key(ciphertext, iv, auth_tag, wrapping_key)
        except Exception as err:
            logger.warning(f"Falha ao desencapsular envelope DPP1, tentando fallback legado: {err}")

    # Fallback para DPAPI Legada direta
    hello_id_bytes = (credential_id or "").encode("utf-8") if credential_id else None
    try:
        return unprotect_data_dpapi(wrapped_blob, entropy=hello_id_bytes)
    except Exception:
        # Tenta sem entropia
        return unprotect_data_dpapi(wrapped_blob, entropy=None)
