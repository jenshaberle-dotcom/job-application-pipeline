from pathlib import Path


MIGRATION = Path("db/migrations/040_create_search_intelligence_orchestrator_runs.sql")


def test_nightly_orchestrator_migration_contains_audit_tables_and_guardrails() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists search_intelligence_orchestrator_runs" in sql
    assert "create table if not exists search_intelligence_orchestrator_steps" in sql
    assert "write_audit_only" in sql
    assert "dry_run" in sql
    assert "on delete cascade" in sql


def test_gold_orchestrator_attention_views_migration_exists() -> None:
    migration = Path("db/migrations/041_create_gold_orchestrator_attention_views.sql")

    assert migration.exists()
    text = migration.read_text(encoding="utf-8")

    assert "create or replace view gold_search_intelligence_orchestrator_latest_run" in text
    assert "create or replace view gold_search_intelligence_orchestrator_attention_steps" in text
    assert "search_intelligence_orchestrator_runs" in text
    assert "search_intelligence_orchestrator_steps" in text
    assert "activate sources" in text.lower()
    assert "bronze" in text.lower()
