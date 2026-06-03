from pathlib import Path


MIGRATION_PATH = Path("db/migrations/052_mark_enercity_candidate_active_controlled.sql")


def test_enercity_active_controlled_migration_is_guarded() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "UPDATE employer_origin_source_candidates" in sql
    assert "status = 'active_controlled'" in sql
    assert "company_key = 'enercity'" in sql
    assert "source_name_candidate = 'enercity:discovery'" in sql
    assert "search_profiles" in sql
    assert "ingestion_runs" in sql
    assert "silver_jobs" in sql
    assert "051_activate_enercity_discovery_source_target.sql" in sql
    assert "first successful ingestion run 527" in sql


def test_enercity_active_controlled_migration_keeps_boundary() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "does not create search profiles" in sql
    assert "does not run ingestion" in sql
    assert "does not write raw_jobs or silver_jobs" in sql
    assert "scheduler configuration" in sql
