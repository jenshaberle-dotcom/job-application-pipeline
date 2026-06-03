from pathlib import Path


MIGRATION_PATH = Path("db/migrations/053_normalize_gold_source_health_active_controlled_status.sql")


def test_gold_source_health_status_uses_active_controlled_term() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW gold_source_health_summary" in sql
    assert "THEN 'active_controlled'" in sql
    assert "THEN 'controlled_active'" not in sql
    assert "candidate_status = 'active_controlled'" in sql
    assert "active_controlled_count" in sql


def test_gold_source_health_status_migration_keeps_boundary() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "does not update source candidates" in sql
    assert "does not create search profiles" in sql
    assert "does not run ingestion" in sql
    assert "does not write raw_jobs, silver_jobs or snapshots" in sql
    assert "scheduler configuration" in sql
