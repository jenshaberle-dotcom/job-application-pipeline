
from pathlib import Path


def test_company_vocabulary_migration_contains_table_and_guardrails() -> None:
    sql = Path("db/migrations/031_create_company_vocabulary_observations.sql").read_text(encoding="utf-8")
    assert "company_vocabulary_observations" in sql
    assert "UNIQUE (company_key, observed_term, source_name, evidence_type)" in sql
    assert "not Bronze jobs" in sql
