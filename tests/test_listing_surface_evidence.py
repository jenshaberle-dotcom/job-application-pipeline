from __future__ import annotations

from src.search_intelligence.connector_feasibility import ProbeFetchResult
from src.search_intelligence.listing_surface_evidence import (
    analyze_listing_surface,
    build_listing_booster_plan,
    extract_jsonld_types,
)
from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState


def fetched(
    final_url: str,
    html: str,
    *,
    status: int = 200,
    blocked: bool = False,
    error: str | None = None,
) -> ProbeFetchResult:
    return ProbeFetchResult(
        final_url=final_url,
        http_status=status,
        body=html,
        error=error,
        blocked_by_site=blocked,
    )


def eligibility(plan) -> dict[BoosterStage, bool]:  # type: ignore[no-untyped-def]
    return {stage.stage: stage.eligible for stage in plan.stages}


def test_msg_style_same_host_redirect_with_current_links_is_proven() -> None:
    origin = "https://jobs.msg.group/de/jobs"
    final = "https://jobs.msg.group/de/jobs/iframe"
    links = "".join(
        f'<a href="/de/jobs/{index}/data-engineer-{index}">Data Engineer {index}</a>'
        for index in range(146)
    )

    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(final, links),
    )

    assert evidence.classification == "current_listing_route_proven"
    assert evidence.same_host_redirect is True
    assert len(evidence.current_job_urls) == 146
    assert evidence.external_search_gap is False
    assert evidence.next_action == "use_current_listing_route"

    plan = build_listing_booster_plan(evidence, tavily_state=TavilyState.AVAILABLE)
    stages = eligibility(plan)
    assert plan.deterministic_resolved is True
    assert all(
        not stages[stage]
        for stage in (
            BoosterStage.TAVILY,
            BoosterStage.LUNA_MEDIUM,
            BoosterStage.TERRA_MEDIUM,
            BoosterStage.SOL_MEDIUM,
            BoosterStage.LUNA_MAX,
            BoosterStage.DEEP_EVIDENCE,
        )
    )


def test_dynamic_job_structure_is_deterministic_projection_work_not_search_gap() -> None:
    origin = "https://jobs.example.com/de"
    html = """
      <form class="job-search"><input name="keyword"><input name="location"></form>
      <section class="job-list" data-job-list="true"><span>Data Engineer</span></section>
    """
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, html),
    )

    assert evidence.classification == "dynamic_listing_structure"
    assert evidence.structural_html is True
    assert evidence.external_search_gap is False
    assert evidence.next_action == "improve_bounded_detail_projection"
    plan = build_listing_booster_plan(evidence, tavily_state=TavilyState.AVAILABLE)
    assert plan.deterministic_resolved is True


def test_trusted_iframe_route_is_followed_before_any_provider() -> None:
    origin = "https://www.example.com/karriere"
    iframe = "https://jobs.example.com/de/jobs/iframe"
    html = f'<iframe src="{iframe}"></iframe>'

    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, html),
    )

    assert evidence.classification == "deterministic_listing_route_candidate"
    assert evidence.route_candidates == (iframe,)
    assert evidence.external_search_gap is False
    assert evidence.next_action == "bounded_follow_route_candidate"
    assert build_listing_booster_plan(
        evidence,
        tavily_state=TavilyState.AVAILABLE,
    ).deterministic_resolved is True


def test_unrelated_iframe_lookalike_is_not_trusted() -> None:
    origin = "https://www.example.com/karriere"
    html = '<iframe src="https://jobs.evil.test/de/jobs"></iframe>'
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, html),
    )

    assert evidence.route_candidates == ()
    assert evidence.classification == "external_listing_information_gap"
    assert evidence.external_search_gap is True


def test_jsonld_jobposting_is_deterministic_structure_not_search_gap() -> None:
    origin = "https://careers.example.com/jobs"
    html = """
      <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting","title":"Data Engineer"}
      </script>
    """
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, html),
    )

    assert extract_jsonld_types(html) == ("JobPosting",)
    assert evidence.classification == "dynamic_listing_structure"
    assert "JobPosting" in evidence.jsonld_types
    assert evidence.external_search_gap is False


def test_reachable_career_surface_without_job_evidence_admits_search_then_models() -> None:
    origin = "https://www.example.com/karriere"
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, "<h1>Karriere bei Example</h1>"),
    )

    assert evidence.classification == "external_listing_information_gap"
    assert evidence.external_search_gap is True
    plan = build_listing_booster_plan(evidence, tavily_state=TavilyState.AVAILABLE)
    stages = eligibility(plan)
    assert plan.deterministic_resolved is False
    assert stages[BoosterStage.TAVILY] is True
    assert stages[BoosterStage.LUNA_MEDIUM] is True
    assert stages[BoosterStage.TERRA_MEDIUM] is True
    assert stages[BoosterStage.SOL_MEDIUM] is True
    assert stages[BoosterStage.LUNA_MAX] is True


def test_tavily_unavailable_does_not_block_models_on_true_external_gap() -> None:
    origin = "https://www.example.com/karriere"
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, "<h1>Careers</h1>"),
    )
    plan = build_listing_booster_plan(
        evidence,
        tavily_state=TavilyState.INSUFFICIENT_BUDGET,
    )
    stages = eligibility(plan)
    assert stages[BoosterStage.TAVILY] is False
    assert stages[BoosterStage.LUNA_MEDIUM] is True
    assert stages[BoosterStage.TERRA_MEDIUM] is True


def test_blocked_surface_is_external_gap_but_network_failure_is_not() -> None:
    origin = "https://jobs.example.com/"
    blocked = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, "", status=403, blocked=True, error="forbidden"),
    )
    assert blocked.classification == "blocked_listing_surface"
    assert blocked.external_search_gap is True

    failed = analyze_listing_surface(
        origin_url=origin,
        fetch_result=ProbeFetchResult(
            final_url=origin,
            http_status=None,
            body="",
            error="timeout",
        ),
    )
    assert failed.classification == "operational_fetch_failure"
    assert failed.external_search_gap is False
    assert build_listing_booster_plan(
        failed,
        tavily_state=TavilyState.AVAILABLE,
    ).deterministic_resolved is True


def test_existing_query_id_detail_is_reused_as_current_job_evidence() -> None:
    origin = "https://jobs.example.com/de"
    detail = "https://jobs.example.com/de?id=458ccb"
    html = f'<a href="{detail}">Data Engineer (m/w/d)</a>'
    evidence = analyze_listing_surface(
        origin_url=origin,
        fetch_result=fetched(origin, html),
    )
    assert evidence.classification == "current_listing_route_proven"
    assert evidence.current_job_urls == (detail,)


def test_evidence_fingerprint_is_stable_for_equivalent_link_order() -> None:
    origin = "https://jobs.example.com/jobs"
    first = '<a href="/jobs/2/data-engineer">Data Engineer</a><a href="/jobs/1/cloud-engineer">Cloud Engineer</a>'
    second = '<a href="/jobs/1/cloud-engineer">Cloud Engineer</a><a href="/jobs/2/data-engineer">Data Engineer</a>'
    left = analyze_listing_surface(origin_url=origin, fetch_result=fetched(origin, first))
    right = analyze_listing_surface(origin_url=origin, fetch_result=fetched(origin, second))
    assert left.current_job_urls == right.current_job_urls
    assert left.evidence_fingerprint == right.evidence_fingerprint
