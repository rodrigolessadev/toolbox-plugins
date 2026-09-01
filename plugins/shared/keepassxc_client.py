"""
Módulo Cliente IPC para integração com KeePassXC Desktop (Native Messaging Protocol).
Permite consulta segura de credenciais, senhas e TOTP com criptografia ponta a ponta (Curve25519/NaCl).
Persiste chaves de associação no SQLite Central do Toolbox conforme Abordagem B.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import struct
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("toolbox.keepassxc")

# Tenta importar PyNaCl; se não estiver instalado, avisa mas não quebra importação básica
try:
    import nacl.bindings
    import nacl.public
    import nacl.utils
    from nacl.public import Box, PrivateKey, PublicKey
    HAS_NACL = True
except ImportError:
    HAS_NACL = False
    logger.warning("PyNaCl não encontrado. Para utilizar a integração com o KeePassXC, instale pynacl>=1.5.0.")

from .db_utils import get_central_db_path


class KeePassXCError(Exception):
    """Exceção base para erros de comunicação com KeePassXC."""
    pass


class KeePassXCNotRunningError(KeePassXCError):
    """Lançada quando o KeePassXC não está em execução ou o pipe não foi encontrado."""
    pass


class KeePassXCLockedError(KeePassXCError):
    """Lançada quando o cofre do KeePassXC está bloqueado."""
    pass


class KeePassXCAssociationError(KeePassXCError):
    """Lançada quando a associação é rejeitada ou inválida."""
    pass


class KeePassXCClient:
    """Cliente IPC para comunicação com KeePassXC via Native Messaging (Named Pipe / Unix Socket)."""

    DEFAULT_CLIENT_NAME = "Toolbox"

    def __init__(self, db_path: Optional[Path] = None, client_id: Optional[str] = None):
        self.db_path = db_path or get_central_db_path()
        self._pipe_handle = None
        self._socket = None
        self._connected = False
        self._client_private_key: Optional[PrivateKey] = None
        self._client_public_key: Optional[PublicKey] = None
        self._server_public_key: Optional[PublicKey] = None
        self._session_box: Optional[Box] = None
        self._associated_id: Optional[str] = client_id
        self._nonce_counter = 0

        self._init_db_schema()
        self._load_saved_association()

    # -------------------------------------------------------------------------
    # Persistência no SQLite Central (Abordagem B)
    # -------------------------------------------------------------------------
    def _init_db_schema(self) -> None:
        """Inicializa a tabela de associação no banco SQLite Central."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS plugin_safe_keepassxc_association (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id TEXT NOT NULL UNIQUE,
                        client_public_key TEXT NOT NULL,
                        client_private_key TEXT NOT NULL,
                        server_public_key TEXT NOT NULL,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now'))
                    );
                """)
                conn.commit()
        except Exception as exc:
            logger.error(f"Erro ao inicializar schema de associação KeePassXC no SQLite: {exc}")

    def _load_saved_association(self) -> bool:
        """Carrega chaves e ID de associação salvos anteriormente no SQLite Central."""
        if not HAS_NACL:
            return False
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT client_id, client_public_key, client_private_key, server_public_key
                    FROM plugin_safe_keepassxc_association
                    ORDER BY id DESC LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    self._associated_id = row[0]
                    client_pub_bytes = base64.b64decode(row[1])
                    client_priv_bytes = base64.b64decode(row[2])
                    server_pub_bytes = base64.b64decode(row[3])

                    self._client_private_key = PrivateKey(client_priv_bytes)
                    self._client_public_key = PublicKey(client_pub_bytes)
                    self._server_public_key = PublicKey(server_pub_bytes)
                    return True
        except Exception as exc:
            logger.warning(f"Não foi possível carregar associação salva do KeePassXC: {exc}")
        return False

    def _save_association(self, client_id: str, client_priv: PrivateKey, client_pub: PublicKey, server_pub: PublicKey) -> None:
        """Salva as chaves e o ID de associação no SQLite Central."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                client_pub_b64 = base64.b64encode(bytes(client_pub)).decode("utf-8")
                client_priv_b64 = base64.b64encode(bytes(client_priv)).decode("utf-8")
                server_pub_b64 = base64.b64encode(bytes(server_pub)).decode("utf-8")

                conn.execute("""
                    INSERT INTO plugin_safe_keepassxc_association
                    (client_id, client_public_key, client_private_key, server_public_key, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(client_id) DO UPDATE SET
                        client_public_key = excluded.client_public_key,
                        client_private_key = excluded.client_private_key,
                        server_public_key = excluded.server_public_key,
                        updated_at = datetime('now');
                """, (client_id, client_pub_b64, client_priv_b64, server_pub_b64))
                conn.commit()
                self._associated_id = client_id
                self._client_private_key = client_priv
                self._client_public_key = client_pub
                self._server_public_key = server_pub
        except Exception as exc:
            logger.error(f"Erro ao salvar associação do KeePassXC no SQLite Central: {exc}")

    # -------------------------------------------------------------------------
    # Conexão e Transporte (Named Pipes / Sockets)
    # -------------------------------------------------------------------------
    def _get_candidate_pipe_names(self) -> List[str]:
        """Retorna lista de nomes de pipes candidatos para o KeePassXC no Windows."""
        pipes = []
        custom_socket = os.environ.get("KEEPASSXC_BROWSER_SOCKET")
        if custom_socket:
            pipes.append(rf"\\.\pipe\{custom_socket}" if not custom_socket.startswith(r"\\.\pipe\\") else custom_socket)

        user = ""
        try:
            user = os.getlogin()
        except Exception:
            pass

        if user:
            pipes.append(rf"\\.\pipe\org.keepassxc.KeePassXC.BrowserServer_{user}")
            pipes.append(rf"\\.\pipe\kpxc_server_{user}")

        pipes.append(r"\\.\pipe\org.keepassxc.KeePassXC.BrowserServer")
        pipes.append(r"\\.\pipe\kpxc_server")
        return pipes

    def connect(self) -> bool:
        """Estabelece conexão com o processo KeePassXC e realiza a troca inicial de chaves."""
        if not HAS_NACL:
            raise KeePassXCError("PyNaCl não está instalado. Instale 'pynacl>=1.5.0' para conectar ao KeePassXC.")

        self.disconnect()

        if sys.platform == "win32":
            candidate_pipes = self._get_candidate_pipe_names()
            for pipe_path in candidate_pipes:
                try:
                    # Abre o named pipe em modo binário sem buffer
                    self._pipe_handle = open(pipe_path, "r+b", buffering=0)
                    self._connected = True
                    break
                except (OSError, IOError):
                    continue
        else:
            import socket
            sock_paths = [
                os.environ.get("KEEPASSXC_BROWSER_SOCKET"),
                os.path.expanduser("~/.var/app/org.keepassxc.KeePassXC/data/kpxc_server"),
                os.path.expanduser("~/snap/keepassxc/common/kpxc_server"),
                os.path.expanduser(f"/tmp/kpxc_server_{os.getlogin()}"),
                "/tmp/kpxc_server"
            ]
            for sock_path in sock_paths:
                if sock_path and os.path.exists(sock_path):
                    try:
                        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        s.connect(sock_path)
                        self._socket = s
                        self._connected = True
                        break
                    except (socket.error, OSError):
                        continue

        if not self._connected:
            raise KeePassXCNotRunningError("KeePassXC não está em execução ou a opção 'Integração com o navegador' não está habilitada.")

        # Realiza troca inicial de chaves públicas
        return self._exchange_public_keys()

    def disconnect(self) -> None:
        """Fecha a conexão atual com o KeePassXC."""
        if self._pipe_handle:
            try:
                self._pipe_handle.close()
            except Exception:
                pass
            self._pipe_handle = None
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self._connected = False
        self._session_box = None

    def is_connected(self) -> bool:
        """Verifica se há conexão ativa com o KeePassXC."""
        return self._connected and (self._pipe_handle is not None or self._socket is not None)

    # -------------------------------------------------------------------------
    # Envio / Recepção de Pacotes Native Messaging
    # -------------------------------------------------------------------------
    def _read_bytes(self, n: int) -> bytes:
        """Lê exatamente n bytes do pipe/socket."""
        buf = bytearray()
        while len(buf) < n:
            if self._pipe_handle:
                chunk = self._pipe_handle.read(n - len(buf))
            elif self._socket:
                chunk = self._socket.recv(n - len(buf))
            else:
                raise KeePassXCError("Conexão fechada.")
            if not chunk:
                raise KeePassXCError("Fim de fluxo inesperado ao ler do KeePassXC.")
            buf.extend(chunk)
        return bytes(buf)

    def _send_raw_message(self, data: Dict[str, Any]) -> None:
        """Envia uma mensagem JSON com cabeçalho de comprimento little-endian (4 bytes)."""
        raw_json = json.dumps(data).encode("utf-8")
        header = struct.pack("<I", len(raw_json))
        if self._pipe_handle:
            self._pipe_handle.write(header + raw_json)
            self._pipe_handle.flush()
        elif self._socket:
            self._socket.sendall(header + raw_json)
        else:
            raise KeePassXCError("Nenhum transporte conectado.")

    def _receive_raw_message(self) -> Dict[str, Any]:
        """Recebe uma mensagem JSON com cabeçalho de comprimento little-endian."""
        header = self._read_bytes(4)
        length = struct.unpack("<I", header)[0]
        payload = self._read_bytes(length)
        return json.loads(payload.decode("utf-8"))

    # -------------------------------------------------------------------------
    # Criptografia & Handshake
    # -------------------------------------------------------------------------
    def _next_nonce(self) -> bytes:
        """Gera um nonce aleatório de 24 bytes para a próxima mensagem criptografada."""
        return nacl.utils.random(24)

    def _exchange_public_keys(self) -> bool:
        """Executa a ação 'change-public-keys' para estabelecer a chave de sessão Diffie-Hellman."""
        if not self._client_private_key:
            self._client_private_key = PrivateKey.generate()
            self._client_public_key = self._client_private_key.public_key

        nonce = self._next_nonce()
        req = {
            "action": "change-public-keys",
            "publicKey": base64.b64encode(bytes(self._client_public_key)).decode("utf-8"),
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "clientID": self._associated_id or ""
        }

        self._send_raw_message(req)
        res = self._receive_raw_message()

        if res.get("success") == "true" and "publicKey" in res:
            server_pub_bytes = base64.b64decode(res["publicKey"])
            self._server_public_key = PublicKey(server_pub_bytes)
            self._session_box = Box(self._client_private_key, self._server_public_key)
            return True
        else:
            self.disconnect()
            raise KeePassXCError(f"Falha na troca de chaves públicas: {res.get('message', 'Resposta desconhecida')}")

    def _send_encrypted_request(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Criptografa e envia uma requisição para o KeePassXC, descriptografando a resposta."""
        if not self.is_connected() or not self._session_box:
            self.connect()

        payload = {"action": action}
        if params:
            payload.update(params)

        nonce = self._next_nonce()
        plaintext = json.dumps(payload).encode("utf-8")
        encrypted = self._session_box.encrypt(plaintext, nonce)
        # O encrypted contém nonce (24 bytes) + ciphertext. Separamos para o protocolo:
        ciphertext = encrypted.ciphertext

        envelope = {
            "action": action,
            "message": base64.b64encode(ciphertext).decode("utf-8"),
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "clientID": self._associated_id or ""
        }

        self._send_raw_message(envelope)
        raw_res = self._receive_raw_message()

        if raw_res.get("success") == "false" and "error" in raw_res:
            err_msg = raw_res.get("message") or raw_res.get("error") or "Erro retornado pelo KeePassXC."
            if "database not opened" in err_msg.lower() or "locked" in err_msg.lower():
                raise KeePassXCLockedError(f"Cofre do KeePassXC está bloqueado ou fechado: {err_msg}")
            raise KeePassXCError(err_msg)

        if "message" in raw_res and "nonce" in raw_res:
            res_nonce = base64.b64decode(raw_res["nonce"])
            res_ciphertext = base64.b64decode(raw_res["message"])
            decrypted = self._session_box.decrypt(res_ciphertext, res_nonce)
            return json.loads(decrypted.decode("utf-8"))

        return raw_res

    # -------------------------------------------------------------------------
    # Operações da API do KeePassXC
    # -------------------------------------------------------------------------
    def associate(self, client_name: str = DEFAULT_CLIENT_NAME) -> Dict[str, Any]:
        """
        Dispara o popup nativo de associação no KeePassXC.
        Se aprovado pelo usuário, salva a associação no SQLite Central.
        """
        if not self.is_connected():
            self.connect()

        # Gera novo par de chaves para a associação permanente
        self._client_private_key = PrivateKey.generate()
        self._client_public_key = self._client_private_key.public_key
        self._exchange_public_keys()

        client_pub_b64 = base64.b64encode(bytes(self._client_public_key)).decode("utf-8")
        res = self._send_encrypted_request("associate", {
            "key": client_pub_b64,
            "id": client_pub_b64
        })

        if res.get("success") == "true" and "id" in res:
            associated_id = res["id"]
            self._save_association(associated_id, self._client_private_key, self._client_public_key, self._server_public_key)
            return {
                "success": True,
                "id": associated_id,
                "message": f"Associação com KeePassXC realizada com sucesso como '{client_name}'!"
            }
        else:
            raise KeePassXCAssociationError(res.get("message", "Associação recusada no KeePassXC."))

    def test_associate(self) -> bool:
        """Verifica se a associação atual continua autorizada no KeePassXC."""
        if not self._associated_id or not self._client_public_key:
            return False
        try:
            client_pub_b64 = base64.b64encode(bytes(self._client_public_key)).decode("utf-8")
            res = self._send_encrypted_request("test-associate", {
                "id": self._associated_id,
                "key": client_pub_b64
            })
            return res.get("success") == "true"
        except Exception:
            return False

    def get_logins(self, url: str = "", submit_url: str = "", keys: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
        """
        Consulta credenciais correspondentes à URL/host especificado.
        Retorna lista de dicionários contendo login, senha, uuid e nome da entrada.
        """
        if not self._associated_id or not self._client_public_key:
            raise KeePassXCAssociationError("Toolbox não está associado ao KeePassXC. Execute associate() primeiro.")

        client_pub_b64 = base64.b64encode(bytes(self._client_public_key)).decode("utf-8")
        key_list = keys or [{"id": self._associated_id, "key": client_pub_b64}]

        params = {
            "url": url or "http://localhost",
            "submitUrl": submit_url or url or "http://localhost",
            "keys": key_list
        }

        res = self._send_encrypted_request("get-logins", params)
        if res.get("success") == "true":
            return res.get("entries", [])
        elif res.get("error") == "Database not opened":
            raise KeePassXCLockedError("O cofre do KeePassXC está fechado ou bloqueado.")
        else:
            return []

    def get_totp(self, entry_uuid: str) -> Optional[str]:
        """Obtém o token TOTP atual de uma entrada a partir do seu UUID."""
        if not entry_uuid:
            return None
        res = self._send_encrypted_request("get-totp", {"uuid": entry_uuid})
        if res.get("success") == "true":
            return res.get("totp")
        return None

    def generate_password(self) -> Optional[str]:
        """Gera uma senha forte utilizando as configurações do gerador de senhas do KeePassXC."""
        res = self._send_encrypted_request("generate-password")
        if res.get("success") == "true":
            return res.get("password")
        return None

    def lock_database(self) -> bool:
        """Solicita o bloqueio do cofre ativo no KeePassXC."""
        try:
            res = self._send_encrypted_request("lock-database")
            return res.get("success") == "true"
        except Exception:
            return False

    def get_database_status(self) -> Dict[str, Any]:
        """Retorna o estado da conexão e do cofre (conectado, associado, bloqueado ou aberto)."""
        if not HAS_NACL:
            return {"available": False, "error": "PyNaCl não instalado."}

        try:
            if not self.is_connected():
                self.connect()
            associated = self.test_associate()
            return {
                "available": True,
                "connected": True,
                "associated": associated,
                "client_id": self._associated_id,
                "unlocked": True
            }
        except KeePassXCLockedError:
            return {
                "available": True,
                "connected": True,
                "associated": bool(self._associated_id),
                "client_id": self._associated_id,
                "unlocked": False,
                "error": "Cofre bloqueado."
            }
        except KeePassXCNotRunningError:
            return {
                "available": True,
                "connected": False,
                "associated": bool(self._associated_id),
                "unlocked": False,
                "error": "KeePassXC fechado ou integração desabilitada."
            }
        except Exception as exc:
            return {
                "available": True,
                "connected": False,
                "associated": False,
                "unlocked": False,
                "error": str(exc)
            }
