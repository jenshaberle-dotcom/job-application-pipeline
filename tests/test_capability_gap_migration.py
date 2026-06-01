from __future__ import annotations

from pathlib import Path


def test_capability_gap_migration_creates_expected_tables() -> None:
    sql = Path("db/migrations/034_create_capability_gap_foundation.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS capability_gap_scores" in sql
    assert "priority_score" in sql
    assert "supporting_terms JSONB" in sql
    assert "no search-profile mutation" in sql
