"""
Testes unitários para a camada de banco de dados SQLite do plugin Safe.
"""

import os
import tempfile
import sys
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from safe.db import SafeDatabase


def test_db_schema_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_vault.db"
        safe_db = SafeDatabase(db_path)
        assert db_path.exists()

        # Verifica se as tabelas existem
        with safe_db.connect() as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            assert "safe_metadata" in tables
            assert "safe_entries" in tables
            assert "safe_plugin_grants" in tables


def test_db_metadata_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        safe_db = SafeDatabase(Path(tmpdir) / "test_vault.db")
        assert safe_db.get_metadata() is None

        safe_db.save_metadata(
            auth_mode="hybrid",
            kdf_salt=b"1234567890123456",
            kdf_algorithm="argon2id",
            kdf_params={"iterations": 3},
            wrapped_master_key=b"wrapped_mk_blob",
            hello_credential_id="cred-123",
            auto_lock_timeout=600,
        )

        meta = safe_db.get_metadata()
        assert meta is not None
        assert meta["auth_mode"] == "hybrid"
        assert meta["kdf_salt"] == b"1234567890123456"
        assert meta["auto_lock_timeout"] == 600
        assert meta["kdf_params"] == {"iterations": 3}

        safe_db.update_auto_lock_timeout(120)
        meta2 = safe_db.get_metadata()
        assert meta2["auto_lock_timeout"] == 120


def test_db_entries_and_grants_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        safe_db = SafeDatabase(Path(tmpdir) / "test_vault.db")

        # Inserir entry
        safe_db.insert_entry(
            entry_id="entry-1",
            title="AWS Root Account",
            category="password",
            owner_plugin_id=None,
            username_or_key="root@company.com",
            encrypted_payload=b"encrypted_bytes_payload",
            iv=b"123456789012",
            auth_tag=b"1234567890123456",
            tags=["aws", "cloud"],
            metadata={"env": "prod"},
        )

        assert safe_db.count_entries() == 1
        entry = safe_db.get_entry("entry-1")
        assert entry is not None
        assert entry["title"] == "AWS Root Account"
        assert entry["tags"] == ["aws", "cloud"]
        assert entry["metadata"] == {"env": "prod"}
        assert entry["encrypted_payload"] == b"encrypted_bytes_payload"

        # List summary (sem payload)
        summary = safe_db.list_entries_summary(category="password")
        assert len(summary) == 1
        assert summary[0]["title"] == "AWS Root Account"
        assert "encrypted_payload" not in summary[0]

        # Inserir grant
        safe_db.add_grant(
            grant_id="grant-1",
            plugin_id="plugin-aws",
            entry_id="entry-1",
            access_level="read",
        )

        grant = safe_db.get_grant("plugin-aws", "entry-1")
        assert grant is not None
        assert grant["access_level"] == "read"

        # Deletar entry deve deletar grants em cascata (FK CASCADE)
        assert safe_db.delete_entry("entry-1") is True
        assert safe_db.get_entry("entry-1") is None
        assert safe_db.get_grant("plugin-aws", "entry-1") is None


def test_get_default_db_path():
    from safe.db import get_default_db_path
    from shared.db_utils import get_central_db_path
    path = get_default_db_path()
    assert path.name == "toolbox.db"
    assert path == get_central_db_path()
    if sys.platform == "win32" and "APPDATA" in os.environ:
        assert "com.toolbox.desktop" in str(path)


def test_legacy_vault_migration():
    with tempfile.TemporaryDirectory() as tmpdir:
        legacy_vault = Path(tmpdir) / "vault.db"
        # Cria e popula banco legado
        old_db = SafeDatabase(legacy_vault)
        old_db.save_metadata(
            auth_mode="master_password",
            kdf_salt=b"salt_legado_1234",
            kdf_algorithm="argon2id",
            kdf_params={"time_cost": 3},
            wrapped_master_key=b"mk_legada_1234567890",
            auto_lock_timeout=180,
        )
        old_db.insert_entry(
            entry_id="leg-1",
            title="Credencial Legada",
            category="api_key",
            owner_plugin_id=None,
            username_or_key="user_legado",
            encrypted_payload=b"cifrado_legado",
            iv=b"iv1234567890",
            auth_tag=b"tag1234567890123",
        )

        # Novo banco central toolbox.db
        central_db_path = Path(tmpdir) / "toolbox.db"
        central_db = SafeDatabase(central_db_path)
        
        # Executa migração explícita passando o caminho do legado
        migrated = central_db.migrate_legacy_vault_if_exists(legacy_path=legacy_vault)
        assert migrated is True

        # Valida que os dados foram transferidos para o central
        meta = central_db.get_metadata()
        assert meta is not None
        assert meta["auth_mode"] == "master_password"
        assert meta["kdf_salt"] == b"salt_legado_1234"
        assert central_db.count_entries() == 1
        entry = central_db.get_entry("leg-1")
        assert entry is not None
        assert entry["title"] == "Credencial Legada"

        # Valida que o legado foi renomeado para .bak
        assert not legacy_vault.exists()
        bak_file = Path(tmpdir) / "vault.db.migrated.bak"
        assert bak_file.exists()


def test_legacy_toolbox_folder_migration():
    """Valida migração a partir da pasta órfã %APPDATA%/Toolbox/toolbox.db para o central."""
    with tempfile.TemporaryDirectory() as tmpdir:
        orphan_db_path = Path(tmpdir) / "Toolbox" / "toolbox.db"
        orphan_db_path.parent.mkdir(parents=True)
        
        # Popula o banco órfão
        orphan_db = SafeDatabase(orphan_db_path)
        orphan_db.save_metadata(
            auth_mode="windows_hello",
            kdf_salt=None,
            kdf_algorithm="argon2id",
            kdf_params={},
            wrapped_master_key=b"wrapped_hello_key_blob",
            hello_credential_id="cred-guid-123",
            auto_lock_timeout=300,
        )
        orphan_db.insert_entry(
            entry_id="entry-orphan-1",
            title="Credencial Órfã",
            category="password",
            owner_plugin_id=None,
            username_or_key="admin",
            encrypted_payload=b"encrypted_secret_data",
            iv=b"iv1234567890",
            auth_tag=b"auth_tag_12345678",
        )

        # Novo banco oficial unificado
        canonical_db_path = Path(tmpdir) / "com.toolbox.desktop" / "toolbox.db"
        canonical_db_path.parent.mkdir(parents=True)
        canonical_db = SafeDatabase(canonical_db_path)

        # Executa migração
        migrated = canonical_db.migrate_legacy_vault_if_exists(legacy_path=orphan_db_path)
        assert migrated is True

        # Valida dados migrados
        meta = canonical_db.get_metadata()
        assert meta is not None
        assert meta["auth_mode"] == "windows_hello"
        assert meta["hello_credential_id"] == "cred-guid-123"
        assert canonical_db.count_entries() == 1
        entry = canonical_db.get_entry("entry-orphan-1")
        assert entry is not None
        assert entry["title"] == "Credencial Órfã"

        # Valida que o banco órfão virou .bak
        assert not orphan_db_path.exists()
        bak_file = orphan_db_path.with_suffix(".db.migrated.bak")
        assert bak_file.exists()
