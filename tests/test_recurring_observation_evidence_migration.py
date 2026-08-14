from __future__ import annotations

from pathlib import Path


MIGRATION = Path("db/migrations/095_add_recurring_observation_evidence_hash.sql")


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_adds_nullable_hash_and_contract_columns() -> None:
    sql = migration_sql()

    assert "ADD COLUMN IF NOT EXISTS normalized_evidence_hash text" in sql
    assert "ADD COLUMN IF NOT EXISTS evidence_contract_version text" in sql
    assert "job_observations_evidence_hash_contract_pair_check" in sql
    assert "normalized_evidence_hash ~ '^[0-9a-f]{64}$'" in sql
    assert "NULLIF(BTRIM(evidence_contract_version), '') IS NOT NULL" in sql


def test_migration_does_not_invent_historical_hashes() -> None:
    sql = migration_sql().casefold()

    assert "update job_observations" not in sql
    assert "insert into job_observations" not in sql
    assert "backfill old observations" not in sql


def test_migration_has_no_product_or_lifecycle_side_effects() -> None:
    sql = migration_sql().casefold()

    assert "update raw_jobs" not in sql
    assert "update silver_jobs" not in sql
    assert "insert into silver_jobs" not in sql
    assert "job_lifecycle_health" not in sql
    assert "ranking" not in sql.replace("-- source-activation or scheduler state", "")
    assert "application" not in sql.replace(
        "-- boundary: observability only. no lifecycle, silver, ranking, application,",
        "",
    )
