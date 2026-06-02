from pathlib import Path


MIGRATION = Path("db/migrations/039_create_origin_source_discovery_gate.sql")


def test_origin_source_discovery_migration_contains_review_table_and_gold_view() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS employer_origin_source_discovery_reviews" in sql
    assert "CREATE OR REPLACE VIEW gold_origin_source_discovery_status" in sql
    assert "selected_origin_url" in sql
    assert "blocked_unsafe_url" in sql
    assert "manual_review_required" in sql
