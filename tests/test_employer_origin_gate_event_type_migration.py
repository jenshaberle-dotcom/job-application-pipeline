from __future__ import annotations

from pathlib import Path


MIGRATION = Path("db/migrations/062_extend_employer_origin_gate_event_types_for_source_url_recovery.sql")


def test_source_url_recovery_event_type_is_allowed_by_migration() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "employer_origin_candidate_gate_events_event_type_check" in sql
    assert "candidate_url_recovered" in sql
    assert "candidate_created" in sql
    assert "gate_initialized" in sql
    assert "gate_updated" in sql
    assert "candidate_status_updated" in sql
