from pathlib import Path


MIGRATION = Path("db/migrations/040_create_search_intelligence_orchestrator_runs.sql")


def test_nightly_orchestrator_migration_contains_audit_tables_and_guardrails() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists search_intelligence_orchestrator_runs" in sql
    assert "create table if not exists search_intelligence_orchestrator_steps" in sql
    assert "write_audit_only" in sql
    assert "dry_run" in sql
    assert "on delete cascade" in sql
