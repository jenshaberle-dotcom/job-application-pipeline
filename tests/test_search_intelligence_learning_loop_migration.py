from pathlib import Path


def test_learning_loop_migration_defines_validation_and_confidence_tables() -> None:
    sql = Path('db/migrations/028_create_search_intelligence_learning_loop.sql').read_text(encoding='utf-8')
    assert 'search_term_validation_runs' in sql
    assert 'search_term_confidence_snapshots' in sql
    assert 'tested_found_relevant' in sql
    assert 'no automatic search-profile mutation' in sql
