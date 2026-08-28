"""
Camada de Banco de Dados e Migrações do Plugin Safe - SQLite.

Gerencia as tabelas safe_metadata, safe_entries e safe_plugin_grants.
Garante liberação imediata de file handles no Windows.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union


def get_default_db_path() -> Path:
    """
    Retorna o caminho padrão para a base SQLite do cofre no diretório de dados do usuário.
    """
    app_data = os.environ.get("APPDATA")
    if app_data:
        base_dir = Path(app_data) / "Toolbox" / "safe"
    else:
        base_dir = Path.home() / ".toolbox" / "safe"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "vault.db"


class SafeDatabase:
    """
    Controlador de persistência SQLite com suporte a migrations e transações.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager que abre e fecha a conexão com segurança."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Executa as migrations para inicializar ou atualizar a estrutura do banco."""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # Tabela: Metadados do Cofre
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS safe_metadata (
                id TEXT PRIMARY KEY,
                auth_mode TEXT NOT NULL,
                kdf_salt BLOB,
                kdf_algorithm TEXT DEFAULT 'argon2id',
                kdf_params TEXT,
                wrapped_master_key BLOB,
                hello_credential_id TEXT,
                auto_lock_timeout INTEGER DEFAULT 300,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Tabela: Registros de Segredos Cifrados
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS safe_entries (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                owner_plugin_id TEXT,
                username_or_key TEXT,
                encrypted_payload BLOB NOT NULL,
                iv BLOB NOT NULL,
                auth_tag BLOB NOT NULL,
                tags TEXT,
                metadata TEXT,
                is_locked BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Tabela: Permissões Concedidas a Outros Plugins
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS safe_plugin_grants (
                id TEXT PRIMARY KEY,
                plugin_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                access_level TEXT NOT NULL,
                granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                FOREIGN KEY (entry_id) REFERENCES safe_entries(id) ON DELETE CASCADE
            );
            """)

            # Índices para performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_safe_entries_cat ON safe_entries(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_safe_entries_owner ON safe_entries(owner_plugin_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_safe_grants_plugin ON safe_plugin_grants(plugin_id);")

            conn.commit()

    # ========================================================================
    # Operações de Metadados (Configuração do Cofre)
    # ========================================================================

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM safe_metadata WHERE id = 'default_vault';")
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("kdf_params") and isinstance(data["kdf_params"], str):
                try:
                    data["kdf_params"] = json.loads(data["kdf_params"])
                except Exception:
                    pass
            return data

    def save_metadata(
        self,
        auth_mode: str,
        kdf_salt: Optional[bytes],
        kdf_algorithm: str,
        kdf_params: Dict[str, Any],
        wrapped_master_key: Optional[bytes],
        hello_credential_id: Optional[str] = None,
        auto_lock_timeout: int = 300,
    ) -> None:
        with self.connect() as conn:
            cursor = conn.cursor()
            params_json = json.dumps(kdf_params or {})
            cursor.execute("""
            INSERT INTO safe_metadata (
                id, auth_mode, kdf_salt, kdf_algorithm, kdf_params,
                wrapped_master_key, hello_credential_id, auto_lock_timeout, updated_at
            ) VALUES ('default_vault', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                auth_mode = excluded.auth_mode,
                kdf_salt = excluded.kdf_salt,
                kdf_algorithm = excluded.kdf_algorithm,
                kdf_params = excluded.kdf_params,
                wrapped_master_key = excluded.wrapped_master_key,
                hello_credential_id = excluded.hello_credential_id,
                auto_lock_timeout = excluded.auto_lock_timeout,
                updated_at = CURRENT_TIMESTAMP;
            """, (
                auth_mode,
                kdf_salt,
                kdf_algorithm,
                params_json,
                wrapped_master_key,
                hello_credential_id,
                auto_lock_timeout,
            ))
            conn.commit()

    def update_auto_lock_timeout(self, timeout_seconds: int) -> None:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE safe_metadata SET auto_lock_timeout = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 'default_vault';
            """, (timeout_seconds,))
            conn.commit()

    # ========================================================================
    # Operações de Registros (safe_entries)
    # ========================================================================

    def insert_entry(
        self,
        entry_id: str,
        title: str,
        category: str,
        owner_plugin_id: Optional[str],
        username_or_key: Optional[str],
        encrypted_payload: bytes,
        iv: bytes,
        auth_tag: bytes,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self.connect() as conn:
            cursor = conn.cursor()
            tags_json = json.dumps(tags or [])
            meta_json = json.dumps(metadata or {})
            cursor.execute("""
            INSERT INTO safe_entries (
                id, title, category, owner_plugin_id, username_or_key,
                encrypted_payload, iv, auth_tag, tags, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
            """, (
                entry_id,
                title,
                category,
                owner_plugin_id,
                username_or_key,
                encrypted_payload,
                iv,
                auth_tag,
                tags_json,
                meta_json,
            ))
            conn.commit()

    def update_entry(
        self,
        entry_id: str,
        title: str,
        category: str,
        username_or_key: Optional[str],
        encrypted_payload: bytes,
        iv: bytes,
        auth_tag: bytes,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self.connect() as conn:
            cursor = conn.cursor()
            tags_json = json.dumps(tags or [])
            meta_json = json.dumps(metadata or {})
            cursor.execute("""
            UPDATE safe_entries SET
                title = ?,
                category = ?,
                username_or_key = ?,
                encrypted_payload = ?,
                iv = ?,
                auth_tag = ?,
                tags = ?,
                metadata = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """, (
                title,
                category,
                username_or_key,
                encrypted_payload,
                iv,
                auth_tag,
                tags_json,
                meta_json,
                entry_id,
            ))
            conn.commit()
            return cursor.rowcount > 0

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM safe_entries WHERE id = ?;", (entry_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("tags"):
                try:
                    data["tags"] = json.loads(data["tags"])
                except Exception:
                    data["tags"] = []
            if data.get("metadata"):
                try:
                    data["metadata"] = json.loads(data["metadata"])
                except Exception:
                    data["metadata"] = {}
            return data

    def list_entries_summary(
        self,
        category: Optional[str] = None,
        owner_plugin_id: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retorna listagem resumida dos registros (sem expor payloads criptografados).
        """
        with self.connect() as conn:
            cursor = conn.cursor()
            query = """
            SELECT id, title, category, owner_plugin_id, username_or_key, tags, metadata, is_locked, created_at, updated_at
            FROM safe_entries
            WHERE 1=1
            """
            params: List[Any] = []

            if category and category != "all":
                query += " AND category = ?"
                params.append(category)

            if owner_plugin_id:
                query += " AND (owner_plugin_id = ? OR owner_plugin_id IS NULL)"
                params.append(owner_plugin_id)

            if search_query:
                query += " AND (title LIKE ? OR username_or_key LIKE ? OR tags LIKE ?)"
                like_term = f"%{search_query}%"
                params.extend([like_term, like_term, like_term])

            query += " ORDER BY updated_at DESC;"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                item = dict(row)
                if item.get("tags"):
                    try:
                        item["tags"] = json.loads(item["tags"])
                    except Exception:
                        item["tags"] = []
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        item["metadata"] = {}
                results.append(item)
            return results

    def delete_entry(self, entry_id: str) -> bool:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM safe_entries WHERE id = ?;", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def count_entries(self) -> int:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM safe_entries;")
            row = cursor.fetchone()
            return row[0] if row else 0

    # ========================================================================
    # Operações de Permissões (safe_plugin_grants)
    # ========================================================================

    def add_grant(
        self,
        grant_id: str,
        plugin_id: str,
        entry_id: str,
        access_level: str = "read",
        expires_at: Optional[str] = None,
    ) -> None:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO safe_plugin_grants (
                id, plugin_id, entry_id, access_level, granted_at, expires_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(id) DO UPDATE SET
                access_level = excluded.access_level,
                expires_at = excluded.expires_at;
            """, (grant_id, plugin_id, entry_id, access_level, expires_at))
            conn.commit()

    def get_grant(self, plugin_id: str, entry_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM safe_plugin_grants
            WHERE plugin_id = ? AND entry_id = ?
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP);
            """, (plugin_id, entry_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_grants(self, plugin_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            cursor = conn.cursor()
            query = """
            SELECT g.id, g.plugin_id, g.entry_id, g.access_level, g.granted_at, g.expires_at, e.title as entry_title
            FROM safe_plugin_grants g
            LEFT JOIN safe_entries e ON g.entry_id = e.id
            """
            params: List[Any] = []
            if plugin_id:
                query += " WHERE g.plugin_id = ?"
                params.append(plugin_id)
            query += " ORDER BY g.granted_at DESC;"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def delete_grant(self, grant_id: str) -> bool:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM safe_plugin_grants WHERE id = ?;", (grant_id,))
            conn.commit()
            return cursor.rowcount > 0
