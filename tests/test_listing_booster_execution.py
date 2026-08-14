from __future__ import annotations

from collections.abc import Sequence

from src.search_intelligence.connector_feasibility import ProbeFetchResult
from src.search_intelligence.listing_booster_execution import (
    deterministic_listing_queries,
    execute_listing_booster,
    listing_candidate_resolves,
)
from src.search_intelligence.listing_route_hypothesis_provider import (
    ListingRouteHypothesisObservation,
)
from src.search_intelligence.listing_surface_evidence import analyze_listing_surface
from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState


def fetched(url: str, html: str, status: int = 200) -> ProbeFetchResult:
    return ProbeFetchResult(final_url=url, http_status=status, body=html)


def gap_evidence():  # type: ignore[no-untyped-def]
    origin = "https://www.example.com/karriere"
    return analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, "<h1>Karriere bei Example</h1>"),
    )


def resolved_evidence():  # type: ignore[no-untyped-def]
    origin = "https://jobs.example.com/jobs"
    return analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(
            origin,
            '<a href="/jobs/42/data-engineer">Data Engineer</a>',
        ),
    )


def observation(
    stage: BoosterStage,
    urls: Sequence[str] = (),
    *,
    status: str = "completed",
    attempted: bool = True,
) -> ListingRouteHypothesisObservation:
    model = {
        BoosterStage.LUNA_MEDIUM: "gpt-5.6-luna",
        BoosterStage.TERRA_MEDIUM: "gpt-5.6-terra",
        BoosterStage.SOL_MEDIUM: "gpt-5.6-sol",
        BoosterStage.LUNA_MAX: "gpt-5.6-luna",
    }[stage]
    return ListingRouteHypothesisObservation(
        status=status,
        request_attempted=attempted,
        model=model,
        response_id="resp_test" if attempted else None,
        latency_ms=1,
        estimated_cost_usd=0.001 if attempted else 0.0,
        packet_sha256="a" * 64,
        urls=tuple(urls),
        rationale="bounded test hypothesis",
        product_authority=False,
        failure_class=None if status == "completed" else "SyntheticFailure",
        failure_message=None if status == "completed" else "synthetic",
    )


def test_deterministic_listing_resolution_spends_zero_provider_requests() -> None:
    evidence = resolved_evidence()

    def forbidden_search(query: str):  # type: ignore[no-untyped-def]
        raise AssertionError(f"search must not run: {query}")

    def forbidden_fetch(url: str):  # type: ignore[no-untyped-def]
        raise AssertionError(f"candidate fetch must not run: {url}")

    def forbidden_model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        raise AssertionError(f"model must not run: {stage}")

    result = execute_listing_booster(
        company_name="Example GmbH",
        deterministic_evidence=evidence,
        tavily_state=TavilyState.AVAILABLE,
        max_tavily_requests=2,
        search=forbidden_search,
        fetch=forbidden_fetch,
        model=forbidden_model,
    )
    assert result.resolved is True
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert result.product_writes == 0
    assert result.product_authority is False
    assert [stage.stage for stage in result.stages] == [
        BoosterStage.DETERMINISTIC,
        BoosterStage.TAVILY,
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    ]
    assert all(not stage.attempted for stage in result.stages[1:])


def test_unchanged_external_gap_fingerprint_spends_zero_again() -> None:
    evidence = gap_evidence()

    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("unchanged evidence must not spend or refetch candidates")

    result = execute_listing_booster(
        company_name="Example GmbH",
        deterministic_evidence=evidence,
        tavily_state=TavilyState.AVAILABLE,
        max_tavily_requests=2,
        search=forbidden,
        fetch=forbidden,
        model=forbidden,
        previous_evidence_fingerprint=evidence.evidence_fingerprint,
    )
    assert result.unchanged_evidence_skip is True
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert all(not stage.attempted for stage in result.stages[1:])


def test_tavily_success_is_deterministically_revalidated_and_skips_models() -> None:
    evidence = gap_evidence()
    listing_url = "https://jobs.example.com/positions"
    model_calls: list[BoosterStage] = []

    def search(query: str) -> Sequence[str]:
        return [listing_url]

    def fetch(url: str) -> ProbeFetchResult:
        assert url == listing_url
        return fetched(
            url,
            '<form class="job-search"><input name="keyword"></form>'
            '<section class="job-list"><a href="/positions/42/data-engineer">Data Engineer</a></section>',
        )

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return observation(stage)

    result = execute_listing_booster(
        company_name="Example GmbH",
        deterministic_evidence=evidence,
        tavily_state=TavilyState.AVAILABLE,
        max_tavily_requests=1,
        search=search,
        fetch=fetch,
        model=model,
    )
    assert result.resolved_url == listing_url
    assert result.provider_requests == 1
    assert result.llm_requests == 0
    assert model_calls == []
    assert result.stages[1].stage == BoosterStage.TAVILY
    assert result.stages[1].status == "resolved"
    assert all(not stage.attempted for stage in result.stages[2:])
    assert result.candidate_evidence[0]["deterministically_resolves_listing"] is True


def test_unavailable_tavily_does_not_block_luna() -> None:
    evidence = gap_evidence()
    listing_url = "https://careers.example.com/jobs"
    calls: list[BoosterStage] = []

    def forbidden_search(query: str):  # type: ignore[no-untyped-def]
        raise AssertionError("Tavily unavailable must not call search")

    def fetch(url: str) -> ProbeFetchResult:
        return fetched(url, '<div class="job-list"><a href="/jobs/1/data">Data</a></div>')

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        calls.append(stage)
        return observation(stage, [listing_url])

    result = execute_listing_booster(
        company_name="Example GmbH",
        deterministic_evidence=evidence,
        tavily_state=TavilyState.INSUFFICIENT_BUDGET,
        max_tavily_requests=0,
        search=forbidden_search,
        fetch=fetch,
        model=model,
    )
    assert calls == [BoosterStage.LUNA_MEDIUM]
    assert result.resolved_url == listing_url
    assert result.provider_requests == 1
    assert result.llm_requests == 1
    assert result.stages[1].attempted is False
    assert result.stages[2].status == "resolved"


def test_lone_jobposting_hypothesis_does_not_resolve_listing_route() -> None:
    detail = "https://jobs.example.com/job/42"
    evidence = analyze_listing_surface(
        origin_url=detail,
        fetch_result=fetched(
            detail,
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"JobPosting","title":"Data Engineer"}'
            '</script>',
        ),
    )
    assert evidence.classification == "dynamic_listing_structure"
    assert listing_candidate_resolves(evidence) is False


def test_itemlist_or_structural_list_can_resolve_listing_route() -> None:
    listing = "https://jobs.example.com/jobs"
    item_list = analyze_listing_surface(
        origin_url=listing,
        fetch_result=fetched(
            listing,
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"ItemList","itemListElement":[]}'
            '</script>',
        ),
    )
    assert listing_candidate_resolves(item_list) is True


def test_failed_luna_continues_to_terra_and_terra_can_resolve() -> None:
    evidence = gap_evidence()
    listing_url = "https://jobs.example.com/jobs"
    calls: list[BoosterStage] = []

    def fetch(url: str) -> ProbeFetchResult:
        return fetched(url, '<div data-job-list="true"><a href="/jobs/1/data">Data</a></div>')

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        calls.append(stage)
        if stage == BoosterStage.LUNA_MEDIUM:
            return observation(stage, status="failed_closed")
        return observation(stage, [listing_url])

    result = execute_listing_booster(
        company_name="Example GmbH",
        deterministic_evidence=evidence,
        tavily_state=TavilyState.BUDGET_EXHAUSTED,
        max_tavily_requests=0,
        search=lambda query: (),
        fetch=fetch,
        model=model,
    )
    assert calls == [BoosterStage.LUNA_MEDIUM, BoosterStage.TERRA_MEDIUM]
    assert result.resolved_url == listing_url
    assert result.provider_requests == 2
    assert result.llm_requests == 2
    assert result.stages[2].status == "failed_closed"
    assert result.stages[3].status == "resolved"


def test_repeated_model_url_is_not_fetched_twice() -> None:
    evidence = gap_evidence()
    detail = "https://jobs.example.com/job/42"
    fetches: list[str] = []

    def fetch(url: str) -> ProbeFetchResult:
        fetches.append(url)
        return fetched(
            url,
            '<script type="application/ld+json">'
            '{"@type":"JobPosting","title":"Data"}'
            '</script>',
        )

    def model(stage, summaries, ledger):  # type: ignore[no-untyped-def]
        return observation(stage, [detail])

    result = execute_listing_booster(
        company_name="Example GmbH",
        deterministic_evidence=evidence,
        tavily_state=TavilyState.DISABLED,
        max_tavily_requests=0,
        search=lambda query: (),
        fetch=fetch,
        model=model,
    )
    assert fetches == [detail]
    assert result.resolved is False
    assert result.llm_requests == 4
    assert result.stages[-1].stage == BoosterStage.DEEP_EVIDENCE
    assert result.stages[-1].provider_requests == 0
    assert result.product_authority is False


def test_deterministic_listing_queries_are_bounded_and_origin_scoped() -> None:
    queries = deterministic_listing_queries(
        company_name="Example GmbH",
        origin_url="https://www.example.com/karriere",
        maximum=3,
    )
    assert len(queries) == 3
    assert queries[0] == '"Example GmbH" jobs careers'
    assert queries[-1] == "site:example.com jobs"
