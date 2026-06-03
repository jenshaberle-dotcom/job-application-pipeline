from pathlib import Path


MIGRATION_PATH = Path("db/migrations/054_create_schema_migrations.sql")


def test_schema_migrations_table_uses_filename_identity() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in sql
    assert "migration_key TEXT PRIMARY KEY" in sql
    assert "filename TEXT NOT NULL UNIQUE" in sql
    assert "version_number INTEGER NOT NULL" in sql
    assert "version_number INTEGER NOT NULL UNIQUE" not in sql
    assert "idx_schema_migrations_version_number" in sql


def test_schema_migrations_table_tracks_checksum_and_status() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "checksum_sha256 TEXT NOT NULL" in sql
    assert "chk_schema_migrations_checksum_sha256" in sql
    assert "execution_status IN ('bootstrapped', 'success', 'failed')" in sql
    assert "execution_mode IN ('manual_bootstrap', 'script_apply', 'manual_tracking_migration')" in sql


def test_schema_migrations_migration_keeps_boundary() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "does not mark existing migrations as applied" in sql
    assert "does not run other migrations" in sql
    assert "does not modify pipeline data" in sql
    assert "CSV/Excel/export artifacts" in sql
