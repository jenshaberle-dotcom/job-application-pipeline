from __future__ import annotations

from pathlib import Path


def test_aggregator_novelty_migration_defines_review_tables_and_guardrails() -> None:
    sql = Path("db/migrations/036_create_aggregator_novelty_loop_snapshots.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS aggregator_novelty_snapshots" in sql
    assert "CREATE TABLE IF NOT EXISTS aggregator_novelty_items" in sql
    assert "no pagination" in sql.lower()
    assert "no search-profile mutation" in sql.lower()
    assert "no Bronze writes" in sql
    assert "pause_or_retire_current_query" in sql
    assert "unregistered_company_count" in sql
    assert "newly_observed_company_count" in sql
    assert "previous_snapshot_id" in sql
