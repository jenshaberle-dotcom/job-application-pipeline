from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.record_employer_origin_gate_review import (
    DEFAULT_GATES,
    VALID_DECISIONS,
    VALID_GATE_NAMES,
    parse_json_object,
    validate_gate_update,
)


MIGRATION = Path("db/migrations/023_create_employer_origin_candidate_gate_state.sql")


def test_gate_model_migration_is_db_backed_and_not_export_backed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists employer_origin_source_candidates" in sql
    assert "create table if not exists employer_origin_candidate_gate_reviews" in sql
    assert "create table if not exists employer_origin_candidate_gate_events" in sql
    assert "evidence jsonb" in sql
    assert "on delete cascade" in sql

    lowered = sql.lower()
    for word in ["dictreader", "dictwriter", "removal_candidates_csv"]:
        assert word not in lowered


def test_default_gates_cover_documented_process_order() -> None:
    gate_names = [name for _, name, _ in DEFAULT_GATES]

    assert gate_names == [
        "company_candidate",
        "source_discovery",
        "risk_gate",
        "technical_reachability_gate",
        "scope_gate",
        "defensive_preview_gate",
        "relevance_gate",
        "detail_evidence_gate",
        "incremental_uniqueness_gate",
        "connector_candidate_gate",
        "controlled_activation_gate",
        "bronze_validation",
        "silver_validation",
        "source_lifecycle_tracking",
    ]


def test_gate_update_requires_stop_reason_for_blocking_outcomes() -> None:
    with pytest.raises(ValueError):
        validate_gate_update(
            gate_name="risk_gate",
            gate_status="failed",
            decision="abort_documented",
            stop_reason=None,
        )

    validate_gate_update(
        gate_name="risk_gate",
        gate_status="failed",
        decision="abort_documented",
        stop_reason="login-only source",
    )


def test_gate_update_rejects_unknown_gate_name() -> None:
    with pytest.raises(ValueError):
        validate_gate_update(
            gate_name="unknown_gate",
            gate_status="passed",
            decision="continue",
            stop_reason=None,
        )


def test_json_parser_accepts_only_json_objects() -> None:
    assert parse_json_object('{"status": "ok"}') == {"status": "ok"}
    assert parse_json_object(None) == {}
    assert parse_json_object("") == {}

    with pytest.raises(json.JSONDecodeError):
        parse_json_object("{bad json")

    with pytest.raises(Exception):
        parse_json_object("[1, 2, 3]")


def test_decision_vocabulary_contains_documented_stop_and_activation_outcomes() -> None:
    assert "abort_documented" in VALID_DECISIONS
    assert "activate_controlled" in VALID_DECISIONS
    assert "manual_review_required" in VALID_DECISIONS
    assert "ready_for_final_approval" in VALID_DECISIONS
    assert "approve_connector_registration" in VALID_DECISIONS
    assert "connector_validation_failed" in VALID_DECISIONS
    assert "risk_gate" in VALID_GATE_NAMES
