from __future__ import annotations

from scripts.run_employer_origin_connector_validation_agent import (
    SourceCandidate,
    evaluate_connector_validation,
)


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
