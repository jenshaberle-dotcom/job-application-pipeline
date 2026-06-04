from __future__ import annotations

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    DetailEvidence,
    LinkCandidate,
    RepairOutcome,
    SourceCandidate,
    build_repair_outcome,
    concrete_job_detail_url,
    repair_report_lines,
)


def make_candidate() -> SourceCandidate:
    return SourceCandidate(
        id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/de/karriere/jobs",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="manual_review",
        risk_level="low",
    )


def fake_fetcher(url: str) -> tuple[str, str, int]:
    if url == "https://careers.hdi.group/de/karriere/jobs":
        return (
            """
            <html><body>
              <a href="/de/karriere/jobs/product-owner-data-platform">Product Owner Data Platform Hannover</a>
              <a href="/en/privacy">Privacy</a>
              <a href="/de/karriere/jobs">Jobs overview</a>
            </body></html>
            """,
            url,
            200,
        )

    if url == "https://careers.hdi.group/de/karriere/jobs/product-owner-data-platform":
        return (
            """
            <html>
              <title>Product Owner Data Platform</title>
              <body>Product Owner Data Platform in Hannover with Data Analytics and stakeholder work.</body>
            </html>
            """,
            url,
            200,
        )

    raise AssertionError(f"Unexpected URL: {url}")


def test_concrete_job_detail_url_rejects_overviews_and_legal_pages() -> None:
    assert concrete_job_detail_url("https://careers.hdi.group/de/karriere/jobs/product-owner-data-platform")
    assert not concrete_job_detail_url("https://careers.hdi.group/de/karriere/jobs")
    assert not concrete_job_detail_url("https://careers.hdi.group/en/privacy")


def test_build_repair_outcome_finds_and_validates_concrete_detail_page() -> None:
    outcome = build_repair_outcome(
        candidate=make_candidate(),
        gates={},
        profile_terms=("product owner", "data", "analytics"),
        location_terms=("hannover", "remote"),
        max_seed_pages=3,
        max_detail_pages=3,
        enable_search_discovery=False,
        fetcher=fake_fetcher,
    )

    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert outcome.stop_reason is None
    assert len(outcome.details) == 1
    assert outcome.details[0].url.endswith("/product-owner-data-platform")
    assert outcome.evidence["repair_attempted"] is True
    assert outcome.evidence["repair_boundary"]["bronze_persistence"] is False
    assert outcome.evidence["repair_boundary"]["raw_html_persisted"] is False


def test_build_repair_outcome_stops_when_no_concrete_details_are_found() -> None:
    def empty_fetcher(url: str) -> tuple[str, str, int]:
        return (
            """
            <html><body>
              <a href="/en/privacy">Privacy</a>
              <a href="/de/karriere/jobs">Jobs overview</a>
            </body></html>
            """,
            url,
            200,
        )

    outcome = build_repair_outcome(
        candidate=make_candidate(),
        gates={},
        profile_terms=("product owner", "data"),
        location_terms=("hannover",),
        max_seed_pages=3,
        max_detail_pages=3,
        enable_search_discovery=False,
        fetcher=empty_fetcher,
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"
    assert outcome.stop_reason == "multi-origin repair found no concrete detail pages with profile and target/remote signals"


def test_repair_report_lines_are_actionable() -> None:
    outcome = RepairOutcome(
        gate_status="passed",
        decision="continue",
        stop_reason=None,
        details=(
            DetailEvidence(
                url="https://careers.hdi.group/de/karriere/jobs/product-owner-data-platform",
                final_url="https://careers.hdi.group/de/karriere/jobs/product-owner-data-platform",
                status_code=200,
                title="Product Owner Data Platform",
                profile_terms=("product owner", "data"),
                location_terms=("hannover",),
                html_bytes=123,
                reason="unit test",
            ),
        ),
        rejected_urls=(),
        requested_urls=(),
        evidence={},
    )

    text = "\n".join(repair_report_lines(make_candidate(), outcome))

    assert "detail_evidence_gate: passed / continue" in text
    assert "repaired_detail_count: 1" in text
    assert "rerun connector_candidate_agent" in text



def test_concrete_job_detail_url_accepts_successfactors_like_hdi_pattern() -> None:
    assert concrete_job_detail_url("https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/")


def test_build_repair_outcome_uses_search_discovery_for_hdi_job_host() -> None:
    search_html = """
    <html><body>
      <a href="https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/">HDI Data Analytics Hannover</a>
    </body></html>
    """
    detail_url = "https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/"

    def search_fetcher(query: str) -> tuple[str, str, int]:
        assert "HDI" in query or "hdi" in query
        return search_html, "https://html.duckduckgo.com/html/?q=hdi", 200

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://careers.hdi.group/de/karriere/jobs":
            return "<html><body>No detail links here.</body></html>", url, 200
        if url == detail_url:
            return (
                """
                <html>
                  <title>Data & Analytics Engineer (Long Tail)</title>
                  <body>Hannover Data Analytics SQL Python Datenpipelines Datenarchitektur.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=make_candidate(),
        gates={},
        profile_terms=("data", "analytics", "sql", "python"),
        location_terms=("hannover", "remote"),
        max_seed_pages=12,
        max_detail_pages=8,
        enable_search_discovery=True,
        max_search_queries=2,
        max_search_results=4,
        fetcher=fetcher,
        search_fetcher=search_fetcher,
    )

    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert outcome.details[0].final_url == detail_url
    assert outcome.evidence["decision_taxonomy"] == "accepted"
    assert outcome.evidence["confidence_score"] == 0.96
    assert outcome.evidence["search_discovery_enabled"] is True
    assert outcome.evidence["requested_search_queries"]


def test_build_repair_outcome_reports_implementation_gap_when_detail_candidate_cannot_be_validated() -> None:
    detail_url = "https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/"

    def search_fetcher(query: str) -> tuple[str, str, int]:
        return f'<html><body><a href="{detail_url}">HDI Data Analytics Hannover</a></body></html>', "https://search.example", 200

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://careers.hdi.group/de/karriere/jobs":
            return "<html><body>No detail links here.</body></html>", url, 200
        if url == detail_url:
            return "<html><title>Data & Analytics Engineer</title><body>Data Analytics SQL Python</body></html>", url, 200
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=make_candidate(),
        gates={},
        profile_terms=("data", "analytics", "sql", "python"),
        location_terms=("hannover",),
        max_seed_pages=12,
        max_detail_pages=8,
        enable_search_discovery=True,
        max_search_queries=1,
        max_search_results=2,
        fetcher=fetcher,
        search_fetcher=search_fetcher,
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.evidence["decision_taxonomy"] == "implementation_gap"
    assert outcome.evidence["confidence_score"] == 0.82
    assert "plausible job-detail candidates" in (outcome.stop_reason or "")
    assert any(item["url"] == detail_url for item in outcome.evidence["detail_assessments"])
