from pathlib import Path


def test_search_term_value_migration_creates_expected_tables() -> None:
    sql = Path("db/migrations/033_create_search_term_value_foundation.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS vocabulary_signal_scores" in sql
    assert "CREATE TABLE IF NOT EXISTS search_term_value_scores" in sql
    assert "UNIQUE (observed_term)" in sql
    assert "UNIQUE (observed_term, profile_name, profile_version)" in sql
    assert "no search-profile mutation" in sql
