import json
from typing import Mapping

from src.search_intelligence.origin_llm_model_campaign import (
    BenchmarkExpectation,
    adjudicate_model,
    adjudicate_with_escalation,
    build_request_payload,
    recommend_route,
    score_observation,
    summarize_models,
)
from src.search_intelligence.origin_source_evidence import (
    OriginEvidenceAssessment,
    OriginEvidenceDecision,
)


def _assessment(
    candidate_id: str,
    *,
    url: str,
    source_grade: str = "company_job_listing",
    entity_fidelity: str = "exact_legal_entity",
    locale: str = "de",
    completeness: float = 0.9,
    ranking: float = 0.9,
) -> OriginEvidenceAssessment:
    return OriginEvidenceAssessment(
        candidate_id=candidate_id,
        url=url,
        final_url=url,
        provider="tavily",
        source_grade=source_grade,
        entity_fidelity=entity_fidelity,
        job_inventory_state="job_bearing_proven",
        page_type="job_listing",
        ats_family=None,
        http_status=200,
        reachable=True,
        locale=locale,
        observed_job_count=3,
        target_signal_job_count=1,
        sample_job_urls=(f"{url}/job/1",),
        identity_score=0.9,
        source_grade_score=0.94,
        entity_fidelity_score=1.0,
        job_bearing_score=1.0,
        locale_preference_score=1.0 if locale == "de" else 0.4,
        target_relevance_score=0.7,
        evidence_completeness=completeness,
        ranking_score=ranking,
        reasons=("fixture",),
        failure_class=None,
    )


def _decision(*, ambiguous: bool = False) -> OriginEvidenceDecision:
    assessments = (
        _assessment(
            "C1",
            url="https://jobs.example.de/careers",
            entity_fidelity="ambiguous" if ambiguous else "exact_legal_entity",
            ranking=0.82,
        ),
        _assessment(
            "C2",
            url="https://jobs.example.de/stellenangebote",
            entity_fidelity="brand_match",
            ranking=0.78,
        ),
    )
    return OriginEvidenceDecision(
        company_key="example_ag",
        company_name="Example AG",
        deterministic_decision=(
            "manual_review_required" if ambiguous else "origin_url_candidate_selected"
        ),
        selected_candidate_id=None if ambiguous else "C1",
        selected_url=None if ambiguous else assessments[0].final_url,
        confidence_score=0.72,
        confidence_band="medium",
        selection_margin=0.18,
        manual_review_required=ambiguous,
        adjudication_reasons=("entity_ambiguity",) if ambiguous else (),
        assessments=assessments,
    )


def _response(
    *,
    model: str,
    decision: str,
    candidate_id: str | None,
    manual: bool,
) -> Mapping[str, object]:
    payload = {
        "decision": decision,
        "recommended_candidate_id": candidate_id,
        "entity_relationship": "ambiguous" if manual else "exact_legal_entity",
        "origin_assessment": "verified_job_listing",
        "manual_review_required": manual,
        "evidence_references": [candidate_id] if candidate_id else ["C1"],
        "remaining_uncertainty": ["entity relationship"] if manual else [],
        "rationale": "Fixture response.",
    }
    return {
        "id": f"resp_{model}",
        "model": model,
        "usage": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        "output_text": json.dumps(payload),
    }


def test_same_task_contract_across_all_three_models() -> None:
    decision = _decision()
    contract_hashes = set()
    packet_hashes = set()
    for model in ("gpt-5.4-mini", "gpt-5.6-terra", "gpt-5.5"):
        payload, packet_hash, contract_hash = build_request_payload(
            decision,
            model=model,
            reasoning_effort="low",
            max_output_tokens=600,
        )
        packet_hashes.add(packet_hash)
        contract_hashes.add(contract_hash)
        assert payload["model"] == model
        assert payload["store"] is False
        assert payload["reasoning"] == {"effort": "low"}
        assert payload["text"]["verbosity"] == "low"
        assert payload["max_output_tokens"] == 600
    assert len(packet_hashes) == 1
    assert len(contract_hashes) == 1


def test_equal_quality_selects_cheapest_primary() -> None:
    decision = _decision()
    expectation = BenchmarkExpectation(
        case_id="example",
        company_name_contains="example",
        expected_manual_review=False,
        acceptable_url_contains=("example.de",),
        acceptable_source_grades=("company_job_listing",),
        expected_locale="de",
    )
    observations = []
    scores = []

    def transport(_url, _headers, payload, _timeout):
        model = str(payload["model"])
        return _response(
            model=model,
            decision="confirm_deterministic",
            candidate_id="C1",
            manual=False,
        )

    for model in ("gpt-5.4-mini", "gpt-5.6-terra", "gpt-5.5"):
        observation = adjudicate_model(
            decision,
            api_key="secret",
            model=model,
            max_output_tokens=600,
            transport=transport,
        )
        observations.append(observation)
        scores.append(score_observation(decision, observation, expectation))

    summaries = summarize_models(
        observations,
        scores,
        model_order=("gpt-5.4-mini", "gpt-5.6-terra", "gpt-5.5"),
    )
    recommendation = recommend_route(summaries, {})
    assert recommendation["primary_model"] == "gpt-5.4-mini"
    assert recommendation["escalation_value_proven"] is False


def test_better_model_lift_is_required_before_escalation_recommendation() -> None:
    from src.search_intelligence.origin_llm_model_campaign import EscalationSimulation

    summaries = [
        {
            "model": "gpt-5.4-mini",
            "case_count": 6,
            "mean_quality_score": 0.90,
            "critical_failure_count": 1,
            "estimated_cost_usd": 0.04,
        },
        {
            "model": "gpt-5.6-terra",
            "case_count": 6,
            "mean_quality_score": 0.90,
            "critical_failure_count": 1,
            "estimated_cost_usd": 0.13,
        },
        {
            "model": "gpt-5.5",
            "case_count": 6,
            "mean_quality_score": 1.00,
            "critical_failure_count": 0,
            "estimated_cost_usd": 0.26,
        },
    ]
    no_trigger = EscalationSimulation(
        company_key="easy",
        trigger_reason=None,
        primary_model="gpt-5.4-mini",
        escalation_model="gpt-5.5",
        primary_score=1.0,
        escalation_score=1.0,
        score_lift=0.0,
        corrected=False,
        outcome="not_triggered",
    )
    corrected = EscalationSimulation(
        company_key="hard",
        trigger_reason="provider_attempts_to_clear_deterministic_manual_review",
        primary_model="gpt-5.4-mini",
        escalation_model="gpt-5.5",
        primary_score=0.4,
        escalation_score=1.0,
        score_lift=0.6,
        corrected=True,
        outcome="escalation_improved_quality",
    )
    not_corrected = EscalationSimulation(
        company_key="hard",
        trigger_reason="provider_attempts_to_clear_deterministic_manual_review",
        primary_model="gpt-5.4-mini",
        escalation_model="gpt-5.6-terra",
        primary_score=0.4,
        escalation_score=0.4,
        score_lift=0.0,
        corrected=False,
        outcome="provider_consensus",
    )
    simulations = {
        "gpt-5.4-mini->gpt-5.6-terra": [not_corrected] + [no_trigger] * 5,
        "gpt-5.4-mini->gpt-5.5": [corrected] + [no_trigger] * 5,
    }

    recommendation = recommend_route(summaries, simulations)
    assert recommendation["primary_model"] == "gpt-5.4-mini"
    assert recommendation["escalation_model"] == "gpt-5.5"
    assert recommendation["escalation_value_proven"] is True
    assert recommendation["corrected_case_count"] == 1


def test_live_escalation_runs_at_most_one_second_attempt() -> None:
    decision = _decision(ambiguous=True)
    calls = []

    def transport(_url, _headers, payload, _timeout):
        model = str(payload["model"])
        calls.append(model)
        if model == "gpt-5.4-mini":
            return _response(
                model=model,
                decision="prefer_alternative",
                candidate_id="C1",
                manual=False,
            )
        return _response(
            model=model,
            decision="manual_review_required",
            candidate_id="C1",
            manual=True,
        )

    run = adjudicate_with_escalation(
        decision,
        api_key="secret",
        primary_model="gpt-5.4-mini",
        escalation_model="gpt-5.5",
        max_output_tokens=600,
        transport=transport,
    )

    assert calls == ["gpt-5.4-mini", "gpt-5.5"]
    assert run.trigger_reason == "provider_attempts_to_clear_deterministic_manual_review"
    assert run.outcome == "provider_disagreement_manual_review_required"
    assert run.escalation is not None


def test_failed_closed_preserves_provider_metadata_and_candidate_stage() -> None:
    payload = {
        "decision": "confirm_deterministic",
        "recommended_candidate_id": "C1",
        "entity_relationship": "exact_legal_entity",
        "origin_assessment": "verified_job_listing",
        "manual_review_required": False,
        "evidence_references": ["not-a-candidate-id"],
        "remaining_uncertainty": [],
        "rationale": "Fixture with an invalid evidence reference.",
    }

    def transport(_url, _headers, _request, _timeout):
        return {
            "id": "resp_diagnostic",
            "model": "gpt-5.4-mini-2026-07-01",
            "status": "completed",
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 100,
                "total_tokens": 1100,
            },
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(payload)}
                    ],
                }
            ],
        }

    observation = adjudicate_model(
        _decision(),
        api_key="secret",
        model="gpt-5.4-mini",
        transport=transport,
    )

    result = observation.result
    assert result.status == "failed_closed"
    assert result.failure_stage == "candidate_validation"
    assert result.failure_class == "AdjudicationValidationError"
    assert result.failure_message == "provider cited an unknown candidate ID"
    assert result.response_id == "resp_diagnostic"
    assert result.provider_status == "completed"
    assert result.usage == {
        "input_tokens": 1000,
        "output_tokens": 100,
        "total_tokens": 1100,
    }
    assert result.output_item_types == ("message",)
    assert result.output_text_length is not None
    assert result.output_text_length > 0
    assert result.raw_output_sha256 is not None
    assert observation.model_returned == "gpt-5.4-mini-2026-07-01"
    assert observation.estimated_cost_usd > 0


def test_incomplete_response_preserves_provider_diagnostics() -> None:
    def transport(_url, _headers, _request, _timeout):
        return {
            "id": "resp_incomplete",
            "model": "gpt-5.4-mini",
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 600,
                "total_tokens": 1600,
            },
            "output": [{"type": "reasoning", "content": []}],
        }

    observation = adjudicate_model(
        _decision(),
        api_key="secret",
        model="gpt-5.4-mini",
        transport=transport,
    )

    result = observation.result
    assert result.status == "failed_closed"
    assert result.failure_stage == "output_extraction"
    assert result.failure_message == "response contains no output_text"
    assert result.response_id == "resp_incomplete"
    assert result.provider_status == "incomplete"
    assert result.incomplete_details == {"reason": "max_output_tokens"}
    assert result.output_item_types == ("reasoning",)
    assert result.output_text_length is None
    assert result.raw_output_sha256 is None
    assert observation.estimated_cost_usd > 0
