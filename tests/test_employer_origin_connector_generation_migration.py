from __future__ import annotations

from pathlib import Path


def test_s6a_connector_generation_migration_creates_expected_table_and_boundaries() -> None:
    sql = Path("db/migrations/035_create_employer_origin_connector_generation_plans.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS employer_origin_connector_generation_plans" in sql
    assert "candidate_id BIGINT NOT NULL" in sql
    assert "REFERENCES employer_origin_source_candidates" in sql
    assert "generation_status" in sql
    assert "recommendation" in sql
    assert "no auto-PR creation" in sql
    assert "no source activation" in sql
    assert "no Bronze writes" in sql
    assert "no CSV/Excel/export artifact as pipeline input" in sql
