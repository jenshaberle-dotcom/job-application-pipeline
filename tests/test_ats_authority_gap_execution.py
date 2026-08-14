from __future__ import annotations

from collections.abc import Sequence

from src.search_intelligence.ats_authority_gap import (
    ATSAuthorityAttemptOutcome,
    analyze_ats_authority_gap,
    build_ats_authority_attempt_observation,
)
from src.search_intelligence.ats_authority_gap_execution import (
    ATSAuthorityHypothesisObservation,
    execute_ats_authority_gap_booster,
)
from src.search_intelligence.ats_delegation_evidence import analyze_ats_delegation
from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState


PERSONIO = "https://bridgingit.jobs.personio.de/"
PERSONIO_XML = "https://bridgingit.jobs.personio.de/xml"


def decision(tavily_state: TavilyState = TavilyState.AVAILABLE):  # type: ignore[no-untyped-def]
    evidence = analyze_ats_delegation(
        candidate_urls=(PERSONIO,),
        employer_backed_urls=(PERSONIO,),
    )
    attempt = build_ats_authority_attempt_observation(
        provider="personio",
        employer_identity="BridgingIT GmbH",
        target_url=PERSONIO,
        evidence_url=PERSONIO_XML,
        validation_contract="personio_target_authority.v1",
        outcome=ATSAuthorityAttemptOutcome.HTTP_RATE_LIMITED,
        http_status=429,
        final_url="https://www.personio.com/",
    )
    return analyze_ats_authority_gap(
        delegation_evidence=evidence,
        tavily_state=tavily_state,
        authority_attempt=attempt,
    )


def observation(
    stage: BoosterStage,
    urls: Sequence[str] = (),
    *,
    status: str = "completed",
    attempted: bool = True,
) -> ATSAuthorityHypothesisObservation:
    return ATSAuthorityHypothesisObservation(
        status=status,
        request_attempted=attempted,
        urls=tuple(urls),
        model=stage.value,
        response_id="resp_test" if attempted else None,
        estimated_cost_usd=0.001 if attempted else 0.0,
        rationale="bounded candidate hypothesis",
    )


def test_unchanged_gap_spends_zero_provider_requests() -> None:
    first = decision()
    evidence = analyze_ats_delegation(
        candidate_urls=(PERSONIO,),
        employer_backed_urls=(PERSONIO,),
    )
    attempt = build_ats_authority_attempt_observation(
        provider="personio",
        employer_identity="BridgingIT GmbH",
        target_url=PERSONIO,
        evidence_url=PERSONIO_XML,
        validation_contract="personio_target_authority.v1",
        outcome=ATSAuthorityAttemptOutcome.HTTP_RATE_LIMITED,
        http_status=429,
        final_url="https://www.personio.com/",
    )
    unchanged = analyze_ats_authority_gap(
        delegation_evidence=evidence,
        tavily_state=TavilyState.AVAILABLE,
        authority_attempt=attempt,
        previous_gap_fingerprint=first.evidence_fingerprint,
    )

    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("unchanged ATS gap must not spend")

    result = execute_ats_authority_gap_booster(
        company_name="BridgingIT GmbH",
        decision=unchanged,
        expected_provider="personio",
        max_tavily_requests=1,
        search=forbidden,
        model=forbidden,
        blocked_candidate_urls=(PERSONIO_XML,),
    )
    assert result.unchanged_gap_skip is True
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert result.product_writes == 0
    assert result.product_authority is False
    assert all(not stage.attempted for stage in result.stages[1:])


def test_tavily_candidate_stops_models_but_never_grants_authority() -> None:
    alternate = "https://bridgingit.jobs.personio.de/job/123"
    model_calls: list[BoosterStage] = []

    def search(query: str) -> Sequence[str]:
        return [PERSONIO_XML, alternate]

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return observation(stage)

    result = execute_ats_authority_gap_booster(
        company_name="BridgingIT GmbH",
        decision=decision(),
        expected_provider="personio",
        max_tavily_requests=1,
        search=search,
        model=model,
        blocked_candidate_urls=(PERSONIO_XML,),
    )
    assert result.selected_candidate_url == alternate
    assert result.provider_requests == 1
    assert result.llm_requests == 0
    assert model_calls == []
    assert result.candidate_evidence[0].provider == "personio"
    assert result.candidate_evidence[0].deterministic_validation_required is True
    assert result.candidate_evidence[0].tenant_authority is False
    assert result.candidate_evidence[0].delegation_permitted is False
    assert result.tenant_authority is False
    assert result.delegation_permitted is False
    assert result.product_authority is False
    assert all(not stage.attempted for stage in result.stages[2:])


def test_wrong_provider_candidate_is_rejected_and_luna_can_supply_personio() -> None:
    personio_candidate = "https://bridgingit.jobs.personio.de/jobs/42"
    calls: list[BoosterStage] = []

    def search(query: str) -> Sequence[str]:
        return ["https://boards.greenhouse.io/bridgingit"]

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        calls.append(stage)
        return observation(stage, [personio_candidate])

    result = execute_ats_authority_gap_booster(
        company_name="BridgingIT GmbH",
        decision=decision(),
        expected_provider="personio",
        max_tavily_requests=1,
        search=search,
        model=model,
        blocked_candidate_urls=(PERSONIO_XML,),
    )
    assert calls == [BoosterStage.LUNA_MEDIUM]
    assert result.selected_candidate_url == personio_candidate
    assert result.provider_requests == 2
    assert result.llm_requests == 1
    assert result.candidate_evidence[0].provider == "personio"
    assert result.product_authority is False


def test_insufficient_tavily_budget_skips_search_but_not_luna() -> None:
    candidate = "https://bridgingit.jobs.personio.de/jobs/99"
    calls: list[BoosterStage] = []

    def forbidden_search(query: str):  # type: ignore[no-untyped-def]
        raise AssertionError(f"Tavily must not run: {query}")

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        calls.append(stage)
        return observation(stage, [candidate])

    result = execute_ats_authority_gap_booster(
        company_name="BridgingIT GmbH",
        decision=decision(TavilyState.INSUFFICIENT_BUDGET),
        expected_provider="personio",
        max_tavily_requests=0,
        search=forbidden_search,
        model=model,
        blocked_candidate_urls=(PERSONIO_XML,),
    )
    assert calls == [BoosterStage.LUNA_MEDIUM]
    assert result.selected_candidate_url == candidate
    assert result.provider_requests == 1
    assert result.llm_requests == 1
    assert result.stages[1].attempted is False


def test_same_candidate_is_not_reconsumed_across_model_stages() -> None:
    unknown = "https://jobs.example.test/not-an-ats"
    observed: list[tuple[BoosterStage, tuple[str, ...]]] = []

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        observed.append((stage, tuple(sorted(ledger.attempted_urls))))
        return observation(stage, [unknown])

    result = execute_ats_authority_gap_booster(
        company_name="BridgingIT GmbH",
        decision=decision(TavilyState.DISABLED),
        expected_provider="personio",
        max_tavily_requests=0,
        search=lambda query: (),
        model=model,
        blocked_candidate_urls=(PERSONIO_XML,),
    )
    assert result.candidate_found is False
    assert result.llm_requests == 4
    assert len(observed) == 4
    assert unknown in observed[1][1]
    assert result.stages[-1].stage == BoosterStage.DEEP_EVIDENCE
    assert result.product_authority is False


def test_http_and_tracking_variants_of_blocked_url_do_not_reopen_exact_candidate() -> None:
    selected = "https://bridgingit.jobs.personio.de/jobs?id=42"

    def search(query: str) -> Sequence[str]:
        return [
            PERSONIO_XML + "?utm_source=tavily",
            selected + "&utm_source=tavily",
        ]

    result = execute_ats_authority_gap_booster(
        company_name="BridgingIT GmbH",
        decision=decision(),
        expected_provider="personio",
        max_tavily_requests=1,
        search=search,
        model=lambda stage, summaries, ledger: observation(stage),
        blocked_candidate_urls=(PERSONIO_XML,),
    )
    assert result.selected_candidate_url == selected
    assert PERSONIO_XML not in result.stages[1].proposed_urls


def test_stage_order_remains_canonical_and_contains_no_pro() -> None:
    result = execute_ats_authority_gap_booster(
        company_name="BridgingIT GmbH",
        decision=decision(TavilyState.DISABLED),
        expected_provider="personio",
        max_tavily_requests=0,
        search=lambda query: (),
        model=lambda stage, summaries, ledger: observation(stage),
        blocked_candidate_urls=(PERSONIO_XML,),
    )
    assert [stage.stage for stage in result.stages] == [
        BoosterStage.DETERMINISTIC,
        BoosterStage.TAVILY,
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    ]
    assert "pro" not in " ".join(stage.stage.value for stage in result.stages)
