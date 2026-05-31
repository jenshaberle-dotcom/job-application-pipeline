from pathlib import Path


def test_search_term_learning_migration_creates_review_state_tables() -> None:
    sql = Path("db/migrations/027_create_search_term_learning_reassessment.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS search_term_suggestions" in sql
    assert "CREATE TABLE IF NOT EXISTS candidate_reassessment_queue" in sql
    assert "UNIQUE (candidate_id, suggested_term)" in sql
    assert "WHERE status = 'open'" in sql
    assert "no automatic search-profile mutation" in sql
