from pathlib import Path


def test_build_mode_migration_allows_s7o_queue_evidence_mode() -> None:
    text = Path("db/migrations/048_allow_build_queue_evidence_build_mode.sql").read_text(encoding="utf-8")

    assert "chk_employer_origin_connector_build_mode" in text
    assert "DROP CONSTRAINT IF EXISTS chk_employer_origin_connector_build_mode" in text
    assert "connector_candidate_from_build_queue_evidence" in text
    assert "connector_candidate_from_gate_evidence" in text
    assert "bounded_investigation_connector" in text
    assert "existing_artifacts" in text
    assert "NOT VALID" in text


def test_build_mode_migration_keeps_safe_boundary() -> None:
    text = Path("db/migrations/048_allow_build_queue_evidence_build_mode.sql").read_text(encoding="utf-8")

    assert "does not build connector" in text
    assert "register connectors" in text
    assert "activate sources" in text
    assert "write Bronze" in text
    assert "scheduler configuration" in text
