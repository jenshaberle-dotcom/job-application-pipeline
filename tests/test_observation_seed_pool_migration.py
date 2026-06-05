from __future__ import annotations

from pathlib import Path

MIGRATION = Path("db/migrations/068_create_observation_seed_pool_snapshots.sql")


def test_seed_pool_migration_creates_seed_snapshot_table() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS origin_observation_seed_pool_snapshots" in sql
    assert "origin_job_observation_runs" in sql
    assert "seed_source_type_counts" in sql
    assert "learning_value_by_source_type" in sql


def test_seed_pool_migration_preserves_learning_only_boundary() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "must not pass candidate gates" in sql
    assert "no_gate_decision" not in sql  # boundary is enforced in code snapshots/evidence, not column default here
    assert "company_name_only_seed" in sql
    assert "aggregator_company_seed" in sql
    assert "job_text_signal_seed" in sql
