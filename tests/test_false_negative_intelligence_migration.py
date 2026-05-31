from pathlib import Path


def test_false_negative_intelligence_migration_contains_market_evidence_model() -> None:
    sql = Path("db/migrations/026_create_false_negative_intelligence_foundation.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS market_evidence" in sql
    assert "candidate_market_evidence_summary" in sql
    assert "false_negative_risk_snapshots" in sql
    assert "not a Bronze job record" in sql
