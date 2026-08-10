from __future__ import annotations

import pytest

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    SourceCandidate,
    build_repair_outcome,
    concrete_job_detail_url,
)
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


@pytest.mark.parametrize(
    "url",
    [
        "https://career.example.test/job-invite/5161/",
        "https://career.example.test/job-invite/5161?locale=de_DE",
    ],
)
def test_job_invite_numeric_path_is_concrete_detail(url: str) -> None:
    assert job_detail_url_shape(url)
    assert concrete_job_detail_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://career.example.test/job-invite/",
        "https://career.example.test/job-invite/search",
        "https://career.example.test/job-invite/foo",
        "https://career.example.test/content/job-invite/5161/",
    ],
)
def test_job_invite_non_detail_shapes_are_rejected(url: str) -> None:
    assert not job_detail_url_shape(url)
    assert not concrete_job_detail_url(url)


def test_repair_agent_validates_job_invite_detail_from_listing() -> None:
    listing_url = "https://career.example.test/search/"
    detail_url = "https://career.example.test/job-invite/5161/"
    candidate = SourceCandidate(
        id=46,
        company_key="example",
        company_name="Example Telecom GmbH",
        candidate_url=listing_url,
        source_name_candidate="example:discovery",
        source_family_candidate="example",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == listing_url:
            return (
                f'<html><body><a href="{detail_url}">Data Engineer Hannover</a></body></html>',
                url,
                200,
            )
        if url == detail_url:
            return (
                """
                <html>
                  <title>Data Engineer</title>
                  <body>Data Engineer in Hannover with Python, SQL and Analytics.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "python", "sql", "analytics"),
        location_terms=("hannover",),
        max_seed_pages=1,
        max_detail_pages=2,
        enable_search_discovery=False,
        fetcher=fetcher,
    )

    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert outcome.stop_reason is None
    assert [detail.final_url for detail in outcome.details] == [detail_url]
    assert outcome.evidence["decision_taxonomy"] == "accepted"
