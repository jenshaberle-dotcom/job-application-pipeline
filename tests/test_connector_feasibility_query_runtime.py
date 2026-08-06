from __future__ import annotations

from src.search_intelligence.connector_feasibility import (
    OriginCandidate,
    ProbeFetchResult,
)
from src.search_intelligence.connector_feasibility_query_runtime import (
    evaluate_connector_feasibility_runtime,
    extract_trusted_query_job_detail_links,
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


def test_query_parameter_job_detail_reaches_likely_feasible() -> None:
    origin_url = "https://careers.example.com/de"
    detail_url = "https://careers.example.com/de?id=458ccb"
    html = f"""
        <section class="job-list">
          <a href="{detail_url}">Bid Manager (m/w/d)</a>
          <a href="{detail_url}">Mehr</a>
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
    assert item.url_quality.status == "valid_probe_ready"
    assert item.evidence["query_parameter_job_detail_candidates"] == [
        detail_url
    ]


def test_query_detail_allows_bounded_company_scope_parameter() -> None:
    origin_url = "https://jobs.example.com/de"
    detail_url = (
        "https://jobs.example.com/de?companyId=tenant_42&id=082cba"
    )
    html = (
        f'<a href="{detail_url}">'
        "Cloud Consultant (m/w/d)"
        "</a>"
    )

    links = extract_trusted_query_job_detail_links(origin_url, html)

    assert tuple(link.url for link in links) == (detail_url,)


def test_query_detail_rejects_generic_label_without_role_evidence() -> None:
    origin_url = "https://jobs.example.com/de"
    detail_url = "https://jobs.example.com/de?id=458ccb"
    html = f'<a href="{detail_url}">Mehr</a>'

    assert extract_trusted_query_job_detail_links(origin_url, html) == ()


def test_query_detail_rejects_tracking_only_query() -> None:
    origin_url = "https://jobs.example.com/de"
    tracking_url = "https://jobs.example.com/de?utm_source=newsletter"
    html = f'<a href="{tracking_url}">Data Engineer (m/w/d)</a>'

    assert extract_trusted_query_job_detail_links(origin_url, html) == ()


def test_query_detail_rejects_unrelated_job_host() -> None:
    origin_url = "https://jobs.example.com/de"
    lookalike = "https://careers.evil.test/de?id=458ccb"
    html = f'<a href="{lookalike}">Data Engineer (m/w/d)</a>'

    assert extract_trusted_query_job_detail_links(origin_url, html) == ()


def test_query_detail_rejects_non_job_host() -> None:
    origin_url = "https://www.example.com/de"
    detail_url = "https://www.example.com/de?id=458ccb"
    html = f'<a href="{detail_url}">Data Engineer (m/w/d)</a>'

    assert extract_trusted_query_job_detail_links(origin_url, html) == ()


def test_query_detail_rejects_redirect_parameter() -> None:
    origin_url = "https://jobs.example.com/de"
    detail_url = (
        "https://jobs.example.com/de"
        "?id=458ccb&redirectUrl=https%3A%2F%2Fevil.test"
    )
    html = f'<a href="{detail_url}">Data Engineer (m/w/d)</a>'

    assert extract_trusted_query_job_detail_links(origin_url, html) == ()
