from pathlib import Path


def test_approve_connector_registration_gate_decision_is_allowed() -> None:
    text = Path("db/migrations/050_allow_approve_connector_registration_gate_decision.sql").read_text(encoding="utf-8")

    assert "employer_origin_candidate_gate_reviews_decision_check" in text
    assert "approve_connector_registration" in text
    assert "ready_for_final_approval" in text
    assert "NOT VALID" in text


def test_approve_connector_registration_gate_decision_migration_keeps_safe_boundary() -> None:
    text = Path("db/migrations/050_allow_approve_connector_registration_gate_decision.sql").read_text(encoding="utf-8")

    assert "does not register connectors" in text
    assert "activate sources" in text
    assert "write Bronze" in text
    assert "scheduler configuration" in text
