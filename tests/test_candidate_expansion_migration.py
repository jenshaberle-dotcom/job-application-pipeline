from pathlib import Path


def test_candidate_expansion_migration_defines_review_tables_and_boundaries() -> None:
    sql = Path("db/migrations/042_create_candidate_expansion_reviews.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS candidate_expansion_reviews" in sql
    assert "CREATE TABLE IF NOT EXISTS candidate_expansion_review_items" in sql
    assert "create_candidate_recommended" in sql
    assert "manual_review_required" in sql
    assert "candidate_creation_allowed" not in sql
    assert "no automatic candidate creation" in sql.lower()
