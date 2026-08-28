"""
Testes unitários para o motor criptográfico do plugin Safe.
Valida AES-256-GCM, KDF (Argon2id/PBKDF2), wrapping e zeroization.
"""

import pytest
import sys
from pathlib import Path

# Adiciona plugins ao sys.path
PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from safe import crypto


def test_generate_master_key():
    mk = crypto.generate_master_key()
    assert isinstance(mk, bytes)
    assert len(mk) == 32
    mk2 = crypto.generate_master_key()
    assert mk != mk2


def test_encrypt_and_decrypt_dict_payload():
    mk = crypto.generate_master_key()
    payload = {"username": "admin", "password": "supersecretpassword123!", "custom_field": 42}
    
    ciphertext, iv, auth_tag = crypto.encrypt_payload(payload, mk)
    
    assert len(iv) == 12
    assert len(auth_tag) == 16
    assert isinstance(ciphertext, bytes)
    # Nenhum dado sensível em texto puro no ciphertext
    assert b"supersecretpassword123!" not in ciphertext

    decrypted = crypto.decrypt_payload(ciphertext, iv, auth_tag, mk)
    assert decrypted == payload
    assert decrypted["username"] == "admin"
    assert decrypted["password"] == "supersecretpassword123!"


def test_encrypt_and_decrypt_string_and_bytes():
    mk = crypto.generate_master_key()
    
    # String
    text = "minha-chave-de-api-secreta-9999"
    ct, iv, tag = crypto.encrypt_payload(text, mk)
    dec = crypto.decrypt_payload(ct, iv, tag, mk)
    assert dec == text

    # Raw Bytes
    raw = b"\x00\x01\x02\x03\xff\xfe"
    ct, iv, tag = crypto.encrypt_payload(raw, mk)
    dec = crypto.decrypt_payload(ct, iv, tag, mk, as_json=False)
    assert dec == raw


def test_tampered_ciphertext_raises_integrity_error():
    mk = crypto.generate_master_key()
    payload = "dado super confidencial"
    ct, iv, tag = crypto.encrypt_payload(payload, mk)

    # Modifica 1 byte do ciphertext
    tampered_ct = bytearray(ct)
    tampered_ct[0] ^= 0xFF

    with pytest.raises(crypto.IntegrityError):
        crypto.decrypt_payload(bytes(tampered_ct), iv, tag, mk)


def test_tampered_auth_tag_raises_integrity_error():
    mk = crypto.generate_master_key()
    payload = "dado super confidencial"
    ct, iv, tag = crypto.encrypt_payload(payload, mk)

    # Modifica a tag de autenticação
    tampered_tag = bytearray(tag)
    tampered_tag[0] ^= 0x01

    with pytest.raises(crypto.IntegrityError):
        crypto.decrypt_payload(ct, iv, bytes(tampered_tag), mk)


def test_wrong_master_key_raises_integrity_error():
    mk1 = crypto.generate_master_key()
    mk2 = crypto.generate_master_key()
    ct, iv, tag = crypto.encrypt_payload("teste", mk1)

    with pytest.raises(crypto.IntegrityError):
        crypto.decrypt_payload(ct, iv, tag, mk2)


def test_key_derivation_argon2_and_pbkdf2():
    salt = crypto.generate_salt(16)
    pwd = "MinhaSenhaSuperForte!2026"

    # Argon2id
    k1 = crypto.derive_key(pwd, salt, algorithm="argon2id", params={"iterations": 2, "memory_cost": 32768, "parallelism": 2})
    assert isinstance(k1, bytes)
    assert len(k1) == 32

    # PBKDF2
    k2 = crypto.derive_key(pwd, salt, algorithm="pbkdf2", params={"iterations": 1000})
    assert isinstance(k2, bytes)
    assert len(k2) == 32
    assert k1 != k2


def test_key_wrapping_and_unwrapping():
    master_key = crypto.generate_master_key()
    wrapping_key = crypto.generate_master_key()

    wrapped_ct, iv, tag = crypto.wrap_key(master_key, wrapping_key)
    assert len(iv) == 12
    assert len(tag) == 16
    assert wrapped_ct != master_key

    unwrapped = crypto.unwrap_key(wrapped_ct, iv, tag, wrapping_key)
    assert unwrapped == master_key


def test_zeroization():
    buf = bytearray(b"segredo-extremamente-critico-em-memoria")
    assert any(b != 0 for b in buf)
    crypto.zeroize(buf)
    assert all(b == 0 for b in buf)
