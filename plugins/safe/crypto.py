"""
Motor Criptográfico do Plugin Safe (Cofre Seguro) - Toolbox.

Fornece criptografia autenticada AES-256-GCM, derivação de chaves via Argon2id
e PBKDF2-HMAC-SHA256, encapsulamento de chaves e utilitários de limpeza de memória (zeroization).
"""

from __future__ import annotations

import json
import os
import secrets
from typing import Any, Dict, Optional, Tuple, Union

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.exceptions import InvalidTag
except ImportError:
    AESGCM = None
    Argon2id = None
    PBKDF2HMAC = None
    hashes = None
    InvalidTag = Exception


class CryptoError(Exception):
    """Exceção base para erros criptográficos."""
    pass


class DecryptionError(CryptoError):
    """Falha ao decriptografar dados ou chave (autenticação falhou ou chave incorreta)."""
    pass


class IntegrityError(CryptoError):
    """Tag de autenticação inválida ou dados corrompidos."""
    pass


class KeyDerivationError(CryptoError):
    """Erro durante derivação de chave."""
    pass


def generate_master_key() -> bytes:
    """Gera uma chave mestra criptograficamente segura de 256 bits (32 bytes)."""
    return secrets.token_bytes(32)


def generate_salt(length: int = 16) -> bytes:
    """Gera um salt aleatório criptograficamente seguro."""
    return secrets.token_bytes(length)


def derive_key_argon2(
    password: str,
    salt: bytes,
    time_cost: int = 3,
    memory_cost: int = 65536,
    parallelism: int = 4,
    length: int = 32,
) -> bytes:
    """
    Deriva uma chave de 256 bits a partir de senha usando Argon2id.
    """
    if Argon2id is None:
        raise KeyDerivationError("Módulo cryptography.hazmat.primitives.kdf.argon2 não disponível.")
    try:
        kdf = Argon2id(
            salt=salt,
            length=length,
            iterations=time_cost,
            lanes=parallelism,
            memory_cost=memory_cost,
            ad=None,
            secret=None,
        )
        return kdf.derive(password.encode("utf-8"))
    except Exception as e:
        raise KeyDerivationError(f"Falha na derivação Argon2id: {e}") from e


def derive_key_pbkdf2(
    password: str,
    salt: bytes,
    iterations: int = 100000,
    length: int = 32,
) -> bytes:
    """
    Deriva uma chave de 256 bits usando PBKDF2-HMAC-SHA256.
    """
    if PBKDF2HMAC is None:
        raise KeyDerivationError("Módulo cryptography PBKDF2HMAC não disponível.")
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8"))
    except Exception as e:
        raise KeyDerivationError(f"Falha na derivação PBKDF2: {e}") from e


def derive_key(
    password: str,
    salt: bytes,
    algorithm: str = "argon2id",
    params: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Deriva chave de acordo com o algoritmo e parâmetros informados.
    """
    params = params or {}
    algo_lower = (algorithm or "argon2id").lower()

    if "argon2" in algo_lower:
        time_cost = params.get("iterations", params.get("time_cost", 3))
        memory_cost = params.get("memory_cost", 65536)
        parallelism = params.get("parallelism", 4)
        return derive_key_argon2(
            password=password,
            salt=salt,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
        )
    elif "pbkdf2" in algo_lower:
        iterations = params.get("iterations", 100000)
        return derive_key_pbkdf2(password=password, salt=salt, iterations=iterations)
    else:
        raise KeyDerivationError(f"Algoritmo de derivação não suportado: {algorithm}")


def encrypt_payload(
    payload: Union[Dict[str, Any], str, bytes],
    master_key: bytes,
    associated_data: Optional[bytes] = None,
) -> Tuple[bytes, bytes, bytes]:
    """
    Criptografa um payload usando AES-256-GCM.
    
    Retorna:
      (ciphertext, iv, auth_tag) onde iv tem 12 bytes e auth_tag tem 16 bytes.
    """
    if AESGCM is None:
        raise CryptoError("Biblioteca cryptography (AESGCM) não disponível.")
    if len(master_key) != 32:
        raise ValueError("A Master Key deve ter exatamente 32 bytes (256 bits).")

    if isinstance(payload, dict):
        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    elif isinstance(payload, (bytes, bytearray)):
        raw_bytes = bytes(payload)
    else:
        raise TypeError("O payload deve ser dict, str ou bytes.")

    iv = secrets.token_bytes(12)  # 96-bit nonce padrão AES-GCM
    aesgcm = AESGCM(master_key)

    # AESGCM.encrypt no cryptography anexa os 16 bytes de auth tag ao final do ciphertext
    encrypted_blob = aesgcm.encrypt(iv, raw_bytes, associated_data)
    ciphertext = encrypted_blob[:-16]
    auth_tag = encrypted_blob[-16:]

    return ciphertext, iv, auth_tag


def decrypt_payload(
    ciphertext: bytes,
    iv: bytes,
    auth_tag: bytes,
    master_key: bytes,
    associated_data: Optional[bytes] = None,
    as_json: bool = True,
) -> Union[Dict[str, Any], str, bytes]:
    """
    Decriptografa dados cifrados em AES-256-GCM verificando a autenticação.
    """
    if AESGCM is None:
        raise CryptoError("Biblioteca cryptography (AESGCM) não disponível.")
    if len(master_key) != 32:
        raise ValueError("A Master Key deve ter exatamente 32 bytes (256 bits).")
    if len(iv) != 12:
        raise ValueError("O IV deve ter exatamente 12 bytes (96 bits).")
    if len(auth_tag) != 16:
        raise ValueError("A Auth Tag deve ter exatamente 16 bytes (128 bits).")

    aesgcm = AESGCM(master_key)
    combined = ciphertext + auth_tag

    try:
        decrypted_bytes = aesgcm.decrypt(iv, combined, associated_data)
    except InvalidTag as e:
        raise IntegrityError("Falha na autenticação dos dados cifrados (chave incorreta ou dados corrompidos).") from e
    except Exception as e:
        raise DecryptionError(f"Erro ao decriptografar payload: {e}") from e

    if not as_json:
        return decrypted_bytes

    try:
        text = decrypted_bytes.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    except UnicodeDecodeError:
        return decrypted_bytes


def wrap_key(key_to_wrap: bytes, wrapping_key: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Encapsula (wrap) uma chave simétrica com outra chave de 256 bits via AES-256-GCM.
    Retorna (wrapped_key_ciphertext, iv, auth_tag).
    """
    return encrypt_payload(key_to_wrap, wrapping_key, associated_data=b"toolbox-key-wrap-v1")


def unwrap_key(wrapped_key: bytes, iv: bytes, auth_tag: bytes, wrapping_key: bytes) -> bytes:
    """
    Desencapsula (unwrap) uma chave simétrica cifrada.
    """
    result = decrypt_payload(
        wrapped_key, iv, auth_tag, wrapping_key, associated_data=b"toolbox-key-wrap-v1", as_json=False
    )
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    raise DecryptionError("Resultado do unwrap de chave inválido.")


def zeroize(buffer: Union[bytearray, memoryview, list]) -> None:
    """
    Sobrescreve o buffer em memória com zeros para descarte seguro.
    """
    if isinstance(buffer, bytearray):
        for i in range(len(buffer)):
            buffer[i] = 0
    elif isinstance(buffer, memoryview):
        if not buffer.readonly:
            for i in range(len(buffer)):
                buffer[i] = 0
    elif isinstance(buffer, list):
        for i in range(len(buffer)):
            buffer[i] = 0


SAFEPACK_MAGIC = b"SAFEPACK\x01\x00\x00\x00"  # 12 bytes


def pack_safepack_container(payload_data: Any, backup_password: str) -> bytes:
    """
    Empacota e criptografa dados em um container portátil .safepack protegido por senha.
    Utiliza derivação de chave Argon2id e criptografia AES-256-GCM.
    
    Estrutura do arquivo binário:
      [12 bytes] Magic Header ("SAFEPACK\x01\x00\x00\x00")
      [16 bytes] Salt KDF
      [12 bytes] IV (Nonce AES-GCM)
      [16 bytes] Auth Tag AES-GCM
      [N bytes]  Ciphertext
    """
    if not backup_password or len(backup_password.strip()) < 4:
        raise ValueError("A senha de backup deve conter pelo menos 4 caracteres.")

    salt = generate_salt(16)
    kdf_params = {"iterations": 3, "memory_cost": 65536, "parallelism": 4}
    wrapping_key = derive_key(backup_password, salt, algorithm="argon2id", params=kdf_params)

    ciphertext, iv, auth_tag = encrypt_payload(
        payload_data,
        wrapping_key,
        associated_data=b"toolbox-safepack-v1",
    )

    return SAFEPACK_MAGIC + salt + iv + auth_tag + ciphertext


def unpack_safepack_container(safepack_bytes: bytes, backup_password: str) -> Any:
    """
    Desempacota e decriptografa um container .safepack verificando a integridade.
    Lança DecryptionError ou IntegrityError se a senha estiver incorreta ou dados corrompidos.
    """
    if not safepack_bytes or len(safepack_bytes) < 56:  # 12 + 16 + 12 + 16 = 56 bytes mínimos
        raise ValueError("Arquivo .safepack inválido ou corrompido (tamanho insuficiente).")

    if not safepack_bytes.startswith(SAFEPACK_MAGIC[:8]):
        raise ValueError("Cabeçalho do arquivo .safepack inválido (não é um arquivo SafePack oficial).")

    if not backup_password:
        raise ValueError("Senha de backup necessária para restaurar o arquivo .safepack.")

    header = safepack_bytes[:12]
    salt = safepack_bytes[12:28]
    iv = safepack_bytes[28:40]
    auth_tag = safepack_bytes[40:56]
    ciphertext = safepack_bytes[56:]

    kdf_params = {"iterations": 3, "memory_cost": 65536, "parallelism": 4}
    wrapping_key = derive_key(backup_password, salt, algorithm="argon2id", params=kdf_params)

    try:
        return decrypt_payload(
            ciphertext,
            iv,
            auth_tag,
            wrapping_key,
            associated_data=b"toolbox-safepack-v1",
            as_json=True,
        )
    except (IntegrityError, InvalidTag) as e:
        raise IntegrityError("Senha de backup incorreta ou arquivo de backup corrompido.") from e
