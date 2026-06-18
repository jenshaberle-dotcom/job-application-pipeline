from __future__ import annotations

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    DetailEvidence,
    RepairOutcome,
    SourceCandidate,
    StructuredSearchResult,
    build_repair_outcome,
    concrete_job_detail_url,
    extract_embedded_detail_url_candidates,
    repair_report_lines,
    requested_seed_urls,
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

def test_extract_embedded_detail_urls_from_json_like_portal_state() -> None:
    html = """
    <html><script>
      window.__jobs = [{"url":"\\/job\\/Hannover-IT-Cloud-Engineer-AWS\\/1325613255\\/"}];
    </script></html>
    """

    links = extract_embedded_detail_url_candidates(html, "https://jobs.hannover-re.com/")

    assert links == [("https://jobs.hannover-re.com/job/Hannover-IT-Cloud-Engineer-AWS/1325613255/", "embedded detail URL candidate")]


def test_build_repair_outcome_uses_embedded_detail_urls_from_dynamic_listing() -> None:
    detail_url = "https://jobs.hannover-re.com/job/Hannover-IT-Cloud-Engineer-AWS/1325613255/"
    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.hannover-re.com/":
            return (
                """
                <html><body>
                  <script>window.__jobs = [{"url":"\\/job\\/Hannover-IT-Cloud-Engineer-AWS\\/1325613255\\/"}];</script>
                </body></html>
                """,
                url,
                200,
            )
        if url == detail_url:
            return (
                """
                <html>
                  <title>IT Cloud Engineer AWS</title>
                  <body>Hannover AWS cloud platform automation Python Terraform Data infrastructure.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "python", "cloud"),
        location_terms=("hannover", "remote"),
        max_seed_pages=3,
        max_detail_pages=3,
        enable_search_discovery=False,
        fetcher=fetcher,
    )

    assert outcome.gate_status == "passed"
    assert outcome.details[0].final_url == detail_url
    assert outcome.evidence["detail_link_discovery_version"] == "DETAIL-004B"
    assert outcome.evidence["embedded_detail_url_extraction_enabled"] is True



def test_requested_seed_urls_does_not_replay_rejected_gate_urls() -> None:
    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )
    gates = {
        "detail_evidence_gate": {
            "evidence": {
                "rejected_urls": [
                    "https://html.duckduckgo.com/html/ :: domain_not_plausible",
                    "https://jobs.hannover-re.com/home :: not_concrete_job_detail_url",
                    "https://d1qnw94usouwub.cloudfront.net/asset/document_x :: domain_not_plausible",
                    "javascript:void(0) :: domain_not_plausible",
                ],
                "candidate_links": [
                    {"url": "https://jobs.hannover-re.com/job/Hannover-IT-Cloud-Engineer-AWS/1325613255/"},
                    {"url": "https://jobs.hannover-re.com/home"},
                ],
            }
        }
    }

    seeds = requested_seed_urls(candidate, gates)

    assert seeds == (
        "https://jobs.hannover-re.com/",
        "https://jobs.hannover-re.com/job/Hannover-IT-Cloud-Engineer-AWS/1325613255/",
    )
    assert not any("::" in seed for seed in seeds)
    assert not any("%20" in seed for seed in seeds)
    assert not any("duckduckgo" in seed or "cloudfront" in seed for seed in seeds)


def test_build_repair_outcome_does_not_refetch_audit_rejection_strings() -> None:
    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )
    gates = {
        "detail_evidence_gate": {
            "evidence": {
                "rejected_urls": [
                    "https://jobs.hannover-re.com/ :: not_concrete_job_detail_url",
                    "https://jobs.hannover-re.com/home :: not_concrete_job_detail_url",
                    "https://html.duckduckgo.com/html/ :: domain_not_plausible",
                ]
            }
        }
    }
    requested: list[str] = []

    def fetcher(url: str) -> tuple[str, str, int]:
        requested.append(url)
        assert "::" not in url
        assert "%20" not in url
        return "<html><body>No detail links here.</body></html>", url, 200

    outcome = build_repair_outcome(
        candidate=candidate,
        gates=gates,
        profile_terms=("data",),
        location_terms=("hannover",),
        max_seed_pages=3,
        max_detail_pages=1,
        enable_search_discovery=False,
        fetcher=fetcher,
    )

    assert "https://jobs.hannover-re.com/" in requested
    assert "https://jobs.hannover-re.com/home" not in outcome.requested_urls
    assert not any("::" in url or "%20" in url for url in requested)
    assert not any("duckduckgo" in url for url in requested)
    assert outcome.evidence["detail_link_discovery_version"] == "DETAIL-004B"

def test_build_repair_outcome_search_queries_use_real_candidate_host_before_synthetic_hosts() -> None:
    captured_queries: list[str] = []

    def search_fetcher(query: str) -> tuple[str, str, int]:
        captured_queries.append(query)
        return "<html><body>No results</body></html>", "https://html.duckduckgo.com/html/", 200

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.hannover-re.com/":
            return "<html><body>No detail links here.</body></html>", url, 200
        raise AssertionError(f"Unexpected URL: {url}")

    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data",),
        location_terms=("hannover",),
        max_seed_pages=1,
        max_detail_pages=1,
        enable_search_discovery=True,
        max_search_queries=4,
        max_search_results=2,
        fetcher=fetcher,
        search_fetcher=search_fetcher,
    )

    assert captured_queries[0] == "site:jobs.hannover-re.com/job data hannover"
    assert any(query.startswith("site:jobs.hannover-re.com") for query in captured_queries)
    assert not any("hannover_ruck.group" in query for query in captured_queries)


def test_build_repair_outcome_keeps_rejected_url_history_out_of_seed_budget_for_search_details() -> None:
    detail_url = "https://jobs.eon.com/job/Hannover-Machine-Learning-Engineer-m_w_d-Predictive-Maintenance-MLOps/244635"
    candidate = SourceCandidate(
        id=37,
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        candidate_url="https://jobs.eon.com/en",
        source_name_candidate="e_on_grid_solutions:hannover",
        source_family_candidate="e_on_grid_solutions",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )
    gates = {
        "detail_evidence_gate": {
            "evidence": {
                "rejected_urls": [
                    "https://html.duckduckgo.com/html/ :: domain_not_plausible",
                    "https://www.eon.com/en/energy-grids.html :: not_concrete_job_detail_url",
                    "https://www.eon.com/en/investor-relations.html :: not_concrete_job_detail_url",
                    "https://www.eon.com/en/about-us/careers.html :: not_concrete_job_detail_url",
                    "https://jobs.eon.com/privacy :: not_concrete_job_detail_url",
                    "https://www.linkedin.com/company/e-on/ :: domain_not_plausible",
                ]
            }
        }
    }
    requested: list[str] = []

    def search_fetcher(query: str) -> tuple[str, str, int]:
        return f'<html><body><a href="{detail_url}">Machine Learning Engineer Hannover Data MLOps</a></body></html>', "https://html.duckduckgo.com/html/", 200

    def fetcher(url: str) -> tuple[str, str, int]:
        requested.append(url)
        if url == "https://jobs.eon.com/en":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url == detail_url:
            return (
                """
                <html>
                  <title>Machine Learning Engineer Predictive Maintenance & MLOps</title>
                  <body>Hannover Data Python PySpark SQL Databricks Hybrid E.ON Grid Solutions GmbH.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates=gates,
        profile_terms=("data", "python", "sql", "databricks"),
        location_terms=("hannover", "remote"),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=True,
        max_search_queries=1,
        max_search_results=2,
        fetcher=fetcher,
        search_fetcher=search_fetcher,
    )

    assert outcome.gate_status == "passed"
    assert detail_url in requested
    assert not any("duckduckgo" in url or "linkedin" in url for url in requested)
    assert outcome.evidence["detail_link_discovery_version"] == "DETAIL-004B"



def test_build_repair_outcome_uses_tavily_structured_results_as_detail_candidates() -> None:
    detail_url = "https://jobs.hannover-re.com/job/Hannover-IT-Cloud-Engineer-AWS/1325613255/"
    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )
    captured_queries: list[str] = []

    def tavily_fetcher(query: str, *, max_results: int) -> tuple[StructuredSearchResult, ...]:
        captured_queries.append(query)
        return (
            StructuredSearchResult(
                url=detail_url,
                title="IT Cloud Engineer AWS",
                snippet="Hannover Cloud Python Data Plattform",
                query=query,
                provider="tavily",
            ),
        )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.hannover-re.com/":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url == detail_url:
            return (
                """
                <html>
                  <title>IT Cloud Engineer AWS</title>
                  <body>Hannover Cloud Python Data Plattform AWS Terraform.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "python", "cloud"),
        location_terms=("hannover", "remote"),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=True,
        search_provider="tavily",
        max_search_queries=1,
        max_search_results=3,
        fetcher=fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    assert captured_queries == ["site:jobs.hannover-re.com/job data hannover"]
    assert outcome.gate_status == "passed"
    assert outcome.details[0].final_url == detail_url
    assert outcome.evidence["search_provider"] == "tavily"
    assert outcome.evidence["detail_link_discovery_version"] == "DETAIL-004B"
    assert any(item["url"] == detail_url for item in outcome.evidence["candidate_links"])
    assert outcome.evidence["preliminary_detail_candidates"] == outcome.evidence["candidate_links"]
    assert outcome.evidence["authoritative_detail_assessments"] == outcome.evidence["detail_assessments"]
    assert outcome.evidence["supported_detail_evidence"] == outcome.evidence["supported_details"]
    assert "not gate-pass evidence" in outcome.evidence["report_contract"]["preliminary_detail_candidates"]


def test_build_repair_outcome_keeps_tavily_as_candidate_finder_not_gate_decider() -> None:
    detail_url = "https://jobs.eon.com/job/Machine-Learning-Engineer-m_w_d/244635"
    candidate = SourceCandidate(
        id=37,
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        candidate_url="https://jobs.eon.com/en",
        source_name_candidate="e_on_grid_solutions:hannover",
        source_family_candidate="e_on_grid_solutions",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def tavily_fetcher(query: str, *, max_results: int) -> tuple[StructuredSearchResult, ...]:
        return (
            StructuredSearchResult(
                url=detail_url,
                title="Machine Learning Engineer",
                snippet="Data MLOps",
                query=query,
                provider="tavily",
            ),
        )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.eon.com/en":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url == detail_url:
            return "<html><title>Machine Learning Engineer</title><body>Python MLOps</body></html>", url, 200
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("python", "mlops"),
        location_terms=("hannover",),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=True,
        search_provider="tavily",
        max_search_queries=1,
        max_search_results=3,
        fetcher=fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.evidence["decision_taxonomy"] == "implementation_gap"
    assert outcome.evidence["search_provider"] == "tavily"
    assert outcome.evidence["candidate_links"][0]["url"] == detail_url
    assert not outcome.details



def test_detail_validation_rejects_cross_domain_supported_details_even_with_matching_signals() -> None:
    search_url = "https://jobs.eon.com/job/Data-Engineer-Energy-Networks-w_d_m-Salzgitter/244547"
    external_url = "https://jobs.avacon.de/de/job/Data-Engineer-Energy-Networks-w_d_m-Salzgitter/244547"
    candidate = SourceCandidate(
        id=37,
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        candidate_url="https://jobs.eon.com/en",
        source_name_candidate="e_on_grid_solutions:hannover",
        source_family_candidate="e_on_grid_solutions",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def tavily_fetcher(query: str, *, max_results: int) -> tuple[StructuredSearchResult, ...]:
        return (
            StructuredSearchResult(
                url=search_url,
                title="Data Engineer Energy Networks",
                snippet="Data Python Hannover remote hybrid",
                query=query,
                provider="tavily",
            ),
        )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.eon.com/en":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url == search_url:
            return (
                "<html><title>Data Engineer</title><body>Data Python Hannover Remote Hybrid</body></html>",
                external_url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "python"),
        location_terms=("hannover", "remote", "hybrid"),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=True,
        search_provider="tavily",
        max_search_queries=1,
        max_search_results=3,
        fetcher=fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.evidence["decision_taxonomy"] == "manual_review_required"
    assert any("domain_not_plausible" in item for item in outcome.rejected_urls)
    assert not outcome.evidence["details"]


def test_hannover_employer_brand_does_not_count_as_target_location_signal() -> None:
    detail_url = "https://jobs.hannover-re.com/job/London-Junior-Data-Analyst-Apprenticeship-ENG-EC3V-0BG/1352591255"
    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def tavily_fetcher(query: str, *, max_results: int) -> tuple[StructuredSearchResult, ...]:
        return (
            StructuredSearchResult(
                url=detail_url,
                title="Junior Data Analyst Apprenticeship | hannoverre",
                snippet="Hannover Re seeks a Junior Data Analyst in London.",
                query=query,
                provider="tavily",
            ),
        )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.hannover-re.com/":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url == detail_url:
            return (
                """
                <html>
                  <title>Junior Data Analyst Apprenticeship Job Details | hannoverre</title>
                  <body>Hannover Re is hiring a Junior Data Analyst Apprenticeship in London.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "analyst"),
        location_terms=("hannover",),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=True,
        search_provider="tavily",
        max_search_queries=1,
        max_search_results=3,
        fetcher=fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.evidence["decision_taxonomy"] == "implementation_gap"
    assert outcome.evidence["detail_assessments"][0]["signals"]["location_terms"] == []
    assert not outcome.details




def test_hannover_brand_in_phrase_does_not_count_as_location_context() -> None:
    detail_url = "https://jobs.hannover-re.com/job/Orlando-VP%2C-Actuary-FL-32801/1345906455"
    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def tavily_fetcher(query: str, *, max_results: int) -> tuple[StructuredSearchResult, ...]:
        return (
            StructuredSearchResult(
                url=detail_url,
                title="VP, Actuary - Hannover Re - Job Portal",
                snippet="Hannover Life Reassurance Company is hiring talented candidates for Orlando.",
                query=query,
                provider="tavily",
            ),
        )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.hannover-re.com/":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url == detail_url:
            return (
                """
                <html>
                  <title>VP, Actuary - Hannover Re - Job Portal</title>
                  <body>Hannover Life Reassurance Company is hiring a VP, Actuary in Orlando, FL. Data analytics exposure.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "analytics"),
        location_terms=("hannover",),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=True,
        search_provider="tavily",
        max_search_queries=1,
        max_search_results=3,
        fetcher=fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    assert outcome.gate_status == "manual_review_required"
    assert outcome.evidence["decision_taxonomy"] == "implementation_gap"
    assert outcome.evidence["detail_assessments"][0]["signals"]["location_terms"] == []
    assert not outcome.details


def test_hannover_in_url_path_still_counts_for_hannover_re() -> None:
    detail_url = "https://jobs.hannover-re.com/job/Hannover-Underwriterin-Lateinamerikanischer-Markt/1167988855"
    candidate = SourceCandidate(
        id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        candidate_url="https://jobs.hannover-re.com/",
        source_name_candidate="hannover_ruck:hannover",
        source_family_candidate="hannover_ruck",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def tavily_fetcher(query: str, *, max_results: int) -> tuple[StructuredSearchResult, ...]:
        return (
            StructuredSearchResult(
                url=detail_url,
                title="Underwriter:in Lateinamerikanischer Markt",
                snippet="Standort Hannover. Data Science, Mathematik und Python.",
                query=query,
                provider="tavily",
            ),
        )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.hannover-re.com/":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url == detail_url:
            return (
                """
                <html>
                  <title>Underwriter:in Lateinamerikanischer Markt</title>
                  <body>Standort Hannover. Data Science, Mathematik und Python.</body>
                </html>
                """,
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "python"),
        location_terms=("hannover",),
        max_seed_pages=2,
        max_detail_pages=2,
        enable_search_discovery=True,
        search_provider="tavily",
        max_search_queries=1,
        max_search_results=3,
        fetcher=fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    assert outcome.gate_status == "passed"
    assert outcome.details[0].location_terms == ("hannover",)

def test_detail_validation_deduplicates_equivalent_detail_urls() -> None:
    detail_url = "https://jobs.eon.com/de/eon-gridsolutions/job/Machine-Learning-Engineer-m_w_d-Predictive-Maintenance-MLOps-Hannover/244635"
    slash_url = detail_url + "/"
    candidate = SourceCandidate(
        id=37,
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        candidate_url="https://jobs.eon.com/en",
        source_name_candidate="e_on_grid_solutions:hannover",
        source_family_candidate="e_on_grid_solutions",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="low",
    )

    def tavily_fetcher(query: str, *, max_results: int) -> tuple[StructuredSearchResult, ...]:
        return (
            StructuredSearchResult(
                url=detail_url,
                title="Machine Learning Engineer",
                snippet="Data Python Hannover Hybrid",
                query=query,
                provider="tavily",
            ),
            StructuredSearchResult(
                url=slash_url,
                title="Machine Learning Engineer duplicate",
                snippet="Data Python Hannover Hybrid",
                query=query,
                provider="tavily",
            ),
        )

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == "https://jobs.eon.com/en":
            return "<html><body>No static detail links here.</body></html>", url, 200
        if url in {detail_url, slash_url}:
            return (
                """
                <html>
                  <title>Machine Learning Engineer</title>
                  <body>Standort Hannover. Data Python SQL Hybrid.</body>
                </html>
                """,
                url.rstrip("/"),
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    outcome = build_repair_outcome(
        candidate=candidate,
        gates={},
        profile_terms=("data", "python", "sql"),
        location_terms=("hannover", "hybrid"),
        max_seed_pages=3,
        max_detail_pages=3,
        enable_search_discovery=True,
        search_provider="tavily",
        max_search_queries=1,
        max_search_results=3,
        fetcher=fetcher,
        tavily_fetcher=tavily_fetcher,
    )

    assert outcome.gate_status == "passed"
    assert len(outcome.details) == 1
    assert outcome.evidence["search_budget_observability"]["estimated_provider_credit_count"] == 1
