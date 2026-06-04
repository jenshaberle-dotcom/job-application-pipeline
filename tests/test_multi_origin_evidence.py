from __future__ import annotations

from src.search_intelligence.multi_origin_evidence import (
    EvidenceDecision,
    build_search_discovery_queries,
    classify_checked_url,
    decode_search_redirect_url,
    job_detail_url_shape,
    plausible_sibling_origin_urls,
    successfactors_like_job_detail_url,
)


def test_successfactors_like_hdi_job_url_is_detail_shape() -> None:
    url = "https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/"

    assert successfactors_like_job_detail_url(url)
    assert job_detail_url_shape(url)


def test_plausible_sibling_origin_urls_include_job_host() -> None:
    candidates = plausible_sibling_origin_urls(
        "https://careers.hdi.group/de/karriere/jobs",
        company_key="hdi",
    )
    urls = {candidate.url for candidate in candidates}

    assert "https://job.hdi.group/" in urls
    assert "https://job.hdi.group/job" in urls
    assert "https://jobs.hdi.group/jobs" in urls


def test_search_queries_include_company_jobs_and_site_queries() -> None:
    queries = build_search_discovery_queries(
        company_name="HDI Group",
        company_key="hdi",
        profile_terms=("data", "analytics"),
        location_terms=("hannover",),
    )
    query_text = [query.query for query in queries]

    assert "HDI Group jobs" in query_text
    assert "HDI Group data hannover" in query_text
    assert any(query.startswith("site:job.hdi.group") for query in query_text)


def test_decode_search_redirect_url_prefers_embedded_target_url() -> None:
    url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fjob.hdi.group%2Fjob%2FData%2F720-en_US%2F"

    assert decode_search_redirect_url(url) == "https://job.hdi.group/job/Data/720-en_US/"


def test_classify_checked_url_marks_unsupported_detail_as_implementation_gap_without_text() -> None:
    assessment = classify_checked_url(
        url="https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/",
        reference_url="https://careers.hdi.group/de/karriere/jobs",
        profile_terms=("data",),
        location_terms=("hannover",),
        text="",
    )

    assert assessment.decision == EvidenceDecision.IMPLEMENTATION_GAP
    assert assessment.confidence_score >= 0.70
