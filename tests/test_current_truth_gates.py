from src.connectors.enercity import (
    CandidateLink as EnercityCandidateLink,
    DetailPage as EnercityDetailPage,
    detail_supports_record as enercity_detail_supports_record,
    extract_candidate_links as extract_enercity_candidate_links,
)
from src.connectors.hdi import (
    CandidateLink as HdiCandidateLink,
    DetailPage as HdiDetailPage,
    detail_supports_record as hdi_detail_supports_record,
)
from src.connectors.relevance_terms import find_relevance_terms
from src.job_lifecycle_health import (
    COVERAGE_EXACT_DETAIL,
    OUTCOME_CLOSED,
    HealthClassification,
    HttpProbeResult,
    JobHealthTarget,
    classify_exact_detail,
)
from src.search_intelligence.vacancy_page_signals import (
    explicit_vacancy_closure_marker,
)


def test_short_relevance_terms_require_lexical_boundaries() -> None:
    assert find_relevance_terms("Power BI Data", ("bi", "data")) == ("bi", "data")
    assert find_relevance_terms("AI Engineer", ("ai",)) == ("ai",)
    assert find_relevance_terms("KI / UI", ("ki", "ui")) == ("ki", "ui")

    assert find_relevance_terms("mikrobiologisches Trinkwasserlabor", ("bi",)) == ()
    assert find_relevance_terms("detail page", ("ai",)) == ()


def test_long_relevance_terms_preserve_useful_compound_matching() -> None:
    assert find_relevance_terms("Datenanalyse und Datenqualität", ("daten",)) == (
        "daten",
    )


def test_enercity_lab_title_is_not_selected_from_bi_substring() -> None:
    html = (
        "<html><body>"
        "<a href='/karriere/jobsuche/"
        "bta-cta-uta-fuer-mikrobiologisches-trinkwasserlabor-J2026377'>"
        "BTA/CTA/UTA für mikrobiologisches Trinkwasserlabor Hannover"
        "</a>"
        "</body></html>"
    )

    candidates = extract_enercity_candidate_links(
        html,
        "https://www.enercity.de/karriere/jobsuche",
    )

    assert candidates == []


def _enercity_candidate() -> EnercityCandidateLink:
    return EnercityCandidateLink(
        url=(
            "https://www.enercity.de/karriere/jobsuche/"
            "operation-expert-process-data-und-automation-m-w-d-J2026362"
        ),
        path=(
            "/karriere/jobsuche/"
            "operation-expert-process-data-und-automation-m-w-d-J2026362"
        ),
        text="Operation Expert Process, Data und Automation Hannover",
        location_terms=("hannover",),
        profile_terms=("data",),
        recommendation="strong_listing_candidate_for_review",
        reason="fixture",
    )


def test_enercity_explicit_closed_detail_is_not_emitted_positive() -> None:
    candidate = _enercity_candidate()
    detail = EnercityDetailPage(
        url=candidate.url,
        final_url=candidate.url,
        status_code=200,
        title="Operation Expert Process, Data und Automation",
        text=(
            "Operation Expert Process, Data und Automation Hannover. "
            "This job is no longer available."
        ),
        html_bytes=100,
    )

    assert not enercity_detail_supports_record(candidate, detail)


def _hdi_candidate() -> HdiCandidateLink:
    url = "https://job.hdi.group/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/"
    return HdiCandidateLink(
        url=url,
        path="/job/Data-&-Analytics-Engineer-%28Long-Tail%29/720-en_US/",
        text="Data Analytics Engineer Hannover",
        location_terms=("hannover",),
        profile_terms=("data", "analytics"),
        recommendation="known_detail_candidate_from_gate_evidence",
        reason="fixture",
    )


def test_hdi_explicit_closed_detail_is_not_emitted_positive() -> None:
    candidate = _hdi_candidate()
    detail = HdiDetailPage(
        url=candidate.url,
        final_url=candidate.url,
        status_code=200,
        title="Data & Analytics Engineer (Long Tail)",
        text=(
            "Data & Analytics Engineer (Long Tail). "
            "You can't view this job because it's not available at this time."
        ),
        html_bytes=100,
    )

    assert not hdi_detail_supports_record(candidate, detail)


def test_explicit_vacancy_closure_marker_is_narrow() -> None:
    assert (
        explicit_vacancy_closure_marker(
            "You can't view this job because it's not available at this time."
        )
        == "job_not_available_at_this_time"
    )
    assert explicit_vacancy_closure_marker("Careers page. Job search unavailable.") is None


def _health_target() -> JobHealthTarget:
    url = "https://jobs.example.test/job/Data-Engineer/42"
    return JobHealthTarget(
        silver_job_id=42,
        raw_job_id=420,
        ingestion_run_id=10,
        source_name="example:origin",
        external_job_id="42",
        source_url=url,
        title="Data Engineer",
        canonical_source_type="employer_origin_career_site",
        raw_source_type="employer_origin_career_site",
    )


def test_2xx_explicit_closed_content_is_exact_detail_closure() -> None:
    target = _health_target()
    classification: HealthClassification = classify_exact_detail(
        target,
        HttpProbeResult(
            status_code=200,
            final_url=target.source_url,
            response_text=(
                "<title>Data Engineer</title>"
                "You can't view this job because it's not available at this time."
            ),
            redirect_count=0,
        ),
    )

    assert classification.outcome == OUTCOME_CLOSED
    assert classification.coverage == COVERAGE_EXACT_DETAIL
    assert (
        classification.evidence_reason
        == "explicit_vacancy_unavailable_on_exact_detail"
    )
    assert (
        classification.evidence["explicit_closure_marker"]
        == "job_not_available_at_this_time"
    )


def test_generic_2xx_title_mismatch_remains_unverifiable() -> None:
    target = _health_target()
    classification = classify_exact_detail(
        target,
        HttpProbeResult(
            status_code=200,
            final_url=target.source_url,
            response_text="Careers at Example — browse open roles",
            redirect_count=0,
        ),
    )

    assert classification.outcome == "unverifiable"
    assert classification.evidence_reason == "vacancy_title_not_confirmed_on_detail_page"
    assert classification.evidence["explicit_closure_marker"] is None
