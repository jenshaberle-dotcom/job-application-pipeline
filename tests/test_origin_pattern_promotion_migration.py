from __future__ import annotations

from pathlib import Path

MIGRATION = Path("db/migrations/065_create_origin_pattern_promotion_runs.sql")


def test_pattern_promotion_migration_creates_audit_tables_and_view() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS origin_pattern_promotion_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS origin_pattern_promotion_decisions" in sql
    assert "CREATE OR REPLACE VIEW gold_origin_promoted_observation_patterns" in sql


def test_pattern_promotion_migration_preserves_learning_boundary() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert '"learning_input_only": true' in sql
    assert '"no_gate_decision": true' in sql
    assert '"no_candidate_status_mutation": true' in sql
    assert '"no_bronze_write": true' in sql
    assert '"no_silver_write": true' in sql
    assert '"pattern_usage_requires_promotion": true' in sql
