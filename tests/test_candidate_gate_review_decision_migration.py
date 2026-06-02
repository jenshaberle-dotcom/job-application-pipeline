from pathlib import Path


def test_ready_for_final_approval_gate_decision_is_allowed() -> None:
    text = Path("db/migrations/049_allow_ready_for_final_approval_gate_decision.sql").read_text(encoding="utf-8")

    assert "employer_origin_candidate_gate_reviews_decision_check" in text
    assert "DROP CONSTRAINT IF EXISTS employer_origin_candidate_gate_reviews_decision_check" in text
    assert "ready_for_final_approval" in text
    assert "NOT VALID" in text


def test_ready_for_final_approval_gate_decision_migration_keeps_safe_boundary() -> None:
    text = Path("db/migrations/049_allow_ready_for_final_approval_gate_decision.sql").read_text(encoding="utf-8")

    assert "does not register connectors" in text
    assert "activate sources" in text
    assert "write Bronze" in text
    assert "scheduler configuration" in text
