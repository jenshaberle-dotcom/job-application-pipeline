from __future__ import annotations

import json
from typing import Any

from scripts.run_employer_origin_connector_validation_agent import (
    SourceCandidate,
    ValidationRepository,
    ValidationResult,
    evaluate_connector_validation,
)


class RecordingCursor:
    def __init__(self, executions: list[tuple[str, tuple[object, ...]]]) -> None:
        self.executions = executions

    def __enter__(self) -> RecordingCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.executions.append((query, params))


class RecordingConnection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    def cursor(self, *_args: Any, **_kwargs: Any) -> RecordingCursor:
        return RecordingCursor(self.executions)


def candidate(company_key: str = "missing") -> SourceCandidate:
    return SourceCandidate(
        id=1,
        company_key=company_key,
        company_name="Missing AG",
        source_name_candidate=f"{company_key}:hannover",
        source_family_candidate=company_key,
        source_type_candidate="employer_origin_career_site",
        status="connector_candidate",
    )


def test_validation_fails_when_connector_module_is_missing() -> None:
    result = evaluate_connector_validation(candidate(), run_pytest=False)

    assert result.gate_status == "manual_review_required"
    assert result.decision == "connector_validation_failed"
    assert result.stop_reason == "connector module is missing"
    assert result.evidence["boundary"]["bronze_persistence"] is False
    assert result.evidence["agent"] == "s4b_connector_validation_agent"
    assert result.evidence["expected_files"]["bounded_preview"]["attempted"] is False


def test_validation_is_not_applicable_for_active_controlled_source() -> None:
    active = SourceCandidate(
        id=1,
        company_key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        source_name_candidate="finanz_informatik:hannover",
        source_family_candidate="finanz_informatik",
        source_type_candidate="employer_origin_career_site",
        status="active_controlled",
    )

    result = evaluate_connector_validation(active, run_pytest=False)

    assert result.gate_status == "not_applicable"
    assert result.decision == "monitor_existing_source"
    assert result.stop_reason == "candidate is already active_controlled"


def test_validation_records_s4b_agent_name_for_active_controlled_source() -> None:
    active = SourceCandidate(
        id=1,
        company_key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        source_name_candidate="finanz_informatik:hannover",
        source_family_candidate="finanz_informatik",
        source_type_candidate="employer_origin_career_site",
        status="active_controlled",
    )

    result = evaluate_connector_validation(active, run_pytest=False)

    assert result.evidence["agent"] == "s4b_connector_validation_agent"


def test_validation_gate_persistence_binds_official_order_and_name() -> None:
    connection = RecordingConnection()
    repository = ValidationRepository(connection)  # type: ignore[arg-type]
    result = ValidationResult(
        gate_status="passed",
        decision="ready_for_final_approval",
        stop_reason=None,
        evidence={"agent": "s4b_connector_validation_agent"},
    )

    repository.record_gate(
        candidate_id=57,
        result=result,
        reviewed_by="connector_autonomy_a1",
    )

    assert len(connection.executions) == 1
    _query, params = connection.executions[0]
    assert len(params) == 8
    assert params[0] == 57
    assert params[1] == 11
    assert params[2] == "connector_validation_gate"
    assert params[3] == "passed"
    assert params[4] == "ready_for_final_approval"
    assert params[5] is None
    assert json.loads(str(params[6])) == {
        "agent": "s4b_connector_validation_agent"
    }
    assert params[7] == "connector_autonomy_a1"
