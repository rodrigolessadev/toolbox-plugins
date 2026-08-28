"""
Serviço Principal do Cofre Seguro (SafeService / ISafeService).

Coordena criptografia, autenticação Windows Hello / Senha Mestra,
auto-lock por inatividade e controle de acesso (ACL) para outros plugins.
"""

from __future__ import annotations

import os
import secrets
import string
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import crypto
    import db
    import windows_hello
except ImportError:
    try:
        from . import crypto
        from . import db
        from . import windows_hello
    except ImportError:
        from safe import crypto
        from safe import db
        from safe import windows_hello


class SafeAccessDeniedError(Exception):
    """Acesso negado por falta de permissão ou cofre bloqueado."""
    pass


class SafeVaultLockedError(Exception):
    """Operação requer que o cofre esteja desbloqueado."""
    pass


class SafeService:
    """
    Serviço central do Cofre Seguro com gerenciamento de chave mestra em memória.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db = db.SafeDatabase(db_path)
        self._master_key: Optional[bytearray] = None
        self._last_activity_time: float = time.time()

    # ========================================================================
    # Ciclo de Vida & Status
    # ========================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual do cofre.
        """
        meta = self.db.get_metadata()
        if not meta:
            return {
                "configured": False,
                "status": "UNCONFIGURED",
                "auth_mode": None,
                "entries_count": 0,
                "auto_lock_timeout": 300,
                "auto_lock_remaining": 0,
                "windows_hello_available": windows_hello.is_windows_hello_available(),
            }

        self.check_auto_lock()
        is_unlocked = self._master_key is not None
        timeout = meta.get("auto_lock_timeout", 300)
        
        remaining = 0
        if is_unlocked and timeout > 0:
            elapsed = time.time() - self._last_activity_time
            remaining = max(0, int(timeout - elapsed))

        return {
            "configured": True,
            "status": "UNLOCKED" if is_unlocked else "LOCKED",
            "auth_mode": meta.get("auth_mode", "master_password"),
            "entries_count": self.db.count_entries(),
            "auto_lock_timeout": timeout,
            "auto_lock_remaining": remaining,
            "windows_hello_available": windows_hello.is_windows_hello_available(),
        }

    def touch_activity(self) -> None:
        """Atualiza o timestamp de atividade recente para o auto-lock."""
        self._last_activity_time = time.time()

    def check_auto_lock(self) -> bool:
        """
        Verifica se o tempo limite de inatividade foi atingido e bloqueia automaticamente.
        """
        if self._master_key is None:
            return False

        meta = self.db.get_metadata()
        if not meta:
            return False

        timeout = meta.get("auto_lock_timeout", 300)
        if timeout <= 0:
            return False  # Auto-lock desabilitado

        elapsed = time.time() - self._last_activity_time
        if elapsed >= timeout:
            self.lock()
            return True
        return False

    def setup_vault(
        self,
        auth_mode: str = "master_password",
        password: Optional[str] = None,
        use_hello: bool = False,
        auto_lock_timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Inicializa o cofre gerando a Master Key e persistindo metadados de KDF/DPAPI.
        """
        auth_mode_clean = auth_mode.lower()
        mk_raw = crypto.generate_master_key()

        kdf_salt = None
        kdf_algorithm = "argon2id"
        kdf_params: Dict[str, Any] = {}
        wrapped_mk = None
        hello_cred_id = None

        if auth_mode_clean in ("master_password", "hybrid"):
            if not password or len(password.strip()) < 4:
                raise ValueError("A senha mestre deve ter pelo menos 4 caracteres.")
            
            kdf_salt = crypto.generate_salt(16)
            kdf_params = {"iterations": 3, "memory_cost": 65536, "parallelism": 4}
            wrapping_key = crypto.derive_key(password, kdf_salt, kdf_algorithm, kdf_params)
            
            # Criptografa a MK com a chave derivada da senha
            ciphertext, iv, auth_tag = crypto.wrap_key(mk_raw, wrapping_key)
            wrapped_mk = iv + auth_tag + ciphertext  # 12b IV + 16b Tag + 32b Ciphertext

        if auth_mode_clean in ("windows_hello", "hybrid"):
            hello_cred_id = str(uuid.uuid4())
            if not wrapped_mk:
                # No modo puro Windows Hello, protege a MK diretamente via DPAPI de hardware/perfil
                dpapi_blob = windows_hello.protect_data_dpapi(mk_raw, entropy=hello_cred_id.encode("utf-8"))
                wrapped_mk = dpapi_blob

        self.db.save_metadata(
            auth_mode=auth_mode_clean,
            kdf_salt=kdf_salt,
            kdf_algorithm=kdf_algorithm,
            kdf_params=kdf_params,
            wrapped_master_key=wrapped_mk,
            hello_credential_id=hello_cred_id,
            auto_lock_timeout=auto_lock_timeout,
        )

        # Guarda a chave ativa em memória protegida (bytearray)
        self._master_key = bytearray(mk_raw)
        self.touch_activity()

        return {"success": True, "message": "Cofre configurado e desbloqueado com sucesso."}

    def unlock(
        self,
        password: Optional[str] = None,
        use_hello: bool = False,
        reason: str = "Acesso ao Cofre Seguro",
    ) -> bool:
        """
        Desbloqueia o cofre via Windows Hello ou Senha Mestra.
        """
        meta = self.db.get_metadata()
        if not meta:
            raise ValueError("O cofre ainda não foi configurado. Execute a configuração inicial.")

        auth_mode = meta.get("auth_mode", "master_password")
        wrapped_mk = meta.get("wrapped_master_key")

        if not wrapped_mk:
            raise ValueError("Chave mestra não encontrada nos metadados do cofre.")

        mk_bytes: Optional[bytes] = None

        if use_hello and auth_mode in ("windows_hello", "hybrid"):
            # Solicita confirmação biométrica/PIN
            ok, msg = windows_hello.verify_windows_hello(reason)
            if not ok:
                raise SafeAccessDeniedError(f"Windows Hello recusado: {msg}")

            hello_id = (meta.get("hello_credential_id") or "").encode("utf-8")
            try:
                mk_bytes = windows_hello.unprotect_data_dpapi(wrapped_mk, entropy=hello_id if hello_id else None)
            except Exception:
                # Se falhar pelo DPAPI e for híbrido, tenta senha mestre se informada
                if auth_mode != "hybrid" or not password:
                    raise SafeAccessDeniedError("Não foi possível desencapsular a chave com Windows Hello.")

        if mk_bytes is None:
            if not password:
                raise ValueError("Senha mestre necessária para desbloquear.")

            salt = meta.get("kdf_salt")
            algorithm = meta.get("kdf_algorithm", "argon2id")
            params = meta.get("kdf_params") or {}
            
            if not salt:
                raise ValueError("Salt de derivação não encontrado.")

            wrapping_key = crypto.derive_key(password, salt, algorithm, params)
            
            # Formato: 12b IV + 16b Tag + Ciphertext
            if len(wrapped_mk) < 28:
                raise ValueError("Blob de chave mestra corrompido.")

            iv = wrapped_mk[:12]
            auth_tag = wrapped_mk[12:28]
            ciphertext = wrapped_mk[28:]

            try:
                mk_bytes = crypto.unwrap_key(ciphertext, iv, auth_tag, wrapping_key)
            except Exception as e:
                raise SafeAccessDeniedError("Senha mestre incorreta ou dados corrompidos.") from e

        if not mk_bytes or len(mk_bytes) != 32:
            raise SafeAccessDeniedError("Chave mestra inválida.")

        self._master_key = bytearray(mk_bytes)
        self.touch_activity()
        return True

    def lock(self) -> bool:
        """
        Bloqueia o cofre imediatamente e limpa a chave da memória RAM (Zeroization).
        """
        if self._master_key is not None:
            crypto.zeroize(self._master_key)
            self._master_key = None
        return True

    def _require_unlocked(self) -> bytes:
        """Valida que o cofre está desbloqueado e retorna a Master Key ativa."""
        self.check_auto_lock()
        if self._master_key is None:
            raise SafeVaultLockedError("O cofre está bloqueado. Desbloqueie para continuar.")
        self.touch_activity()
        return bytes(self._master_key)

    # ========================================================================
    # Gerenciamento de Segredos (CRUD)
    # ========================================================================

    def save_secret(
        self,
        title: str,
        secret_payload: Union[Dict[str, Any], str],
        category: str = "general",
        username_or_key: Optional[str] = None,
        entry_id: Optional[str] = None,
        owner_plugin_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Criptografa e armazena ou atualiza uma credencial no banco.
        """
        mk = self._require_unlocked()
        eid = entry_id or str(uuid.uuid4())

        ciphertext, iv, auth_tag = crypto.encrypt_payload(secret_payload, mk)

        existing = self.db.get_entry(eid)
        if existing:
            self.db.update_entry(
                entry_id=eid,
                title=title,
                category=category,
                username_or_key=username_or_key,
                encrypted_payload=ciphertext,
                iv=iv,
                auth_tag=auth_tag,
                tags=tags,
                metadata=metadata,
            )
        else:
            self.db.insert_entry(
                entry_id=eid,
                title=title,
                category=category,
                owner_plugin_id=owner_plugin_id,
                username_or_key=username_or_key,
                encrypted_payload=ciphertext,
                iv=iv,
                auth_tag=auth_tag,
                tags=tags,
                metadata=metadata,
            )

        return {
            "id": eid,
            "title": title,
            "category": category,
            "username_or_key": username_or_key,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_secret(
        self,
        entry_id: str,
        requester_plugin_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recupera e decriptografa um segredo com validação de ACL.
        """
        mk = self._require_unlocked()
        entry = self.db.get_entry(entry_id)
        if not entry:
            raise ValueError(f"Credencial com ID '{entry_id}' não encontrada.")

        # Validação de ACL se for requisitado por um plugin terceiro
        if requester_plugin_id:
            owner = entry.get("owner_plugin_id")
            if owner != requester_plugin_id:
                grant = self.db.get_grant(requester_plugin_id, entry_id)
                if not grant:
                    raise SafeAccessDeniedError(
                        f"Plugin '{requester_plugin_id}' não possui permissão para acessar a credencial '{entry.get('title')}'."
                    )

        ciphertext = entry["encrypted_payload"]
        iv = entry["iv"]
        auth_tag = entry["auth_tag"]

        decrypted = crypto.decrypt_payload(ciphertext, iv, auth_tag, mk)

        return {
            "id": entry["id"],
            "title": entry["title"],
            "category": entry["category"],
            "owner_plugin_id": entry["owner_plugin_id"],
            "username_or_key": entry["username_or_key"],
            "tags": entry.get("tags") or [],
            "metadata": entry.get("metadata") or {},
            "payload": decrypted,
            "created_at": entry["created_at"],
            "updated_at": entry["updated_at"],
        }

    def list_secrets(
        self,
        category: Optional[str] = None,
        requester_plugin_id: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lista resumo de credenciais autorizadas (sem expor payloads).
        """
        self._require_unlocked()
        return self.db.list_entries_summary(
            category=category,
            owner_plugin_id=requester_plugin_id,
            search_query=search_query,
        )

    def delete_secret(
        self,
        entry_id: str,
        requester_plugin_id: Optional[str] = None,
    ) -> bool:
        """
        Exclui uma credencial e suas permissões associadas.
        """
        self._require_unlocked()
        entry = self.db.get_entry(entry_id)
        if not entry:
            return False

        if requester_plugin_id:
            owner = entry.get("owner_plugin_id")
            if owner != requester_plugin_id:
                grant = self.db.get_grant(requester_plugin_id, entry_id)
                if not grant or grant.get("access_level") not in ("read_write", "full"):
                    raise SafeAccessDeniedError(f"Permissão insuficiente para excluir a credencial '{entry.get('title')}'.")

        return self.db.delete_entry(entry_id)

    # ========================================================================
    # Permissões e ACLs de Plugins
    # ========================================================================

    def grant_permission(
        self,
        target_plugin_id: str,
        entry_id: str,
        access_level: str = "read",
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_unlocked()
        grant_id = f"{target_plugin_id}_{entry_id}"
        self.db.add_grant(grant_id, target_plugin_id, entry_id, access_level, expires_at)
        return {"success": True, "grant_id": grant_id}

    def revoke_permission(self, grant_id: str) -> bool:
        self._require_unlocked()
        return self.db.delete_grant(grant_id)

    def list_grants(self, plugin_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_unlocked()
        return self.db.list_grants(plugin_id)

    # ========================================================================
    # Utilitários de Segurança
    # ========================================================================

    def generate_secure_password(
        self,
        length: int = 16,
        use_upper: bool = True,
        use_lower: bool = True,
        use_digits: bool = True,
        use_symbols: bool = True,
    ) -> str:
        """
        Gera uma senha forte com alta entropia.
        """
        chars = ""
        required: List[str] = []

        if use_upper:
            chars += string.ascii_uppercase
            required.append(secrets.choice(string.ascii_uppercase))
        if use_lower:
            chars += string.ascii_lowercase
            required.append(secrets.choice(string.ascii_lowercase))
        if use_digits:
            chars += string.digits
            required.append(secrets.choice(string.digits))
        if use_symbols:
            symbols = "!@#$%^&*()-_=+[]{}<>?~"
            chars += symbols
            required.append(secrets.choice(symbols))

        if not chars:
            chars = string.ascii_letters + string.digits

        length = max(length, len(required))
        remaining = [secrets.choice(chars) for _ in range(length - len(required))]
        all_chars = required + remaining
        secrets.SystemRandom().shuffle(all_chars)
        return "".join(all_chars)

    def update_settings(self, auto_lock_timeout: int) -> None:
        """Atualiza configurações de timeout do auto-lock."""
        self._require_unlocked()
        self.db.update_auto_lock_timeout(auto_lock_timeout)
