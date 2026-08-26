from __future__ import annotations

from src.search_intelligence.connector_feasibility import (
    OriginCandidate,
    ProbeFetchResult,
)
from src.search_intelligence.connector_feasibility_runtime import (
    evaluate_connector_feasibility_runtime,
    extract_trusted_delegated_job_board_urls,
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


def fetched(origin_url: str, html: str) -> ProbeFetchResult:
    return ProbeFetchResult(
        final_url=origin_url,
        http_status=200,
        body=html,
    )


def test_dynamic_job_board_structure_remains_manual_without_detail() -> None:
    origin_url = "https://jobs.example.com/"
    html = """
        <html>
          <body>
            <form class="job-search" action="/search/">
              <input name="keyword" aria-label="Job title">
              <input name="location" aria-label="Location">
            </form>
            <section class="job-list" data-job-list="true">
              <span>Data Engineer</span>
              <span>Remote</span>
            </section>
          </body>
        </html>
    """

    item = evaluate_connector_feasibility_runtime(
        candidate(origin_url),
        fetch_result=fetched(origin_url, html),
    )

    assert item.feasibility_status == "manual_review_required"
    assert item.decision == "manual_review_required"
    assert item.blocker_code == "structural_evidence_without_job_detail"
    assert item.structural_job_evidence_count > 0
    assert item.job_detail_candidate_evidence_count == 0
    assert item.url_quality.status == "structural_without_detail"
    assert item.evidence["html_structural_job_evidence"] is True


def test_strong_delegated_board_label_surfaces_repair_candidate() -> None:
    origin_url = "https://www.example.com/karriere/"
    board_url = "https://karriere.example.com/de"
    html = f'<a href="{board_url}">Offene Stellen</a>'

    item = evaluate_connector_feasibility_runtime(
        candidate(origin_url),
        fetch_result=fetched(origin_url, html),
    )

    assert item.feasibility_status == "manual_review_required"
    assert item.blocker_code == "origin_url_repair_candidate_detected"
    assert item.url_quality.status == "repair_candidate_detected"
    assert item.url_quality.repair_candidate_url == board_url
    assert item.structural_job_evidence_count == 0
    assert item.evidence["delegated_job_board_candidates"] == [board_url]


def test_search_path_with_strong_label_is_a_delegated_board_candidate() -> None:
    origin_url = "https://www.example.com/careers/"
    board_url = "https://careers.example.com/search/"
    html = f'<a href="{board_url}">Search jobs</a>'

    assert extract_trusted_delegated_job_board_urls(origin_url, html) == (
        board_url,
    )


def test_explicit_greenhouse_tenant_root_is_a_delegated_board_repair_candidate() -> None:
    origin_url = "https://www.example.com/careers/"
    board_url = "https://job-boards.greenhouse.io/example"
    html = f'<a href="{board_url}">See all open positions</a>'

    assert extract_trusted_delegated_job_board_urls(origin_url, html) == (
        board_url,
    )

    item = evaluate_connector_feasibility_runtime(
        candidate(origin_url),
        fetch_result=fetched(origin_url, html),
    )
    assert item.blocker_code == "origin_url_repair_candidate_detected"
    assert item.url_quality.repair_candidate_url == board_url


def test_explicit_ashby_tenant_root_is_a_delegated_board_candidate() -> None:
    origin_url = "https://www.example.com/careers/"
    board_url = "https://jobs.ashbyhq.com/examplecareer"
    html = f'<a href="{board_url}">View jobs</a>'

    assert extract_trusted_delegated_job_board_urls(origin_url, html) == (
        board_url,
    )


def test_job_named_lookalike_without_trusted_host_is_rejected() -> None:
    origin_url = "https://www.example.com/careers/"
    lookalike = "https://example-careers.evil.test/de"
    html = f'<a href="{lookalike}">Offene Stellen</a>'

    assert extract_trusted_delegated_job_board_urls(origin_url, html) == ()


def test_concrete_job_detail_still_reaches_likely_feasible() -> None:
    origin_url = "https://careers.example.com/jobs"
    detail_url = "https://careers.example.com/jobs/data-engineer"
    html = f"""
        <section class="job-list">
          <a href="{detail_url}">Data Engineer</a>
        </section>
    """

    item = evaluate_connector_feasibility_runtime(
        candidate(origin_url),
        fetch_result=fetched(origin_url, html),
    )

    assert item.feasibility_status == "likely_feasible"
    assert item.decision == "continue_to_connector_build_planning"
    assert item.blocker_code is None
    assert item.job_detail_candidate_evidence_count == 1
    assert item.sample_job_urls == (detail_url,)
