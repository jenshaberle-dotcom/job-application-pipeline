from __future__ import annotations

from src.search_intelligence.career_origin_drift import (
    career_origin_drift_candidates,
    redirected_career_origin_candidate,
)


def test_explicit_greenhouse_board_from_authorized_employer_page_is_candidate_only() -> None:
    result = career_origin_drift_candidates(
        page_url="https://commercetools.com/careers",
        html=(
            '<a href="https://job-boards.greenhouse.io/commercetools?gh_src=tracking">'
            "See all open positions</a>"
        ),
        allowed_hosts={"commercetools.com"},
    )

    assert len(result) == 1
    candidate = result[0]
    assert candidate.candidate_url == "https://job-boards.greenhouse.io/commercetools"
    assert candidate.provider == "greenhouse"
    assert candidate.evidence_kind == "explicit_ats_career_transition"
    assert candidate.host_authority is False
    assert candidate.product_authority is False


def test_explicit_ashby_board_is_recognized_without_company_specific_rule() -> None:
    result = career_origin_drift_candidates(
        page_url="https://bjak.my/career",
        html='<a href="https://jobs.ashbyhq.com/examplecareer">Explore our jobs</a>',
        allowed_hosts={"bjak.my"},
    )

    assert [item.provider for item in result] == ["ashby"]


def test_recruiting_sibling_host_is_candidate_when_explicitly_linked() -> None:
    result = career_origin_drift_candidates(
        page_url="https://www.example.group/de/karriere/",
        html='<a href="https://jobs.example.group/de/jobs">Alle offenen Jobs</a>',
        allowed_hosts={"www.example.group"},
    )

    assert len(result) == 1
    assert result[0].candidate_host == "jobs.example.group"
    assert result[0].provider is None
    assert result[0].evidence_kind == "explicit_recruiting_sibling_transition"


def test_random_job_named_cross_host_does_not_gain_candidate_status() -> None:
    result = career_origin_drift_candidates(
        page_url="https://www.example.com/careers",
        html='<a href="https://jobs.unrelated.example/jobs">Open jobs</a>',
        allowed_hosts={"www.example.com"},
    )

    assert result == ()


def test_known_aggregator_is_rejected_even_with_job_label() -> None:
    result = career_origin_drift_candidates(
        page_url="https://www.example.com/careers",
        html='<a href="https://www.linkedin.com/jobs/example">See all jobs</a>',
        allowed_hosts={"www.example.com"},
    )

    assert result == ()


def test_provider_privacy_or_apply_surface_is_not_career_drift_candidate() -> None:
    result = career_origin_drift_candidates(
        page_url="https://www.example.com/careers",
        html=(
            '<a href="https://job-boards.greenhouse.io/example/privacy">Privacy</a>'
            '<a href="https://jobs.ashbyhq.com/example/apply">Apply now</a>'
        ),
        allowed_hosts={"www.example.com"},
    )

    assert result == ()


def test_same_host_navigation_is_not_drift() -> None:
    result = career_origin_drift_candidates(
        page_url="https://www.example.com/careers",
        html='<a href="/careers/jobs">Open jobs</a>',
        allowed_hosts={"www.example.com"},
    )

    assert result == ()


def test_unauthorized_source_page_cannot_nominate_new_host() -> None:
    result = career_origin_drift_candidates(
        page_url="https://www.example.com/careers",
        html='<a href="https://job-boards.greenhouse.io/example">Open jobs</a>',
        allowed_hosts={"careers.example.com"},
    )

    assert result == ()


def test_provider_text_without_explicit_transition_does_not_nominate_host() -> None:
    result = career_origin_drift_candidates(
        page_url="https://www.example.com/careers",
        html="Our recruiting platform is powered by Greenhouse. Open jobs below.",
        allowed_hosts={"www.example.com"},
    )

    assert result == ()


def test_verified_cross_domain_redirect_requires_identity_and_career_confirmation() -> None:
    blocked = redirected_career_origin_candidate(
        source_url="https://www.example.com/careers",
        final_url="https://www.example.de/karriere/",
        allowed_hosts={"www.example.com"},
        employer_identity_confirmed=True,
        career_like_confirmed=False,
    )
    assert blocked is None

    accepted = redirected_career_origin_candidate(
        source_url="https://www.example.com/careers",
        final_url="https://www.example.de/karriere/?utm_source=old-domain",
        allowed_hosts={"www.example.com"},
        employer_identity_confirmed=True,
        career_like_confirmed=True,
    )

    assert accepted is not None
    assert accepted.candidate_url == "https://www.example.de/karriere"
    assert accepted.evidence_kind == "verified_career_redirect_transition"
    assert accepted.host_authority is False
    assert accepted.product_authority is False


def test_redirect_to_aggregator_never_becomes_origin_drift_candidate() -> None:
    result = redirected_career_origin_candidate(
        source_url="https://www.example.com/careers",
        final_url="https://www.indeed.com/cmp/example/jobs",
        allowed_hosts={"www.example.com"},
        employer_identity_confirmed=True,
        career_like_confirmed=True,
    )

    assert result is None
