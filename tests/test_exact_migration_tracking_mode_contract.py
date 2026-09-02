from pathlib import Path


TRACKING_FOUNDATION = Path("db/migrations/054_create_schema_migrations.sql")
TRACKING_MODE_REPAIR = Path("db/migrations/105_allow_exact_script_migration_tracking_mode.sql")
RUNNER = Path("scripts/apply_db_migrations.py")


def test_forward_migration_adds_exact_script_tracking_mode() -> None:
    sql = TRACKING_MODE_REPAIR.read_text(encoding="utf-8")

    assert "DROP CONSTRAINT IF EXISTS chk_schema_migrations_execution_mode" in sql
    assert "ADD CONSTRAINT chk_schema_migrations_execution_mode" in sql
    assert "'manual_bootstrap'" in sql
    assert "'script_apply'" in sql
    assert "'script_apply_exact'" in sql
    assert "'manual_tracking_migration'" in sql


def test_exact_runner_and_tracking_schema_use_same_mode() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    repair = TRACKING_MODE_REPAIR.read_text(encoding="utf-8")
    exact_apply = runner[runner.index("def apply_exact_migration(") : runner.index("def build_parser(")]

    assert 'execution_mode="script_apply_exact"' in exact_apply
    assert "'script_apply_exact'" in repair


def test_tracking_foundation_remains_historical_and_repair_is_forward_only() -> None:
    foundation = TRACKING_FOUNDATION.read_text(encoding="utf-8")

    assert "'script_apply_exact'" not in foundation
    assert TRACKING_MODE_REPAIR.name.startswith("105_")
