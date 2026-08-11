from __future__ import annotations

from dataclasses import replace

import pytest

from src.job_lifecycle_health import HttpProbeResult
from src.search_intelligence.product_v1_origin_vacancy_bridge import (
    ExactDetailAttempt,
    OriginCandidateSnapshot,
    SilverContender,
    evaluate_exact_detail_attempts,
    resolve_origin_candidate,
)


def contender() -> SilverContender:
    return SilverContender(
        inspection_priority=1,
        silver_job_id=42,
        title="Senior Machine Learning Engineer",
        company_name="Example GmbH",
        city="Hannover",
        country="DE",
        source_name="stepstone",
        source_url="https://www.stepstone.de/job/legacy-42",
        canonical_source_type="aggregator_company_discovery",
        lifecycle_status="stale_needs_refresh",
        geography_bucket="hannover_explicit",
    )


def candidate(
    candidate_id: int,
    *,
    company_key: str = "example-gmbh",
    company_name: str = "Example GmbH",
    candidate_url: str | None = "https://jobs.example.test/",
    status: str = "candidate",
) -> OriginCandidateSnapshot:
    return OriginCandidateSnapshot(
        candidate_id=candidate_id,
        company_key=company_key,
        company_name=company_name,
        candidate_url=candidate_url,
        source_name_candidate="Example Careers",
        source_family_candidate="example",
        source_target_candidate=None,
        source_type_candidate="employer_origin_career_site",
        status=status,
        risk_level="low",
    )


def probe(
    url: str,
    *,
    status: int | None = 200,
    final_url: str | None = None,
    body: str = "",
    error_type: str | None = None,
) -> HttpProbeResult:
    return HttpProbeResult(
        status_code=status,
        final_url=final_url or url,
        response_text=body,
        redirect_count=0 if final_url in {None, url} else 1,
        error_type=error_type,
        error_message=None,
    )


def active_body(title: str, location: str = "Hannover, Germany") -> str:
    return (
        f"<html><title>{title}</title><body>"
        f"<div>Location:</div><div>{location}</div></body></html>"
    )


def test_unique_generic_origin_candidate_is_ready() -> None:
    resolution = resolve_origin_candidate(contender(), [candidate(7)])
    assert resolution.status == "ready_for_bounded_detail_discovery"
    assert resolution.candidate is not None
    assert resolution.candidate.candidate_id == 7


def test_multiple_non_terminal_origin_candidates_fail_closed() -> None:
    resolution = resolve_origin_candidate(
        contender(),
        [
            candidate(7, candidate_url="https://jobs.example.test/"),
            candidate(8, candidate_url="https://careers.example.test/"),
        ],
    )
    assert resolution.status == "ambiguous_origin_candidate_identity"
    assert resolution.matching_candidate_ids == (7, 8)


def test_terminal_duplicate_does_not_create_false_ambiguity() -> None:
    resolution = resolve_origin_candidate(
        contender(),
        [
            candidate(7),
            candidate(8, status="deprecated"),
        ],
    )
    assert resolution.status == "ready_for_bounded_detail_discovery"
    assert resolution.matching_candidate_ids == (7,)


def test_unique_candidate_without_origin_root_reports_cand_prerequisite() -> None:
    resolution = resolve_origin_candidate(
        contender(),
        [candidate(7, candidate_url=None)],
    )
    assert resolution.status == "origin_source_url_required"
    assert resolution.candidate is not None


def test_active_exact_detail_requires_title_and_geography_identity() -> None:
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-42"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=url,
                link_text="Senior Machine Learning Engineer",
                probe=probe(
                    url,
                    body=active_body("Senior Machine Learning Engineer"),
                ),
            )
        ],
    )
    assert result["status"] == "current_vacancy_confirmed"
    assert result["resolved_url"] == url
    assert result["health_outcome"] == "seen_active"
    assessment = result["assessments"][0]
    assert assessment["geography_identity"]["status"] == "compatible"
    assert assessment["exact_vacancy_identity_confirmed"] is True


def test_same_title_current_foreign_location_is_not_exact_vacancy() -> None:
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-north-macedonia"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=url,
                link_text="Apply now",
                probe=probe(
                    url,
                    body=active_body(
                        "Senior Machine Learning Engineer - North Macedonia",
                        "Skopje, North Macedonia",
                    ),
                ),
            )
        ],
    )

    assert result["status"] == "exact_vacancy_not_found"
    assert result["resolved_url"] is None
    assessment = result["assessments"][0]
    assert assessment["page_title_match"] is True
    assert assessment["geography_identity"]["status"] == "conflict"
    assert assessment["exact_vacancy_identity_confirmed"] is False


def test_active_title_without_current_location_evidence_fails_closed() -> None:
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-42"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=url,
                link_text="Senior Machine Learning Engineer",
                probe=probe(
                    url,
                    body="<html><title>Senior Machine Learning Engineer</title></html>",
                ),
            )
        ],
    )

    assert result["status"] == "exact_vacancy_current_state_unverifiable"
    assert result["resolved_url"] is None
    assert result["assessments"][0]["geography_identity"]["status"] == "evidence_required"


def test_germany_remote_current_location_is_geography_compatible() -> None:
    remote = replace(
        contender(),
        city="Berlin",
        country="Germany",
        geography_bucket="germany_remote",
    )
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-remote"
    result = evaluate_exact_detail_attempts(
        remote,
        [
            ExactDetailAttempt(
                url=url,
                link_text="Senior Machine Learning Engineer",
                probe=probe(
                    url,
                    body=active_body(
                        "Senior Machine Learning Engineer",
                        "Remote",
                    ),
                ),
            )
        ],
    )

    assert result["status"] == "current_vacancy_confirmed"
    assert result["assessments"][0]["geography_identity"]["status"] == "compatible"


def test_json_ld_job_location_is_accepted_as_current_geography_evidence() -> None:
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-42"
    body = """
    <html><title>Senior Machine Learning Engineer</title>
    <script type="application/ld+json">
    {"@type":"JobPosting","jobLocation":{"@type":"Place","address":{
      "@type":"PostalAddress","addressLocality":"Hanover","addressCountry":"Germany"
    }}}
    </script></html>
    """
    result = evaluate_exact_detail_attempts(
        contender(),
        [ExactDetailAttempt(url=url, link_text="Apply", probe=probe(url, body=body))],
    )

    assert result["status"] == "current_vacancy_confirmed"
    evidence = result["assessments"][0]["geography_identity"]["location_evidence"]
    assert evidence[0]["source"] == "json_ld_job_location"


def test_detail_page_without_exact_silver_title_is_not_resolved() -> None:
    url = "https://jobs.example.test/jobs/data-engineer-99"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=url,
                link_text="Data Engineer",
                probe=probe(url, body="<html><title>Data Engineer</title></html>"),
            )
        ],
    )
    assert result["status"] == "exact_vacancy_not_found"
    assert result["resolved_url"] is None


def test_410_can_confirm_closed_when_link_identity_matches_exact_title() -> None:
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-42"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=url,
                link_text="Senior Machine Learning Engineer",
                probe=probe(url, status=410),
            )
        ],
    )
    assert result["status"] == "inactive_vacancy_confirmed"
    assert result["health_outcome"] == "closed"


def test_redirect_identity_change_remains_unverifiable() -> None:
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-42"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=url,
                link_text="Senior Machine Learning Engineer",
                probe=probe(
                    url,
                    final_url="https://jobs.example.test/jobs/",
                    body="Senior Machine Learning Engineer",
                ),
            )
        ],
    )
    assert result["status"] == "exact_vacancy_current_state_unverifiable"
    assert result["health_outcome"] == "unverifiable"


def test_multiple_distinct_exact_title_urls_fail_closed() -> None:
    first = "https://jobs.example.test/jobs/senior-machine-learning-engineer-42"
    second = "https://jobs.example.test/jobs/senior-machine-learning-engineer-43"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=first,
                link_text="Senior Machine Learning Engineer",
                probe=probe(
                    first,
                    body=active_body("Senior Machine Learning Engineer"),
                ),
            ),
            ExactDetailAttempt(
                url=second,
                link_text="Senior Machine Learning Engineer",
                probe=probe(
                    second,
                    body=active_body("Senior Machine Learning Engineer"),
                ),
            ),
        ],
    )
    assert result["status"] == "ambiguous_exact_vacancy_identity"
    assert result["resolved_url"] is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (404, "exact_vacancy_current_state_unverifiable"),
        (403, "exact_vacancy_current_state_unverifiable"),
        (429, "exact_vacancy_current_state_unverifiable"),
        (500, "exact_vacancy_current_state_unverifiable"),
    ],
)
def test_weak_http_outcomes_never_become_active(status: int, expected: str) -> None:
    url = "https://jobs.example.test/jobs/senior-machine-learning-engineer-42"
    result = evaluate_exact_detail_attempts(
        contender(),
        [
            ExactDetailAttempt(
                url=url,
                link_text="Senior Machine Learning Engineer",
                probe=probe(url, status=status),
            )
        ],
    )
    assert result["status"] == expected
    assert result["health_outcome"] == "unverifiable"
