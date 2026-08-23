from pathlib import Path

import pytest

from scripts.apply_db_migrations import (
    TrackedMigration,
    build_parser,
    checksum_mismatches,
    discover_migration_files,
    parse_migration_file,
    pending_migrations,
    select_exact_pending_migration,
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


def test_exact_migration_selects_only_requested_pending_file(tmp_path: Path) -> None:
    target = tmp_path / "101_target.sql"
    target.write_text("SELECT 101;\n", encoding="utf-8")
    migrations = discover_migration_files(tmp_path)

    selected, state = select_exact_pending_migration(
        migrations=migrations,
        tracked={},
        migration_key="101_target.sql",
        require_sole_pending=True,
    )

    assert selected.filename == "101_target.sql"
    assert state == "pending"


def test_exact_migration_refuses_unresolved_target(tmp_path: Path) -> None:
    (tmp_path / "101_target.sql").write_text("SELECT 101;\n", encoding="utf-8")
    migrations = discover_migration_files(tmp_path)

    with pytest.raises(ValueError, match="must resolve once"):
        select_exact_pending_migration(
            migrations=migrations,
            tracked={},
            migration_key="999_missing.sql",
            require_sole_pending=True,
        )


def test_exact_migration_refuses_additional_pending_files_when_required(tmp_path: Path) -> None:
    (tmp_path / "100_other.sql").write_text("SELECT 100;\n", encoding="utf-8")
    (tmp_path / "101_target.sql").write_text("SELECT 101;\n", encoding="utf-8")
    migrations = discover_migration_files(tmp_path)

    with pytest.raises(RuntimeError, match="sole pending target"):
        select_exact_pending_migration(
            migrations=migrations,
            tracked={},
            migration_key="101_target.sql",
            require_sole_pending=True,
        )


def test_exact_migration_reports_already_applied_without_reselecting_pending(tmp_path: Path) -> None:
    target = tmp_path / "101_target.sql"
    target.write_text("SELECT 101;\n", encoding="utf-8")
    migrations = discover_migration_files(tmp_path)
    parsed = migrations[0]
    tracked = {
        parsed.migration_key: TrackedMigration(
            migration_key=parsed.migration_key,
            version_number=parsed.version_number,
            filename=parsed.filename,
            checksum_sha256=parsed.checksum_sha256,
            execution_status="success",
            execution_mode="script_apply_exact",
            applied_by="test",
        )
    }

    selected, state = select_exact_pending_migration(
        migrations=migrations,
        tracked=tracked,
        migration_key="101_target.sql",
        require_sole_pending=True,
    )

    assert selected.filename == "101_target.sql"
    assert state == "already_applied"


def test_parser_exposes_exact_apply_and_sole_pending_guard() -> None:
    args = build_parser().parse_args(
        [
            "--apply-exact",
            "101_create_job_review_relevance_label_events.sql",
            "--require-sole-pending",
            "--applied-by",
            "ml-pilot-001b",
        ]
    )

    assert args.apply_exact == "101_create_job_review_relevance_label_events.sql"
    assert args.require_sole_pending is True
    assert args.applied_by == "ml-pilot-001b"


def test_script_uses_shared_database_config() -> None:
    text = Path("scripts/apply_db_migrations.py").read_text(encoding="utf-8")

    assert "from src.config import get_database_config" in text
    assert "psycopg.connect(**get_database_config()" in text
    assert "os.environ[" not in text
