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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import crypto
    import db
    import windows_hello
    import windows_session
    import importers
    import logger as safe_logger_module
except ImportError:
    try:
        from . import crypto
        from . import db
        from . import windows_hello
        from . import windows_session
        from . import importers
        from . import logger as safe_logger_module
    except ImportError:
        from safe import crypto
        from safe import db
        from safe import windows_hello
        from safe import logger as safe_logger_module
        try:
            from safe import windows_session
        except ImportError:
            windows_session = None
        try:
            from safe import importers
        except ImportError:
            importers = None

logger = safe_logger_module.get_logger("safe.service")


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
        self._on_lock_listeners: List[Callable[[str], None]] = []
        logger.info("SafeService inicializado.")
        
        # Inicializa o listener de bloqueio de sessão do Windows
        if windows_session and hasattr(windows_session, "start_session_lock_listener"):
            try:
                windows_session.start_session_lock_listener(self._handle_os_session_lock)
            except Exception as e:
                logger.debug(f"Aviso ao iniciar session_lock_listener: {e}")

    def add_on_lock_listener(self, listener: Callable[[str], None]) -> None:
        """Registra um callback a ser acionado sempre que o cofre for bloqueado."""
        if listener not in self._on_lock_listeners:
            self._on_lock_listeners.append(listener)

    def _handle_os_session_lock(self) -> None:
        """Callback acionado quando o Windows é bloqueado (Win + L / Suspensão)."""
        meta = self.db.get_metadata()
        if meta and meta.get("lock_on_os_lock", True):
            logger.info("Bloqueio de sessão do Windows detectado (Win+L). Bloqueando cofre.")
            self.lock(reason="Bloqueio de Sessão do Windows")

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
                "lock_on_os_lock": True,
                "needs_password_migration": False,
                "windows_hello_available": windows_hello.is_windows_hello_available(),
            }

        self.check_auto_lock()
        is_unlocked = self._master_key is not None
        timeout = meta.get("auto_lock_timeout", 300)
        lock_on_os = meta.get("lock_on_os_lock", True)
        auth_mode = meta.get("auth_mode", "master_password")
        has_salt = bool(meta.get("kdf_salt"))
        
        remaining = 0
        if is_unlocked and timeout > 0:
            elapsed = time.time() - self._last_activity_time
            remaining = max(0, int(timeout - elapsed))

        return {
            "configured": True,
            "status": "UNLOCKED" if is_unlocked else "LOCKED",
            "auth_mode": auth_mode,
            "entries_count": self.db.count_entries(),
            "auto_lock_timeout": timeout,
            "auto_lock_remaining": remaining,
            "lock_on_os_lock": lock_on_os,
            "needs_password_migration": (auth_mode == "windows_hello" and not has_salt),
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
            logger.info("Tempo limite de inatividade atingido. Bloqueando o cofre automaticamente.")
            self.lock(reason="Inatividade")
            return True
        return False

    def setup_vault(
        self,
        auth_mode: str = "hybrid",
        password: Optional[str] = None,
        use_hello: bool = False,
        auto_lock_timeout: int = 300,
        lock_on_os_lock: bool = True,
    ) -> Dict[str, Any]:
        """
        Inicializa o cofre gerando a Master Key e persistindo metadados de KDF e proteção.
        A criação de senha mestra é obrigatória para todos os modos.
        """
        if not password or len(password.strip()) < 4:
            logger.warning("Tentativa de setup do cofre rejeitada: senha mestre inválida ou curta.")
            raise ValueError("A senha mestre é obrigatória e deve ter pelo menos 4 caracteres.")

        auth_mode_clean = "hybrid" if use_hello or auth_mode.lower() == "hybrid" else "master_password"
        logger.info(f"Iniciando configuração inicial do cofre (modo: {auth_mode_clean}, timeout: {auto_lock_timeout}s, lock_on_os: {lock_on_os_lock}).")
        mk_raw = crypto.generate_master_key()

        kdf_salt = crypto.generate_salt(16)
        kdf_algorithm = "argon2id"
        kdf_params = {"iterations": 3, "memory_cost": 65536, "parallelism": 4}
        wrapping_key = crypto.derive_key(password, kdf_salt, kdf_algorithm, kdf_params)
        
        # Criptografa a MK com a chave derivada da senha
        ciphertext, iv, auth_tag = crypto.wrap_key(mk_raw, wrapping_key)
        wrapped_mk = iv + auth_tag + ciphertext  # 12b IV + 16b Tag + 32b Ciphertext

        hello_cred_id = None
        wrapped_hello = None
        if auth_mode_clean == "hybrid":
            hello_cred_id = str(uuid.uuid4())
            try:
                wrapped_hello = windows_hello.protect_data_dpapi(mk_raw, entropy=hello_cred_id.encode("utf-8"))
            except Exception as e:
                logger.debug(f"Proteção DPAPI para Windows Hello indisponível no setup: {e}")
                wrapped_hello = None

        self.db.save_metadata(
            auth_mode=auth_mode_clean,
            kdf_salt=kdf_salt,
            kdf_algorithm=kdf_algorithm,
            kdf_params=kdf_params,
            wrapped_master_key=wrapped_mk,
            wrapped_hello_key=wrapped_hello,
            hello_credential_id=hello_cred_id,
            auto_lock_timeout=auto_lock_timeout,
            lock_on_os_lock=lock_on_os_lock,
        )

        # Guarda a chave ativa em memória protegida (bytearray)
        self._master_key = bytearray(mk_raw)
        self.touch_activity()
        logger.info("Cofre configurado e desbloqueado com sucesso.")

        return {"success": True, "message": "Cofre configurado e desbloqueado com sucesso."}

    def set_master_password(self, password: str) -> Dict[str, Any]:
        """
        Define ou altera a Senha Mestra do cofre (para migração de contas ou alteração de senha).
        Exige que o cofre esteja desbloqueado. Mantém o envelope do Windows Hello sincronizado.
        """
        self._require_unlocked()
        if not password or len(password.strip()) < 4:
            logger.warning("Tentativa de alteração de senha mestre rejeitada: senha curta.")
            raise ValueError("A senha mestre deve ter pelo menos 4 caracteres.")

        meta = self.db.get_metadata()
        if not meta:
            raise ValueError("Cofre não configurado.")

        mk_raw = bytes(self._master_key)
        kdf_salt = crypto.generate_salt(16)
        kdf_algorithm = "argon2id"
        kdf_params = {"iterations": 3, "memory_cost": 65536, "parallelism": 4}
        wrapping_key = crypto.derive_key(password, kdf_salt, kdf_algorithm, kdf_params)

        ciphertext, iv, auth_tag = crypto.wrap_key(mk_raw, wrapping_key)
        wrapped_mk = iv + auth_tag + ciphertext

        # Se já tiver Windows Hello configurado, passa a ser híbrido; caso contrário, master_password
        current_auth = meta.get("auth_mode", "master_password")
        new_auth_mode = "hybrid" if current_auth in ("windows_hello", "hybrid") else "master_password"
        hello_id = meta.get("hello_credential_id")
        if new_auth_mode == "hybrid" and not hello_id:
            hello_id = str(uuid.uuid4())

        wrapped_hello = None
        if new_auth_mode == "hybrid" and hello_id:
            try:
                wrapped_hello = windows_hello.protect_data_dpapi(mk_raw, entropy=hello_id.encode("utf-8"))
            except Exception:
                wrapped_hello = meta.get("wrapped_hello_key")

        self.db.save_metadata(
            auth_mode=new_auth_mode,
            kdf_salt=kdf_salt,
            kdf_algorithm=kdf_algorithm,
            kdf_params=kdf_params,
            wrapped_master_key=wrapped_mk,
            wrapped_hello_key=wrapped_hello,
            hello_credential_id=hello_id,
            auto_lock_timeout=meta.get("auto_lock_timeout", 300),
            lock_on_os_lock=meta.get("lock_on_os_lock", True),
        )
        logger.info("Senha mestre redefinida e persistida com sucesso.")

        return {"success": True, "message": "Senha mestre definida com sucesso."}

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
            logger.warning("Tentativa de desbloqueio falhou: cofre não configurado.")
            raise ValueError("O cofre ainda não foi configurado. Execute a configuração inicial.")

        auth_mode = meta.get("auth_mode", "master_password")
        wrapped_mk = meta.get("wrapped_master_key")
        wrapped_hello = meta.get("wrapped_hello_key")

        if not wrapped_mk and not wrapped_hello:
            raise ValueError("Chave mestra não encontrada nos metadados do cofre.")

        mk_bytes: Optional[bytes] = None

        if use_hello and auth_mode in ("windows_hello", "hybrid"):
            # Solicita confirmação biométrica/PIN
            ok, msg = windows_hello.verify_windows_hello(reason)
            if not ok:
                logger.warning(f"Desbloqueio via Windows Hello recusado: {msg}")
                raise SafeAccessDeniedError(f"Windows Hello recusado: {msg}")

            hello_id = (meta.get("hello_credential_id") or "").encode("utf-8")

            # Se for base híbrida moderna mas wrapped_hello_key for NULL
            if auth_mode == "hybrid" and not wrapped_hello:
                logger.warning("Vínculo do Windows Hello ausente no cofre híbrido.")
                raise SafeAccessDeniedError(
                    "Vínculo do Windows Hello desatualizado. Desbloqueie com a Senha Mestra uma vez para restaurar o acesso por biometria/PIN."
                )

            # Prefere wrapped_hello_key; fallback para wrapped_mk apenas se for base legada pura windows_hello
            target_hello_blob = wrapped_hello if wrapped_hello else (wrapped_mk if auth_mode == "windows_hello" else None)
            if not target_hello_blob:
                raise SafeAccessDeniedError("Chave de segurança do Windows Hello não encontrada.")

            try:
                mk_bytes = windows_hello.unprotect_data_dpapi(target_hello_blob, entropy=hello_id if hello_id else None)
            except Exception as e:
                # Tenta fallback sem entropia para bases legadas
                try:
                    mk_bytes = windows_hello.unprotect_data_dpapi(target_hello_blob, entropy=None)
                except Exception:
                    logger.warning(f"Falha ao desencapsular chave DPAPI do Windows Hello: {e}")
                    raise SafeAccessDeniedError("Não foi possível desencapsular a chave com Windows Hello.") from e

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
                logger.warning("Tentativa de desbloqueio com senha mestre incorreta.")
                raise SafeAccessDeniedError("Senha mestre incorreta ou dados corrompidos.") from e

        if not mk_bytes or len(mk_bytes) != 32:
            logger.error("Chave mestra resultante do desencapsulamento é inválida.")
            raise SafeAccessDeniedError("Chave mestra inválida.")

        self._master_key = bytearray(mk_bytes)
        self.touch_activity()

        # Auto-Cura (Self-Healing): se o cofre é híbrido e wrapped_hello_key está ausente ou vazio
        if not use_hello and auth_mode == "hybrid":
            if not wrapped_hello or len(wrapped_hello) == 0:
                try:
                    hello_id_str = meta.get("hello_credential_id") or str(uuid.uuid4())
                    new_wrapped_hello = windows_hello.protect_data_dpapi(mk_bytes, entropy=hello_id_str.encode("utf-8"))
                    self.db.update_wrapped_hello_key(new_wrapped_hello, hello_id_str)
                    logger.info("Auto-cura realizada: envelope DPAPI do Windows Hello gerado e sincronizado no cofre híbrido.")
                except Exception as heal_err:
                    logger.debug(f"Aviso na auto-cura do Windows Hello: {heal_err}")

        logger.info(f"Cofre desbloqueado com sucesso (método: {'Windows Hello' if use_hello else 'Senha Mestra'}).")
        return True

    def lock(self, reason: str = "Solicitação do Usuário") -> bool:
        """
        Bloqueia o cofre imediatamente e limpa a chave da memória RAM (Zeroization).
        Notifica listeners registrados (como a UI).
        """
        if self._master_key is not None:
            crypto.zeroize(self._master_key)
            self._master_key = None
            logger.info(f"Cofre bloqueado com sucesso (motivo: {reason}).")

        for listener in list(self._on_lock_listeners):
            try:
                listener(reason)
            except Exception as e:
                logger.debug(f"Erro ao notificar on_lock_listener: {e}")

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
            logger.info(f"Credencial atualizada com sucesso: id={eid}, categoria={category}, titulo='{title}'")
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
            logger.info(f"Nova credencial salva com sucesso: id={eid}, categoria={category}, titulo='{title}'")

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
            logger.warning(f"Tentativa de leitura falhou: credencial '{entry_id}' não encontrada.")
            raise ValueError(f"Credencial com ID '{entry_id}' não encontrada.")

        # Validação de ACL se for requisitado por um plugin terceiro
        if requester_plugin_id:
            owner = entry.get("owner_plugin_id")
            if owner != requester_plugin_id:
                grant = self.db.get_grant(requester_plugin_id, entry_id)
                if not grant:
                    logger.warning(f"Acesso negado: plugin '{requester_plugin_id}' tentou acessar credencial '{entry_id}' sem permissão.")
                    raise SafeAccessDeniedError(
                        f"Plugin '{requester_plugin_id}' não possui permissão para acessar a credencial '{entry.get('title')}'."
                    )

        ciphertext = entry["encrypted_payload"]
        iv = entry["iv"]
        auth_tag = entry["auth_tag"]

        decrypted = crypto.decrypt_payload(ciphertext, iv, auth_tag, mk)
        logger.debug(f"Credencial descriptografada com sucesso: id={entry_id}, requisitante={requester_plugin_id or 'safe-ui'}")

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
                    logger.warning(f"Exclusão negada: plugin '{requester_plugin_id}' sem permissão de escrita para '{entry_id}'.")
                    raise SafeAccessDeniedError(f"Permissão insuficiente para excluir a credencial '{entry.get('title')}'.")

        deleted = self.db.delete_entry(entry_id)
        if deleted:
            logger.info(f"Credencial excluída com sucesso: id={entry_id}")
        return deleted

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
        logger.info(f"Permissão de acesso concedida: plugin='{target_plugin_id}', segredo='{entry_id}', nivel='{access_level}'")
        return {"success": True, "grant_id": grant_id}

    def revoke_permission(self, grant_id: str) -> bool:
        self._require_unlocked()
        revoked = self.db.delete_grant(grant_id)
        if revoked:
            logger.info(f"Permissão revogada com sucesso: grant_id='{grant_id}'")
        return revoked

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

    def update_security_settings(self, auto_lock_timeout: int, lock_on_os_lock: bool = True) -> Dict[str, Any]:
        """Atualiza configurações de segurança do cofre."""
        self._require_unlocked()
        self.db.update_security_settings(auto_lock_timeout, lock_on_os_lock)
        logger.info(f"Configurações de segurança atualizadas: timeout={auto_lock_timeout}s, lock_on_os_lock={lock_on_os_lock}")
        return {"success": True, "message": "Configurações de segurança atualizadas com sucesso."}

    # ========================================================================
    # Importação & Exportação de Segredos (Save in Cloud / Backups)
    # ========================================================================

    def export_secrets(
        self,
        format: str = "json",
        backup_password: Optional[str] = None,
    ) -> Union[List[Dict[str, Any]], bytes]:
        """
        Exporta todas as credenciais descriptografadas em formato estruturado ou container .safepack.
        """
        self._require_unlocked()
        entries = self.list_secrets()
        exported = []

        for entry in entries:
            try:
                secret_data = self.get_secret(entry["id"])
                exported.append({
                    "id": entry["id"],
                    "title": entry["title"],
                    "category": entry["category"],
                    "username_or_key": entry.get("username_or_key") or "",
                    "payload": secret_data.get("payload"),
                    "tags": entry.get("tags") or [],
                    "metadata": entry.get("metadata") or {},
                })
            except Exception:
                continue

        logger.info(f"Exportação de credenciais concluída: {len(exported)} itens exportados (formato: {format}).")

        if format == "safepack":
            if not backup_password or len(backup_password.strip()) < 4:
                raise ValueError("A senha de backup deve conter pelo menos 4 caracteres para o formato .safepack.")
            if not hasattr(crypto, "pack_safepack_container"):
                raise RuntimeError("Função de empacotamento .safepack não disponível.")
            payload_wrapper = {
                "version": 1,
                "exported_at": datetime.now().isoformat(),
                "entries": exported,
            }
            return crypto.pack_safepack_container(payload_wrapper, backup_password)

        return exported

    def preview_import(
        self,
        content_or_bytes: Union[str, bytes],
        filename: Optional[str] = None,
        backup_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gera uma pré-visualização dos registros a serem importados sem gravar no banco de dados.
        Identifica formato, total de registros, categorias e possíveis conflitos com itens existentes.
        """
        self._require_unlocked()

        if importers is None:
            raise RuntimeError("Módulo de importadores não disponível.")

        items, detected_format = importers.detect_and_parse_secrets(
            content_or_bytes, filename=filename, backup_password=backup_password
        )
        
        # Obtém títulos já existentes no banco para checar conflitos
        existing_entries = self.db.list_entries_summary()
        existing_titles = {e["title"].strip().lower(): e["id"] for e in existing_entries}

        conflicts_count = 0
        categories_count: Dict[str, int] = {}
        preview_list: List[Dict[str, Any]] = []

        for item in items:
            cat = item.get("category", "password")
            categories_count[cat] = categories_count.get(cat, 0) + 1

            t_clean = (item.get("title") or "").strip().lower()
            is_conflict = t_clean in existing_titles
            if is_conflict:
                conflicts_count += 1

            if len(preview_list) < 25:
                preview_list.append({
                    "title": item.get("title", "Sem Título"),
                    "category": cat,
                    "username": item.get("username_or_key") or "",
                    "has_password": bool(item.get("payload")),
                    "conflict": is_conflict,
                })

        return {
            "success": True,
            "format": detected_format,
            "total_detected": len(items),
            "conflicts_count": conflicts_count,
            "categories": categories_count,
            "preview_items": preview_list,
        }

    def import_secrets(
        self,
        items_or_payload: Union[List[Dict[str, Any]], Dict[str, Any], str, bytes],
        conflict_policy: str = "skip",
        filename: Optional[str] = None,
        backup_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Importa segredos (Microsoft Safe XML/CSV/TXT, Save in Cloud, .safepack ou JSON de backup).
        Políticas de conflito suportadas:
          - 'skip': Se o item já existir (mesmo título), não importa.
          - 'overwrite': Se o item já existir, atualiza os dados do registro existente.
          - 'duplicate': Se o item já existir, cria um novo registro com sufixo '(Importado)'.
        """
        mk = self._require_unlocked()

        raw_list: List[Dict[str, Any]] = []

        if isinstance(items_or_payload, (str, bytes)):
            if importers is None:
                raise RuntimeError("Módulo de importadores não disponível.")
            parsed_items, _ = importers.detect_and_parse_secrets(
                items_or_payload, filename=filename, backup_password=backup_password
            )
            raw_list = parsed_items
        elif isinstance(items_or_payload, dict):
            if "entries" in items_or_payload and isinstance(items_or_payload["entries"], list):
                raw_list = items_or_payload["entries"]
            elif "secrets" in items_or_payload and isinstance(items_or_payload["secrets"], list):
                raw_list = items_or_payload["secrets"]
            elif "items" in items_or_payload and isinstance(items_or_payload["items"], list):
                raw_list = items_or_payload["items"]
            else:
                raw_list = [items_or_payload]
        elif isinstance(items_or_payload, list):
            raw_list = items_or_payload
        else:
            raise ValueError("Formato de dados para importação inválido.")

        existing_entries = self.db.list_entries_summary()
        existing_map = {e["title"].strip().lower(): e for e in existing_entries}

        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors: List[str] = []

        entries_to_batch: List[Dict[str, Any]] = []

        for item in raw_list:
            if not isinstance(item, dict):
                skipped_count += 1
                continue

            title = str(item.get("title") or item.get("name") or "").strip()
            payload = item.get("payload") or item.get("secret") or item.get("password") or item.get("value")
            
            if not title or payload is None:
                skipped_count += 1
                continue

            category = str(item.get("category", "password")).strip()
            username_or_key = item.get("username_or_key") or item.get("username") or item.get("key") or ""
            tags = item.get("tags", [])
            metadata = item.get("metadata", {})

            t_lower = title.lower()
            existing = existing_map.get(t_lower)

            secret_id_to_use = None
            final_title = title

            if existing:
                if conflict_policy == "skip":
                    skipped_count += 1
                    continue
                elif conflict_policy == "overwrite":
                    secret_id_to_use = existing["id"]
                    final_title = existing["title"]
                elif conflict_policy == "duplicate":
                    # Gera um título com sufixo
                    suffix_idx = 1
                    candidate = f"{title} (Importado)"
                    while candidate.lower() in existing_map:
                        suffix_idx += 1
                        candidate = f"{title} (Importado {suffix_idx})"
                    final_title = candidate

            entry_id = secret_id_to_use or str(uuid.uuid4())

            try:
                ciphertext, iv, auth_tag = crypto.encrypt_payload(payload, mk)
                entries_to_batch.append({
                    "id": entry_id,
                    "title": final_title,
                    "category": category,
                    "owner_plugin_id": None,
                    "username_or_key": str(username_or_key).strip() if username_or_key else None,
                    "encrypted_payload": ciphertext,
                    "iv": iv,
                    "auth_tag": auth_tag,
                    "tags": tags if isinstance(tags, list) else [],
                    "metadata": metadata if isinstance(metadata, dict) else {},
                })
                if existing and conflict_policy == "overwrite":
                    updated_count += 1
                else:
                    imported_count += 1
                existing_map[final_title.lower()] = {"id": entry_id, "title": final_title}
            except Exception as e:
                errors.append(f"Erro ao processar item '{title}': {e}")

        if entries_to_batch:
            try:
                self.db.save_entries_batch(entries_to_batch)
            except Exception as e:
                logger.error(f"Falha ao persistir lote de credenciais importadas: {e}")
                raise

        logger.info(
            f"Importação de credenciais concluída: {imported_count} criadas, "
            f"{updated_count} atualizadas, {skipped_count} ignoradas de um total de {len(raw_list)}."
        )
        return {
            "success": True,
            "imported": imported_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "total": len(raw_list),
            "errors": errors,
            "message": f"{imported_count + updated_count} credenciais processadas com sucesso ({imported_count} criadas, {updated_count} atualizadas, {skipped_count} ignoradas).",
        }

