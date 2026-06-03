from pathlib import Path

from scripts.apply_db_migrations import (
    TrackedMigration,
    checksum_mismatches,
    discover_migration_files,
    parse_migration_file,
    pending_migrations,
)


def test_parse_migration_file_uses_filename_as_key(tmp_path: Path) -> None:
    migration = tmp_path / "004_example.sql"
    migration.write_text("SELECT 1;\n", encoding="utf-8")

    parsed = parse_migration_file(migration)

    assert parsed is not None
    assert parsed.version_number == 4
    assert parsed.filename == "004_example.sql"
    assert parsed.migration_key == "004_example.sql"
    assert len(parsed.checksum_sha256) == 64


def test_discover_migrations_tolerates_duplicate_version_numbers(tmp_path: Path) -> None:
    (tmp_path / "004_b.sql").write_text("SELECT 2;\n", encoding="utf-8")
    (tmp_path / "004_a.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "005_c.sql").write_text("SELECT 3;\n", encoding="utf-8")

    filenames = [migration.filename for migration in discover_migration_files(tmp_path)]

    assert filenames == ["004_a.sql", "004_b.sql", "005_c.sql"]


def test_pending_migrations_uses_migration_key_not_version_number(tmp_path: Path) -> None:
    first = tmp_path / "004_a.sql"
    second = tmp_path / "004_b.sql"
    first.write_text("SELECT 1;\n", encoding="utf-8")
    second.write_text("SELECT 2;\n", encoding="utf-8")

    migrations = discover_migration_files(tmp_path)
    tracked = {
        migrations[0].migration_key: TrackedMigration(
            migration_key=migrations[0].migration_key,
            version_number=migrations[0].version_number,
            filename=migrations[0].filename,
            checksum_sha256=migrations[0].checksum_sha256,
            execution_status="bootstrapped",
            execution_mode="manual_bootstrap",
            applied_by="test",
        )
    }

    assert [migration.filename for migration in pending_migrations(migrations, tracked)] == ["004_b.sql"]


def test_checksum_mismatch_detects_changed_tracked_file(tmp_path: Path) -> None:
    migration = tmp_path / "010_example.sql"
    migration.write_text("SELECT 1;\n", encoding="utf-8")
    parsed = parse_migration_file(migration)
    assert parsed is not None

    tracked = {
        parsed.migration_key: TrackedMigration(
            migration_key=parsed.migration_key,
            version_number=parsed.version_number,
            filename=parsed.filename,
            checksum_sha256="0" * 64,
            execution_status="bootstrapped",
            execution_mode="manual_bootstrap",
            applied_by="test",
        )
    }

    mismatches = checksum_mismatches([parsed], tracked)

    assert mismatches == [(parsed, tracked[parsed.migration_key])]


def test_script_uses_shared_database_config() -> None:
    text = Path("scripts/apply_db_migrations.py").read_text(encoding="utf-8")

    assert "from src.config import get_database_config" in text
    assert "psycopg.connect(**get_database_config()" in text
    assert "os.environ[" not in text
