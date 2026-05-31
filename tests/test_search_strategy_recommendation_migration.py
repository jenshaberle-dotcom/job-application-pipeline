from pathlib import Path


def test_search_strategy_recommendation_migration_defines_guardrail_state() -> None:
    sql = Path('db/migrations/029_create_search_strategy_recommendations.sql').read_text(encoding='utf-8')
    assert 'search_strategy_recommendations' in sql
    assert 'guardrail_decision' in sql
    assert 'autonomy_level' in sql
    assert 'recommendation_status' in sql
