from src.search_intelligence.connector_feasibility import (
    OriginCandidate,
    ProbeFetchResult,
    classify_evidence_link,
    evaluate_connector_feasibility,
    extract_sample_job_urls,
    is_public_https_origin_url,
)


def test_rejects_aggregator_origin_url() -> None:
    assert not is_public_https_origin_url("https://www.stepstone.de/jobs/foo")


def test_accepts_public_https_career_url() -> None:
    assert is_public_https_origin_url("https://jobs.example-company.de/search")


def test_extracts_sample_job_urls_from_bounded_html() -> None:
    urls = extract_sample_job_urls(
        "https://example.com/careers",
        "<a href='/jobs/data-engineer'>Data Engineer</a><a href='/about'>About</a>",
    )
    assert urls == ("https://example.com/jobs/data-engineer",)


def test_does_not_count_assets_feeds_or_oembed_as_sample_jobs() -> None:
    urls = extract_sample_job_urls(
        "https://karriere.example.com/stellenangebote",
        """
        <a href='/favicon.svg'>Jobs favicon</a>
        <a href='/feed/'>Jobs feed</a>
        <a href='/comments/feed/'>Comments</a>
        <a href='/wp-json/oembed/1.0/embed?url=https://karriere.example.com/stellenangebote'>Embed</a>
        <a href='/assets/jobs.js'>Jobs script</a>
        """,
    )
    assert urls == ()


def test_does_not_count_social_press_root_or_career_context_as_sample_jobs() -> None:
    urls = extract_sample_job_urls(
        "https://karriere.example.com/stellenangebote",
        """
        <a href='https://www.facebook.com/example'>Facebook Jobs</a>
        <a href='https://www.instagram.com/example'>Instagram Karriere</a>
        <a href='https://www.example.com'>Home</a>
        <a href='/news-hub/news-presse/pressebilder'>Pressebilder</a>
        <a href='/karriere/schueler/ausbildung'>Ausbildung</a>
        <a href='/karriere/students/working_students'>Working Students</a>
        """,
    )
    assert urls == ()


def test_classifies_career_context_without_counting_it_as_structural_job_evidence() -> None:
    item = classify_evidence_link(
        "https://careers.example.com/jobs",
        "https://careers.example.com/students/working_students",
        "Working Students",
    )
    assert item.evidence_type == "career_context_evidence"


def test_evaluates_likely_feasible_with_structural_sample_job_evidence() -> None:
    candidate = OriginCandidate(
        candidate_id=1,
        company_key="example",
        company_name="Example AG",
        origin_url="https://example.com/karriere/jobs",
    )
    item = evaluate_connector_feasibility(
        candidate,
        fetch_result=ProbeFetchResult(
            final_url="https://example.com/karriere/jobs",
            http_status=200,
            body="<html><a href='/jobs/data-engineer'>Data Engineer</a></html>",
        ),
    )
    assert item.feasibility_status == "likely_feasible"
    assert item.decision == "continue_to_connector_build_planning"
    assert item.sample_job_count == 1
    assert item.job_detail_candidate_evidence_count == 1
    assert item.url_quality.status == "valid_probe_ready"


def test_reachable_asset_noise_is_not_likely_feasible() -> None:
    candidate = OriginCandidate(
        candidate_id=1,
        company_key="noise",
        company_name="Noise AG",
        origin_url="https://noise.example.com/karriere/jobs",
    )
    item = evaluate_connector_feasibility(
        candidate,
        fetch_result=ProbeFetchResult(
            final_url="https://noise.example.com/karriere/jobs",
            http_status=200,
            body="""
            <html>
              <a href='/favicon.svg'>Jobs icon</a>
              <a href='/feed/'>Jobs feed</a>
              <a href='/wp-json/oembed/1.0/embed'>Job embed</a>
            </html>
            """,
        ),
    )
    assert item.feasibility_status == "manual_review_required"
    assert item.sample_job_count == 0
    assert item.rejected_noise_count >= 3
    assert item.url_quality.status == "asset_noise_only"


def test_reachable_career_context_only_is_not_likely_feasible() -> None:
    candidate = OriginCandidate(
        candidate_id=1,
        company_key="hdi",
        company_name="HDI",
        origin_url="https://careers.example.com/jobs",
    )
    item = evaluate_connector_feasibility(
        candidate,
        fetch_result=ProbeFetchResult(
            final_url="https://careers.example.com/jobs",
            http_status=200,
            body="""
            <a href='/students/working_students'>Working Students</a>
            <a href='/pupils/vocational_training'>Vocational Training</a>
            """,
        ),
    )
    assert item.feasibility_status == "manual_review_required"
    assert item.career_context_evidence_count == 2
    assert item.structural_job_evidence_count == 0
    assert item.url_quality.status == "career_page_without_job_structure"


def test_unreachable_url_with_alternative_creates_repair_feedback() -> None:
    candidate = OriginCandidate(
        candidate_id=1,
        company_key="adesso",
        company_name="adesso SE",
        origin_url="https://www.adesso.de/de/karriere/jobs/index.jsp",
    )
    item = evaluate_connector_feasibility(
        candidate,
        fetch_result=ProbeFetchResult(
            final_url="https://www.adesso.de/de/karriere/jobs/index.jsp",
            http_status=404,
            body="<a href='https://www.adesso.de/de/karriere/jobs/index.html'>Jobs bei adesso</a>",
            error="HTTP Error 404",
        ),
    )
    assert item.feasibility_status == "manual_review_required"
    assert item.url_quality.status == "repair_candidate_detected"
    assert item.url_quality.code == "origin_url_repair_candidate_detected"
    assert item.url_quality.repair_candidate_url == "https://www.adesso.de/de/karriere/jobs/index.html"


def test_missing_origin_url_defers_until_url_available() -> None:
    candidate = OriginCandidate(candidate_id=1, company_key="rossmann", company_name="Rossmann", origin_url=None)
    item = evaluate_connector_feasibility(candidate)
    assert item.feasibility_status == "missing_origin_url"
    assert item.decision == "defer_until_origin_url_available"
    assert item.url_quality.status == "missing_origin_url"
