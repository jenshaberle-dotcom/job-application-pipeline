from pathlib import Path


def test_origin_url_repair_migration_creates_review_table_and_history_view() -> None:
    text = Path("db/migrations/046_create_origin_url_repair_reviews.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS employer_origin_url_repair_reviews" in text
    assert "CREATE OR REPLACE VIEW gold_origin_url_repair_review_history" in text
    assert "repair_applied" in text
    assert "manual_review_required" in text
    assert "no_connector_artifact_generation" in text
