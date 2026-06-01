from __future__ import annotations

from pathlib import Path


def test_s6c_approval_gated_connector_build_migration_creates_request_table_and_fixes_s6a_constraints() -> None:
    sql = Path("db/migrations/037_create_approval_gated_connector_build_requests.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS employer_origin_connector_build_requests" in sql
    assert "REFERENCES employer_origin_source_candidates" in sql
    assert "gate_reassessment_required" in sql
    assert "rerun_employer_origin_gate_reassessment" in sql
    assert "build_approval_required" in sql
    assert "artifact_generation_allowed" in sql
    assert "bounded_investigation_connector" in sql
    assert "no connector registration approval" in sql
    assert "no source activation" in sql
    assert "no Bronze writes" in sql
    assert "no CSV/Excel/export artifact as pipeline input" in sql
