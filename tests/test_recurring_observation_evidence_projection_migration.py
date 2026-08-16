from __future__ import annotations

from pathlib import Path


MIGRATION = Path("db/migrations/097_add_recurring_observation_evidence_projection.sql")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def executable_sql() -> str:
    return "\n".join(
        line
        for line in migration_sql().splitlines()
        if not line.lstrip().startswith("--")
    ).casefold()


def test_migration_adds_nullable_jsonb_projection_with_fail_closed_shape() -> None:
    sql = migration_sql()

    assert "ADD COLUMN IF NOT EXISTS normalized_evidence jsonb" in sql
    assert "job_observations_normalized_evidence_shape_check" in sql
    assert "normalized_evidence IS NULL" in sql
    assert "jsonb_typeof(normalized_evidence) = 'object'" in sql
    assert "normalized_evidence ? 'source_url'" in sql
    assert "normalized_evidence ? 'raw_evidence'" in sql
    assert "jsonb_typeof(normalized_evidence -> 'source_url') = 'string'" in sql
    assert "jsonb_typeof(normalized_evidence -> 'raw_evidence') = 'object'" in sql


def test_migration_does_not_backfill_or_infer_historical_evidence() -> None:
    sql = executable_sql()

    assert "update job_observations" not in sql
    assert "insert into job_observations" not in sql
    assert "from raw_jobs" not in sql


def test_migration_does_not_change_bronze_or_product_semantics() -> None:
    sql = executable_sql()

    for forbidden in (
        "update raw_jobs",
        "insert into raw_jobs",
        "update silver_jobs",
        "insert into silver_jobs",
        "job_lifecycle_health",
        "ranking",
        "application",
        "scheduler",
        "provider",
        "openai",
        "tavily",
    ):
        assert forbidden not in sql
