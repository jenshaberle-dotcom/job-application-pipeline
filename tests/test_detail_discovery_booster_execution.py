from __future__ import annotations

from src.search_intelligence.detail_discovery_booster_execution import (
    DetailCandidateValidationObservation,
    DetailDiscoveryHypothesisObservation,
    execute_detail_discovery_booster,
)
from src.search_intelligence.detail_discovery_gap import analyze_detail_discovery_gap
from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState

ORIGIN = "https://jobs.example.com/"
DETAIL_A = "https://jobs.example.com/jobs/123-data-engineer"
DETAIL_B = "https://jobs.example.com/jobs/456-platform-engineer"


def d0_evidence(
    *,
    candidates: tuple[str, ...] = (),
    supported: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "repair_attempted": True,
        "search_discovery_enabled": False,
        "detail_link_discovery_version": "DETAIL-004B",
        "detail_url_shape_version": "test-v1",
        "decision_taxonomy": "accepted" if supported else "manual_review_required",
        "preliminary_detail_candidates": [{"url": url} for url in candidates],
        "authoritative_detail_assessments": [
            {
                "url": url,
                "decision": "manual_review_required",
                "failure_reason": "detail_page_extracted_but_no_target_signal",
            }
            for url in candidates
        ],
        "supported_detail_evidence": [
            {"url": url, "final_url": url, "status_code": 200}
            for url in supported
        ],
        "checked_origin_candidates": [
            {
                "url": ORIGIN,
                "final_url": ORIGIN,
                "status": (
                    "job_detail_candidates_found"
                    if candidates or supported
                    else "checked_no_detail_candidates"
                ),
                "status_code": 200,
                "rejection_reasons": [],
            }
        ],
    }


def decision(
    *,
    candidates: tuple[str, ...] = (),
    supported: tuple[str, ...] = (),
    tavily_state: TavilyState = TavilyState.AVAILABLE,
    previous_gap_fingerprint: str | None = None,
):
    return analyze_detail_discovery_gap(
        candidate_id=42,
        company_key="example",
        candidate_url=ORIGIN,
        deterministic_evidence=d0_evidence(candidates=candidates, supported=supported),
        tavily_state=tavily_state,
        previous_gap_fingerprint=previous_gap_fingerprint,
    )


def validation(url: str, *, accepted: bool) -> DetailCandidateValidationObservation:
    return DetailCandidateValidationObservation(
        candidate_url=url,
        accepted=accepted,
        final_url=url if accepted else None,
        classification="accepted" if accepted else "rejected",
        failure_reason=None if accepted else "not_concrete_or_unsupported_detail",
        evidence={"deterministic_validator": "existing_detail_contract"},
    )


def no_model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
    raise AssertionError(f"model must not run: {stage}")


def test_d0_resolved_calls_nothing() -> None:
    search_calls: list[str] = []
    validate_calls: list[str] = []

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(candidates=(DETAIL_A,), supported=(DETAIL_A,)),
        max_tavily_requests=1,
        search=lambda query: search_calls.append(query) or (),
        validate=lambda url: validate_calls.append(url) or validation(url, accepted=True),
        model=no_model,
        seed_urls=(DETAIL_A,),
    )

    assert search_calls == []
    assert validate_calls == []
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert all(not item.attempted for item in result.stages[1:])


def test_tavily_candidate_must_pass_deterministic_validation_before_resolving() -> None:
    model_calls: list[BoosterStage] = []

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(DETAIL_B,),
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(),
        max_tavily_requests=1,
        search=lambda query: (DETAIL_A,),
        validate=lambda url: validation(url, accepted=url == DETAIL_A),
        model=model,
    )

    assert result.resolved is True
    assert result.resolved_url == DETAIL_A
    assert model_calls == []
    assert result.provider_requests == 1
    assert result.llm_requests == 0
    assert result.resolved_validation is not None
    assert result.resolved_validation["product_authority"] is False


def test_rejected_tavily_candidate_continues_to_luna() -> None:
    model_calls: list[BoosterStage] = []

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(DETAIL_B,),
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(),
        max_tavily_requests=1,
        search=lambda query: (DETAIL_A,),
        validate=lambda url: validation(url, accepted=url == DETAIL_B),
        model=model,
    )

    assert result.resolved_url == DETAIL_B
    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    assert result.provider_requests == 2
    assert result.llm_requests == 1


def test_tavily_disabled_starts_with_luna() -> None:
    model_calls: list[BoosterStage] = []
    search_calls: list[str] = []

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(DETAIL_A,),
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(tavily_state=TavilyState.DISABLED),
        max_tavily_requests=1,
        search=lambda query: search_calls.append(query) or (),
        validate=lambda url: validation(url, accepted=True),
        model=model,
    )

    assert search_calls == []
    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    assert result.resolved_url == DETAIL_A


def test_candidate_validation_gap_skips_search_and_starts_models() -> None:
    search_calls: list[str] = []
    model_calls: list[BoosterStage] = []

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(DETAIL_B,),
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(candidates=(DETAIL_A,)),
        max_tavily_requests=1,
        search=lambda query: search_calls.append(query) or (),
        validate=lambda url: validation(url, accepted=url == DETAIL_B),
        model=model,
        seed_urls=(DETAIL_A,),
    )

    assert search_calls == []
    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    assert result.resolved_url == DETAIL_B


def test_duplicate_url_across_provider_and_model_is_validated_once() -> None:
    validate_calls: list[str] = []
    model_calls: list[BoosterStage] = []

    def validate(url: str) -> DetailCandidateValidationObservation:
        validate_calls.append(url)
        return validation(url, accepted=False)

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        urls = (DETAIL_A,) if stage == BoosterStage.LUNA_MEDIUM else ()
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=urls,
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(),
        max_tavily_requests=1,
        search=lambda query: (DETAIL_A,),
        validate=validate,
        model=model,
    )

    assert validate_calls == [DETAIL_A]
    assert model_calls == [
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
    ]
    assert result.resolved is False


def test_first_model_success_stops_later_models() -> None:
    model_calls: list[BoosterStage] = []

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(DETAIL_A,),
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(tavily_state=TavilyState.BUDGET_EXHAUSTED),
        max_tavily_requests=0,
        search=lambda query: (),
        validate=lambda url: validation(url, accepted=True),
        model=model,
    )

    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    assert result.resolved_url == DETAIL_A
    later = [item for item in result.stages if item.stage in {
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    }]
    assert all(item.attempted is False for item in later)


def test_unchanged_gap_calls_nothing() -> None:
    initial = decision()
    unchanged = decision(previous_gap_fingerprint=initial.evidence_fingerprint)
    search_calls: list[str] = []
    validate_calls: list[str] = []

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=unchanged,
        max_tavily_requests=1,
        search=lambda query: search_calls.append(query) or (DETAIL_A,),
        validate=lambda url: validate_calls.append(url) or validation(url, accepted=True),
        model=no_model,
    )

    assert search_calls == []
    assert validate_calls == []
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert result.unchanged_gap_skip is True


def test_attractive_model_url_cannot_resolve_when_validator_rejects_it() -> None:
    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(DETAIL_A,),
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(tavily_state=TavilyState.DISABLED),
        max_tavily_requests=0,
        search=lambda query: (),
        validate=lambda url: validation(url, accepted=False),
        model=model,
    )

    assert result.resolved is False
    assert any(
        item.get("candidate_url") == DETAIL_A and item.get("accepted") is False
        for item in result.candidate_evidence
    )
    assert result.product_authority is False
    assert result.product_writes == 0


def test_stage_order_has_no_pro_stage() -> None:
    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        return DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(),
        )

    result = execute_detail_discovery_booster(
        company_name="Example GmbH",
        candidate_url=ORIGIN,
        decision=decision(tavily_state=TavilyState.DISABLED),
        max_tavily_requests=0,
        search=lambda query: (),
        validate=lambda url: validation(url, accepted=False),
        model=model,
    )

    assert [item.stage for item in result.stages] == [
        BoosterStage.DETERMINISTIC,
        BoosterStage.TAVILY,
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    ]
    assert all("pro" not in item.stage.value for item in result.stages)
