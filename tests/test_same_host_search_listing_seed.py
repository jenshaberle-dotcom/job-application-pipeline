from __future__ import annotations

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    SourceCandidate,
    build_repair_outcome,
)
from src.search_intelligence.multi_origin_evidence import plausible_sibling_origin_urls


def test_plausible_origin_urls_prioritize_same_host_search_before_siblings() -> None:
    candidates = plausible_sibling_origin_urls(
        "https://career.example.com/",
        company_key="example",
    )

    assert candidates[0].url == "https://career.example.com/"
    assert candidates[1].url == "https://career.example.com/search"
    assert candidates[1].discovery_source == "plausible_same_host_listing"

    first_sibling_index = next(
        index
        for index, candidate in enumerate(candidates)
        if candidate.discovery_source == "plausible_sibling_host"
    )
    assert first_sibling_index > 1


def test_repair_follows_same_host_search_to_current_job_detail() -> None:
    candidate = SourceCandidate(
        id=46,
        company_key="example",
        company_name="Example AG",
        candidate_url="https://career.example.com/",
        source_name_candidate="example:discovery",
        source_family_candidate="example",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )
    detail_url = "https://career.example.com/Access/job/Hannover-AI-Product-Analyst/1355317355/"

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://career.example.com/":
            return "<html><body>Career home without job cards.</body></html>", url, 200
        if url == "https://career.example.com/search":
            return (
                f'<html><body><a href="{detail_url}">AI Product Analyst Hannover</a></body></html>',
                "https://career.example.com/search/",
                200,
            )
        if url == detail_url:
            return (
                """
                <html>
                  <title>AI Product Analyst</title>
                  <body>
                    AI Product Analyst in Hannover. Data analytics, SQL and product ownership.
                  </body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("ai", "data", "analytics", "product owner"),
        location_terms=("hannover",),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=False,
        fetcher=fetcher,
    )

    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert len(outcome.details) == 1
    assert outcome.details[0].final_url == detail_url
    assert "https://career.example.com/search/" in outcome.requested_urls

    checked = outcome.evidence["checked_origin_candidates"]
    search_record = next(
        item
        for item in checked
        if item.get("discovery_source") == "plausible_same_host_listing"
    )
    assert search_record["status"] == "job_detail_candidates_found"
    assert search_record["accepted_link_count"] >= 1
