from pathlib import Path


def test_candidate_promotion_migration_exists_and_defines_review_tables() -> None:
    migration = Path("db/migrations/043_create_candidate_promotion_reviews.sql")

    assert migration.exists()
    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS candidate_promotion_reviews" in sql
    assert "CREATE TABLE IF NOT EXISTS candidate_promotion_review_items" in sql
    assert "ALTER COLUMN candidate_url DROP NOT NULL" in sql
    assert "idx_employer_origin_candidates_pending_company" in sql
    assert "candidate_expansion_review_items" in sql
    assert "employer_origin_source_candidates" in sql
    assert "promotion_recommended" in sql
    assert "promotion_manual_review_required" in sql
