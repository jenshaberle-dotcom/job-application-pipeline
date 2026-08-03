from __future__ import annotations

from src.search_intelligence.origin_url_default_repair import (
    blocked_stage,
    compatibility_payload,
    evidence_stage,
    finalize_outcome,
    stage_from_discovery,
)


def discovery_payload(
    *,
    decision: str = "not_found",
    selected_url: str | None = None,
    confidence: float = 0.2,
) -> dict[str, object]:
    return {
        "company_key": "example",
        "company_name": "Example GmbH",
        "decision": decision,
        "selected_url": selected_url,
        "confidence_score": confidence,
        "candidate_count": 3,
        "reason": "fixture",
        "alternatives": [],
        "rejected": [],
        "search_results": [],
    }


def test_baseline_selection_short_circuits_repair() -> None:
    baseline = stage_from_discovery(
        "deterministic_baseline",
        discovery_payload(
            decision="origin_url_candidate_selected",
            selected_url="https://example.com/careers",
            confidence=0.9,
        ),
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=[baseline],
    )

    assert outcome.final_state == "selected_deterministic_baseline"
    assert outcome.selected_url == "https://example.com/careers"
    assert outcome.repair_exhausted is False


def test_tavily_selection_is_generic_second_stage() -> None:
    baseline = stage_from_discovery(
        "deterministic_baseline",
        discovery_payload(),
    )
    tavily = stage_from_discovery(
        "tavily_repair",
        discovery_payload(
            decision="origin_url_candidate_selected",
            selected_url="https://jobs.example.com",
            confidence=1.0,
        ),
        provider_request_count=4,
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=[baseline, tavily],
    )

    assert outcome.final_state == "selected_tavily_repair"
    assert outcome.selected_stage == "tavily_repair"
    assert outcome.stages[1].provider_request_count == 4


def test_full_failed_cascade_is_repair_exhausted() -> None:
    baseline = stage_from_discovery(
        "deterministic_baseline",
        discovery_payload(),
    )
    tavily = stage_from_discovery(
        "tavily_repair",
        discovery_payload(confidence=0.65),
        provider_request_count=4,
    )
    evidence = evidence_stage(
        {
            "deterministic_decision": "no_origin_candidate_selected",
            "selected_url": None,
            "confidence_score": 0.4,
            "manual_review_required": False,
            "assessments": [],
            "reason": "No candidate survived evidence grading.",
        },
        llm_attempted=False,
        llm_status=None,
        llm_recommended_url=None,
        llm_provider_request_count=0,
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=[baseline, tavily, evidence],
    )

    assert outcome.final_state == "repair_exhausted"
    assert outcome.repair_exhausted is True
    assert outcome.operator_review_required is True


def test_missing_provider_configuration_is_not_misreported_as_not_found() -> None:
    baseline = stage_from_discovery(
        "deterministic_baseline",
        discovery_payload(),
    )
    tavily = blocked_stage(
        "tavily_repair",
        "missing_tavily_api_key",
        "Tavily is mandatory after baseline not_found.",
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=[baseline, tavily],
    )

    assert outcome.final_state == "repair_configuration_blocked"
    assert outcome.configuration_blocked is True
    assert outcome.repair_exhausted is False


def test_failed_llm_request_is_an_explicit_repair_blocker() -> None:
    evidence = evidence_stage(
        {
            "deterministic_decision": "manual_review_required",
            "selected_url": None,
            "confidence_score": 0.7,
            "manual_review_required": True,
            "assessments": [{"candidate_id": "C1"}],
        },
        llm_attempted=True,
        llm_status="failed_closed",
        llm_recommended_url=None,
        llm_provider_request_count=1,
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=[evidence],
    )

    assert evidence.status == "configuration_blocked"
    assert evidence.blocker == "llm_provider_failed_closed"
    assert outcome.final_state == "repair_configuration_blocked"
    assert outcome.configuration_blocked is True


def test_llm_may_recommend_only_for_operator_review() -> None:
    baseline = stage_from_discovery(
        "deterministic_baseline",
        discovery_payload(),
    )
    tavily = stage_from_discovery(
        "tavily_repair",
        discovery_payload(confidence=0.65),
        provider_request_count=4,
    )
    evidence = evidence_stage(
        {
            "deterministic_decision": "manual_review_required",
            "selected_url": None,
            "confidence_score": 0.7,
            "manual_review_required": True,
            "assessments": [{"candidate_id": "C1"}],
        },
        llm_attempted=True,
        llm_status="completed",
        llm_recommended_url="https://jobs.example.com",
        llm_provider_request_count=1,
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=[baseline, tavily, evidence],
    )

    assert outcome.final_state == "operator_review_required"
    assert outcome.selected_url is None
    assert outcome.recommended_url == "https://jobs.example.com"
    assert outcome.operator_review_required is True


def test_compatibility_payload_exposes_repair_state_without_promoting_recommendation() -> None:
    evidence = evidence_stage(
        {
            "deterministic_decision": "manual_review_required",
            "selected_url": None,
            "confidence_score": 0.7,
            "manual_review_required": True,
            "assessments": [{"candidate_id": "C1"}],
        },
        llm_attempted=True,
        llm_status="completed",
        llm_recommended_url="https://jobs.example.com",
        llm_provider_request_count=1,
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=[evidence],
    )
    payload = compatibility_payload(
        outcome,
        last_discovery_payload=discovery_payload(confidence=0.65),
    )

    assert payload["decision"] == "manual_review_required"
    assert payload["selected_url"] is None
    assert payload["recommended_url"] == "https://jobs.example.com"
    assert payload["default_repair"]["boundary"]["llm_may_not_invent_or_persist_url"] is True
