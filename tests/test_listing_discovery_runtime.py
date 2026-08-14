from __future__ import annotations

from src.search_intelligence.connector_feasibility import OriginCandidate, ProbeFetchResult
from src.search_intelligence.listing_discovery_runtime import (
    evaluate_listing_discovery_runtime,
)


def candidate(origin_url: str) -> OriginCandidate:
    return OriginCandidate(
        candidate_id=1,
        company_key="example",
        company_name="Example GmbH",
        origin_url=origin_url,
        source_name_candidate="example:hannover",
        status="discovery",
        risk_level="low",
    )


def fetched(final_url: str, html: str) -> ProbeFetchResult:
    return ProbeFetchResult(final_url=final_url, http_status=200, body=html)


def test_listing_projection_preserves_likely_feasible_decision() -> None:
    origin = "https://careers.example.com/jobs"
    detail = "https://careers.example.com/jobs/data-engineer"
    item = evaluate_listing_discovery_runtime(
        candidate(origin),
        fetch_result=fetched(origin, f'<a href="{detail}">Data Engineer</a>'),
    )

    assert item.feasibility_status == "likely_feasible"
    assert item.decision == "continue_to_connector_build_planning"
    listing = item.evidence["listing_surface_evidence"]
    assert listing["classification"] == "current_listing_route_proven"
    assert listing["current_job_urls"] == [detail]
    assert listing["external_search_gap"] is False
    assert listing["product_authority"] is False


def test_listing_projection_preserves_dynamic_manual_review() -> None:
    origin = "https://jobs.example.com/de"
    html = """
      <form class="job-search"><input name="keyword"><input name="location"></form>
      <section class="job-list" data-job-list="true"><span>Data Engineer</span></section>
    """
    item = evaluate_listing_discovery_runtime(
        candidate(origin),
        fetch_result=fetched(origin, html),
    )

    assert item.feasibility_status == "manual_review_required"
    assert item.blocker_code == "structural_evidence_without_job_detail"
    listing = item.evidence["listing_surface_evidence"]
    assert listing["classification"] == "dynamic_listing_structure"
    assert listing["external_search_gap"] is False
    assert listing["next_action"] == "improve_bounded_detail_projection"


def test_listing_projection_reuses_single_supplied_fetch() -> None:
    origin = "https://jobs.example.com/de"
    result = fetched(origin, "<h1>Careers</h1>")
    item = evaluate_listing_discovery_runtime(
        candidate(origin),
        fetch_result=result,
    )
    listing = item.evidence["listing_surface_evidence"]
    assert listing["classification"] == "external_listing_information_gap"
    assert listing["external_search_gap"] is True
