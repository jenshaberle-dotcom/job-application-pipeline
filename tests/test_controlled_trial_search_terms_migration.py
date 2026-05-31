from pathlib import Path


def test_controlled_trial_search_terms_migration_defines_guardrails() -> None:
    sql = Path("db/migrations/030_create_controlled_trial_search_terms.sql").read_text()
    assert "search_strategy_trial_terms" in sql
    assert "search_strategy_trial_outcomes" in sql
    assert "trial_expires_at" in sql
    assert "max_noise_rate" in sql
    assert "trial_status" in sql
