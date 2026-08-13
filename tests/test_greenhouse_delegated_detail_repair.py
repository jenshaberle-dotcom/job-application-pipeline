from __future__ import annotations

from scripts.run_employer_origin_detail_evidence_repair_agent import SourceCandidate
from scripts.run_employer_origin_greenhouse_detail_evidence_repair import (
    build_greenhouse_delegated_repair_outcome,
)


EMPLOYER_URL = "https://commercetools.com/careers"
BOARD_METADATA_URL = "https://boards-api.greenhouse.io/v1/boards/commercetools"
BOARD_JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/commercetools/jobs"
DETAIL_URL = "https://job-boards.greenhouse.io/commercetools/jobs/7774985003"


def make_commercetools_candidate() -> SourceCandidate:
    return SourceCandidate(
        id=47,
        company_key="commercetools",
        company_name="commercetools GmbH",
        candidate_url=EMPLOYER_URL,
        source_name_candidate="commercetools:hannover",
        source_family_candidate="commercetools",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="manual_review",
        risk_level="low",
    )


def employer_page_with_greenhouse_reference() -> str:
    return (
        '<html><body><script src="'
        + BOARD_JOBS_URL
        + '?content=true"></script><div>Careers</div></body></html>'
    )


def matching_jobs_payload(*, absolute_url: str = DETAIL_URL) -> dict[str, object]:
    return {
        "jobs": [
            {
                "id": 7774985003,
                "title": "Senior Data Engineer",
                "location": {"name": "Germany - Hybrid"},
                "absolute_url": absolute_url,
            }
        ]
    }


def make_fetcher(*, employer_html: str | None = None, detail_has_location: bool = True):
    requested: list[str] = []
    source_html = employer_html if employer_html is not None else employer_page_with_greenhouse_reference()

    def fetcher(url: str) -> tuple[str, str, int]:
        requested.append(url)
        if url == EMPLOYER_URL:
            return source_html, url, 200
        if url == DETAIL_URL:
            location = "Germany Hybrid" if detail_has_location else "London office"
            return (
                f"<html><title>Senior Data Engineer</title><body>"
                f"Data SQL Python AI software platform. Location: {location}."
                f"</body></html>",
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    return fetcher, requested


def make_greenhouse_json_fetcher(
    *,
    board_name: str = "commercetools",
    jobs_payload: dict[str, object] | None = None,
):
    requested: list[str] = []
    jobs = jobs_payload if jobs_payload is not None else matching_jobs_payload()

    def json_fetcher(url: str):
        requested.append(url)
        if url == BOARD_METADATA_URL:
            return {"name": board_name}, url, 200
        if url == BOARD_JOBS_URL:
            return jobs, url, 200
        raise AssertionError(f"Unexpected Greenhouse JSON URL: {url}")

    return json_fetcher, requested


def run_outcome(*, fetcher, greenhouse_json_fetcher, candidate: SourceCandidate | None = None):
    return build_greenhouse_delegated_repair_outcome(
        candidate=candidate or make_commercetools_candidate(),
        gates={},
        profile_terms=("data", "sql", "python", "ai", "software"),
        location_terms=("hannover", "remote", "hybrid"),
        max_seed_pages=2,
        max_detail_pages=3,
        enable_search_discovery=False,
        fetcher=fetcher,
        greenhouse_json_fetcher=greenhouse_json_fetcher,
    )


def test_greenhouse_delegation_positive_commercetools_path_uses_existing_detail_validator() -> None:
    fetcher, requested_pages = make_fetcher()
    json_fetcher, requested_json = make_greenhouse_json_fetcher()

    outcome = run_outcome(fetcher=fetcher, greenhouse_json_fetcher=json_fetcher)

    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert outcome.stop_reason is None
    assert [detail.final_url for detail in outcome.details] == [DETAIL_URL]
    assert outcome.details[0].profile_terms
    assert "hybrid" in outcome.details[0].location_terms
    assert requested_pages.count(EMPLOYER_URL) == 2  # ordinary pass + fresh delegation authority check
    assert requested_pages.count(DETAIL_URL) == 1
    assert requested_json == [BOARD_METADATA_URL, BOARD_JOBS_URL]
    delegated = outcome.evidence["greenhouse_delegation"]
    assert delegated["authorized"] is True
    assert delegated["board_identity_proven"] is True
    assert delegated["status"] == "delegation_proven_detail_supported"
    assert delegated["generic_ats_delegation_enabled"] is False
    assert outcome.evidence["supported_details"][0]["final_url"] == DETAIL_URL


def test_greenhouse_delegation_rejects_wrong_first_party_board_organization_name() -> None:
    fetcher, requested_pages = make_fetcher()
    json_fetcher, requested_json = make_greenhouse_json_fetcher(board_name="unrelated employer")

    outcome = run_outcome(fetcher=fetcher, greenhouse_json_fetcher=json_fetcher)

    assert not outcome.details
    assert outcome.gate_status == "manual_review_required"
    assert requested_json == [BOARD_METADATA_URL]
    assert DETAIL_URL not in requested_pages
    delegated = outcome.evidence["greenhouse_delegation"]
    assert delegated["authorized"] is False
    assert delegated["status"] == "board_identity_failed"
    assert delegated["hostname_or_token_alone_authoritative"] is False


def test_greenhouse_delegation_requires_fresh_employer_page_greenhouse_reference() -> None:
    fetcher, requested_pages = make_fetcher(
        employer_html="<html><body>Careers without delegated ATS reference.</body></html>"
    )
    json_fetcher, requested_json = make_greenhouse_json_fetcher()

    outcome = run_outcome(fetcher=fetcher, greenhouse_json_fetcher=json_fetcher)

    assert not outcome.details
    assert requested_pages.count(EMPLOYER_URL) == 2
    assert requested_json == []
    delegated = outcome.evidence["greenhouse_delegation"]
    assert delegated["status"] == "missing_fresh_employer_greenhouse_reference"
    assert delegated["fresh_greenhouse_reference_hosts"] == []


def test_greenhouse_delegation_rejects_greenhouse_hostname_with_wrong_board_token_job() -> None:
    fetcher, requested_pages = make_fetcher()
    json_fetcher, requested_json = make_greenhouse_json_fetcher(
        jobs_payload=matching_jobs_payload(
            absolute_url="https://job-boards.greenhouse.io/contentful/jobs/7774985003"
        )
    )

    outcome = run_outcome(fetcher=fetcher, greenhouse_json_fetcher=json_fetcher)

    assert not outcome.details
    assert DETAIL_URL not in requested_pages
    assert requested_json == [BOARD_METADATA_URL, BOARD_JOBS_URL]
    delegated = outcome.evidence["greenhouse_delegation"]
    assert delegated["authorized"] is True
    assert delegated["token_consistent_job_count"] == 0
    assert delegated["profile_location_candidate_count"] == 0
    assert delegated["hostname_or_token_alone_authoritative"] is False


def test_greenhouse_delegation_does_not_fetch_details_without_profile_and_location_match() -> None:
    fetcher, requested_pages = make_fetcher()
    json_fetcher, requested_json = make_greenhouse_json_fetcher(
        jobs_payload={
            "jobs": [
                {
                    "id": 7774985003,
                    "title": "Sales Manager",
                    "location": {"name": "London"},
                    "absolute_url": DETAIL_URL,
                }
            ]
        }
    )

    outcome = run_outcome(fetcher=fetcher, greenhouse_json_fetcher=json_fetcher)

    assert not outcome.details
    assert DETAIL_URL not in requested_pages
    assert requested_json == [BOARD_METADATA_URL, BOARD_JOBS_URL]
    delegated = outcome.evidence["greenhouse_delegation"]
    assert delegated["authorized"] is True
    assert delegated["profile_location_candidate_count"] == 0
    assert delegated["status"] == "board_authorized_no_current_profile_location_match"


def test_greenhouse_delegation_does_not_leak_to_personio_or_unreviewed_company() -> None:
    personio_candidate = SourceCandidate(
        id=33,
        company_key="x1f",
        company_name="X1F GmbH",
        candidate_url="https://x1f.jobs.personio.de/",
        source_name_candidate="x1f:hannover",
        source_family_candidate="x1f",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="manual_review",
        risk_level="low",
    )
    requested_pages: list[str] = []

    def fetcher(url: str) -> tuple[str, str, int]:
        requested_pages.append(url)
        assert url == personio_candidate.candidate_url
        return (
            '<html><body><a href="https://x1f.jobs.personio.de/job/12345">Jobs</a></body></html>',
            url,
            200,
        )

    json_fetcher, requested_json = make_greenhouse_json_fetcher()
    outcome = run_outcome(
        fetcher=fetcher,
        greenhouse_json_fetcher=json_fetcher,
        candidate=personio_candidate,
    )

    assert not outcome.details
    assert requested_json == []
    delegated = outcome.evidence["greenhouse_delegation"]
    assert delegated["status"] == "missing_fresh_employer_greenhouse_reference"
    assert delegated["generic_ats_delegation_enabled"] is False
