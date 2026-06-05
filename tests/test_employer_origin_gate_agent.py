from __future__ import annotations

import argparse

from scripts.run_employer_origin_gate_agent import (
    GateOutcome,
    defensive_preview_gate,
    has_disallowed_url_shape,
    parse_same_domain_job_links,
    postfetch_risk_gate,
    technical_reachability_gate,
    relevance_gate,
    scope_gate,
    source_discovery_gate,
)
from scripts.run_employer_origin_gate_agent import FetchResult


def test_url_shape_blocks_login_like_sources() -> None:
    assert has_disallowed_url_shape("ftp://example.com/jobs") == "candidate URL must use http or https"
    assert has_disallowed_url_shape("https://example.com/login/jobs") == "candidate URL appears to require authentication"
    assert has_disallowed_url_shape("https://sso.example.com/jobs") == "candidate URL appears to require authentication"
    assert has_disallowed_url_shape("https://example.com/jobs?auth=1") == "candidate URL appears to require authentication"
    assert has_disallowed_url_shape("https://example.com/jobs") is None


def test_url_shape_does_not_match_auth_tokens_inside_company_names() -> None:
    assert has_disallowed_url_shape("https://www.adesso.de/de/karriere/jobs/index.html") is None
    assert has_disallowed_url_shape("https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer-Databricks-%28all-genders%29-NW-52070/1145683555/") is None


def test_source_discovery_gate_stops_on_invalid_url_shape() -> None:
    args = argparse.Namespace(candidate_url="ftp://example.com/jobs")

    outcome = source_discovery_gate(args)

    assert outcome.gate_status == "failed"
    assert outcome.decision == "abort_documented"
    assert outcome.stop_reason == "candidate URL must use http or https"


def test_same_domain_job_link_extraction_is_bounded_and_source_local() -> None:
    html = """
    <html>
      <head><title>Jobs</title></head>
      <body>
        <a href="/de/karriere/offene-stellen/hannover/product-owner">PO</a>
        <a href="https://example.com/jobs/data-engineer">Data</a>
        <a href="https://other.example/jobs/nope">Other</a>
        <a href="/about">About</a>
      </body>
    </html>
    """

    links = parse_same_domain_job_links(
        requested_url="https://example.com/careers",
        final_url="https://example.com/careers",
        body=html,
        max_links=1,
    )

    assert links == ("https://example.com/de/karriere/offene-stellen/hannover/product-owner",)


def test_job_link_extraction_allows_related_employer_job_host() -> None:
    html = """
    <html>
      <body>
        <a href="https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer-Databricks-%28all-genders%29-NW-52070/1145683555/">Data Engineer</a>
        <a href="https://unrelated-example.com/jobs/data-engineer">Unrelated</a>
      </body>
    </html>
    """

    links = parse_same_domain_job_links(
        requested_url="https://www.adesso.de/de/karriere/jobs/index.html",
        final_url="https://www.adesso.de/de/karriere/jobs/index.html",
        body=html,
        max_links=5,
        source_family_candidate="adesso",
    )

    assert links == (
        "https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer-Databricks-%28all-genders%29-NW-52070/1145683555/",
    )


def test_scope_gate_requires_single_listing_page_for_agent_mvp() -> None:
    args = argparse.Namespace(
        max_listing_pages=2,
        max_preview_links=25,
        source_name_candidate="example:hannover",
        source_family_candidate="example",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
    )

    outcome = scope_gate(args)

    assert outcome.gate_status == "failed"
    assert outcome.decision == "abort_documented"
    assert "one listing page" in outcome.stop_reason


def test_defensive_preview_gate_requires_job_like_same_domain_links() -> None:
    fetch = FetchResult(
        requested_url="https://example.com/jobs",
        final_url="https://example.com/jobs",
        status_code=200,
        response_bytes=100,
        title="Jobs",
        text="jobs",
        same_domain_job_links=(),
    )

    outcome = defensive_preview_gate(fetch)

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"


def test_relevance_gate_passes_with_profile_and_location_evidence() -> None:
    args = argparse.Namespace(
        profile_terms=["product owner", "sql"],
        target_location="hannover",
        source_target_candidate="hannover",
    )
    fetch = FetchResult(
        requested_url="https://example.com/jobs",
        final_url="https://example.com/jobs",
        status_code=200,
        response_bytes=100,
        title="Jobs",
        text="Product Owner in Hannover with SQL",
        same_domain_job_links=("https://example.com/jobs/product-owner",),
    )

    outcome = relevance_gate(args, fetch)

    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert outcome.evidence["profile_hits"] == ["product owner", "sql"]
    assert outcome.evidence["location_hits"] == ["hannover"]


def test_gate_outcome_shape_is_explicit() -> None:
    outcome = GateOutcome(
        gate_name="risk_gate",
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={"finding": "ok"},
    )

    assert outcome.gate_name == "risk_gate"
    assert outcome.evidence == {"finding": "ok"}


def test_technical_reachability_404_is_classified_as_recoverable_url_problem() -> None:
    fetch = FetchResult(
        requested_url="https://db.jobs/de-de/jobs",
        final_url="https://db.jobs/de-de/jobs",
        status_code=404,
        response_bytes=100,
        title="Not Found",
        text="",
        same_domain_job_links=(),
    )

    outcome = technical_reachability_gate(fetch)

    assert outcome.gate_status == "failed"
    assert outcome.decision == "abort_documented"
    assert outcome.evidence["stop_category"] == "recoverable_url_problem"
    assert outcome.evidence["terminal"] is False


def test_postfetch_risk_gate_does_not_abort_on_weak_captcha_markers_on_reachable_page() -> None:
    fetch = FetchResult(
        requested_url="https://karriere.ratiodata.de/stellenangebote",
        final_url="https://karriere.ratiodata.de/stellenangebote/",
        status_code=200,
        response_bytes=105542,
        title="Stellenangebote – Ratiodata",
        text="Karriere Stellenangebote recaptcha captcha",
        same_domain_job_links=("https://karriere.ratiodata.de/stellenangebote/data-engineer",),
    )

    outcome = postfetch_risk_gate(fetch)

    assert outcome is not None
    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"
    assert outcome.evidence["stop_category"] == "risk_marker_review"
    assert outcome.evidence["terminal"] is False


def test_postfetch_risk_gate_aborts_on_confirmed_access_risk_markers() -> None:
    fetch = FetchResult(
        requested_url="https://example.com/jobs",
        final_url="https://example.com/jobs",
        status_code=403,
        response_bytes=200,
        title="Access Denied",
        text="Access denied bot detection",
        same_domain_job_links=(),
    )

    outcome = postfetch_risk_gate(fetch)

    assert outcome is not None
    assert outcome.gate_status == "failed"
    assert outcome.decision == "abort_documented"
    assert outcome.evidence["stop_category"] == "terminal_access_risk"
    assert outcome.evidence["terminal"] is True
