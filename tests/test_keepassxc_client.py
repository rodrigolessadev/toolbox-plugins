"""
Testes unitários para o cliente IPC do KeePassXC (plugins/shared/keepassxc_client.py).
Valida comunicação, criptografia Native Messaging, persistência no SQLite e tratamento de erros.
"""

from __future__ import annotations

import base64
import io
import json
import sqlite3
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import os
import sys
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

import nacl.public
import nacl.utils
from nacl.public import Box, PrivateKey, PublicKey

from shared.keepassxc_client import (
    KeePassXCClient,
    KeePassXCError,
    KeePassXCNotRunningError,
    KeePassXCLockedError,
    KeePassXCAssociationError,
)


class MockPipeTransport:
    """Simula um named pipe duplex com respostas pré-programadas do protocolo KeePassXC."""

    def __init__(self):
        self.client_writes = bytearray()
        self.server_reads = io.BytesIO()
        self.server_private_key = PrivateKey.generate()
        self.server_public_key = self.server_private_key.public_key
        self.session_box: Box | None = None

    def write(self, data: bytes) -> None:
        self.client_writes.extend(data)
        # Ao receber mensagem do cliente, processa e prepara resposta automática
        self._process_client_message()

    def read(self, n: int) -> bytes:
        return self.server_reads.read(n)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    def _queue_server_message(self, msg_dict: dict) -> None:
        payload = json.dumps(msg_dict).encode("utf-8")
        header = struct.pack("<I", len(payload))
        # Salva a posição atual, anexa e reposiciona para leitura
        cur_pos = self.server_reads.tell()
        self.server_reads.seek(0, io.SEEK_END)
        self.server_reads.write(header + payload)
        self.server_reads.seek(cur_pos)

    def _process_client_message(self) -> None:
        # Se temos pelo menos 4 bytes de header
        if len(self.client_writes) < 4:
            return
        msg_len = struct.unpack("<I", self.client_writes[:4])[0]
        if len(self.client_writes) < 4 + msg_len:
            return

        raw_payload = self.client_writes[4:4 + msg_len]
        self.client_writes = self.client_writes[4 + msg_len:]
        req = json.loads(raw_payload.decode("utf-8"))
        action = req.get("action")

        if action == "change-public-keys":
            client_pub_bytes = base64.b64decode(req["publicKey"])
            client_pub = PublicKey(client_pub_bytes)
            self.session_box = Box(self.server_private_key, client_pub)
            server_pub_b64 = base64.b64encode(bytes(self.server_public_key)).decode("utf-8")
            self._queue_server_message({
                "action": "change-public-keys",
                "publicKey": server_pub_b64,
                "success": "true"
            })
        elif "message" in req and "nonce" in req:
            # Mensagem criptografada
            nonce = base64.b64decode(req["nonce"])
            ciphertext = base64.b64decode(req["message"])
            decrypted_json = json.loads(self.session_box.decrypt(ciphertext, nonce).decode("utf-8"))
            inner_action = decrypted_json.get("action")

            resp_payload = {"action": inner_action, "success": "true"}
            if inner_action == "associate":
                resp_payload["id"] = "test-toolbox-client-id-123"
            elif inner_action == "test-associate":
                resp_payload["success"] = "true"
            elif inner_action == "get-logins":
                resp_payload["entries"] = [
                    {
                        "name": "AWS Production Database",
                        "login": "admin_master",
                        "password": "SuperSecretPassword123!",
                        "uuid": "1111-2222-3333-4444"
                    }
                ]
            elif inner_action == "get-totp":
                resp_payload["totp"] = "852963"
            elif inner_action == "generate-password":
                resp_payload["password"] = "G3n3r4t3d-P@ssw0rd!"
            elif inner_action == "lock-database":
                resp_payload["success"] = "true"

            # Criptografa a resposta de volta para o cliente
            resp_nonce = nacl.utils.random(24)
            resp_encrypted = self.session_box.encrypt(json.dumps(resp_payload).encode("utf-8"), resp_nonce)
            self._queue_server_message({
                "action": inner_action,
                "message": base64.b64encode(resp_encrypted.ciphertext).decode("utf-8"),
                "nonce": base64.b64encode(resp_nonce).decode("utf-8")
            })


def test_sqlite_association_persistence(tmp_path: Path):
    """Valida a persistência e recuperação das chaves de associação no SQLite Central."""
    db_file = tmp_path / "test_central.db"
    client = KeePassXCClient(db_path=db_file)

    # Verifica se a tabela foi criada
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plugin_safe_keepassxc_association'")
        assert cursor.fetchone() is not None

    # Simula gravação de associação
    priv = PrivateKey.generate()
    pub = priv.public_key
    serv_pub = PrivateKey.generate().public_key
    client._save_association("client-abc", priv, pub, serv_pub)

    # Cria nova instância apontando para o mesmo banco e verifica recuperação
    client2 = KeePassXCClient(db_path=db_file)
    assert client2._associated_id == "client-abc"
    assert client2._client_public_key == pub
    assert client2._server_public_key == serv_pub


def test_keepassxc_not_running_error(tmp_path: Path):
    """Valida exceção clara quando o KeePassXC não está aberto ou pipes não existem."""
    db_file = tmp_path / "test_central.db"
    client = KeePassXCClient(db_path=db_file)

    with patch("builtins.open", side_effect=OSError("Pipe not found")), \
         patch("os.path.exists", return_value=False):
        with pytest.raises(KeePassXCNotRunningError):
            client.connect()

    assert not client.is_connected()


def test_full_handshake_and_encrypted_operations(tmp_path: Path):
    """Valida handshake inicial, associação, consultas de login, TOTP e geração de senha com mock."""
    db_file = tmp_path / "test_central.db"
    client = KeePassXCClient(db_path=db_file)
    mock_transport = MockPipeTransport()

    with patch("builtins.open", return_value=mock_transport):
        # 1. Conexão & Handshake
        assert client.connect() is True
        assert client.is_connected() is True

        # 2. Associação
        assoc_res = client.associate("Toolbox Test")
        assert assoc_res["success"] is True
        assert assoc_res["id"] == "test-toolbox-client-id-123"

        # 3. Teste de Associação
        assert client.test_associate() is True

        # 4. Busca de Logins
        logins = client.get_logins(url="https://aws.amazon.com")
        assert len(logins) == 1
        assert logins[0]["login"] == "admin_master"
        assert logins[0]["password"] == "SuperSecretPassword123!"

        # 5. Busca de TOTP
        totp = client.get_totp("1111-2222-3333-4444")
        assert totp == "852963"

        # 6. Geração de Senha
        gen_pass = client.generate_password()
        assert gen_pass == "G3n3r4t3d-P@ssw0rd!"

        # 7. Bloqueio de Cofre
        assert client.lock_database() is True

        # 8. Desconexão
        client.disconnect()
        assert not client.is_connected()


def test_get_database_status(tmp_path: Path):
    """Valida o relatório de status retornado pelo cliente."""
    db_file = tmp_path / "test_central.db"
    client = KeePassXCClient(db_path=db_file)
    mock_transport = MockPipeTransport()

    with patch("builtins.open", return_value=mock_transport):
        client.connect()
        client._associated_id = "mock-id"
        client._client_public_key = PrivateKey.generate().public_key

        status = client.get_database_status()
        assert status["available"] is True
        assert status["connected"] is True
        assert status["unlocked"] is True
