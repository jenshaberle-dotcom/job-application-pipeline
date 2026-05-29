from __future__ import annotations

from pathlib import Path


MIGRATION = Path("db/migrations/024_extend_employer_origin_gate_decisions_for_s4.sql")


def test_s4_gate_vocabulary_migration_extends_db_constraints_for_validation_and_approval() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "drop constraint if exists employer_origin_candidate_gate_reviews_gate_status_check" in sql
    assert "drop constraint if exists employer_origin_candidate_gate_reviews_decision_check" in sql
    assert "not_applicable" in sql
    assert "ready_for_final_approval" in sql
    assert "approve_connector_registration" in sql
    assert "connector_validation_failed" in sql
    assert "bronze" in sql.lower()
    assert "activate sources" in sql.lower()
