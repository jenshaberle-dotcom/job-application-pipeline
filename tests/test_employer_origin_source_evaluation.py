from pathlib import Path

from scripts.evaluate_employer_origin_sources import (
    EmployerOriginTarget,
    FetchedPage,
    detect_ats_hints,
    evaluate_target,
    find_matched_terms,
    recommendation_for_evidence,
    run_evaluation,
    strip_html,
)


def test_strip_html_removes_script_and_normalizes_text() -> None:
    html = "<html><script>ignore me</script><body><h1>Data&nbsp;Engineer</h1></body></html>"

    assert strip_html(html) == "Data Engineer"


def test_matched_terms_support_phrase_and_token_matching() -> None:
    text = "Wir suchen Python Erfahrung und SQL Kenntnisse für eine moderne Data Platform."

    assert find_matched_terms(text, ("Python SQL", "Data Platform", "Big Data")) == (
        "Python SQL",
        "Data Platform",
    )


def test_detect_ats_hints_finds_successfactors_in_static_html() -> None:
    html = '<a href="https://example.successfactors.eu/career">Jobs</a>'
    text = "Jobs bei Beispiel GmbH"

    assert detect_ats_hints(html, text) == ("successfactors",)


def test_recommendation_distinguishes_ats_near_candidate() -> None:
    assert (
        recommendation_for_evidence(
            status_code=200,
            matched_terms=(),
            ats_hints=("successfactors",),
            possible_job_signal_count=10,
        )
        == "ats_near_candidate_manual_review"
    )


def test_evaluate_target_uses_injected_fetcher_without_network() -> None:
    target = EmployerOriginTarget(
        key="example",
        company_name="Example GmbH",
        source_family_candidate="employer_origin:example",
        source_type_candidate="employer_origin_career_site",
        url="https://example.test/jobs",
        validation_reason="unit test",
    )

    def fake_fetcher(_: EmployerOriginTarget, __: int) -> FetchedPage:
        return FetchedPage(
            status_code=200,
            final_url="https://example.test/jobs",
            html=(
                "<html><title>Example Jobs</title>"
                "<body>Data Engineer m/w/d SAP SuccessFactors</body></html>"
            ),
            html_bytes=90,
        )

    row = evaluate_target(target, fetcher=fake_fetcher)

    assert row.title == "Example Jobs"
    assert row.matched_terms == ("Data Engineer",)
    assert row.ats_hints == ("successfactors",)
    assert row.recommendation == "connector_candidate_after_manual_review"


def test_run_evaluation_writes_csv_and_manifest_without_network(tmp_path: Path) -> None:
    target = EmployerOriginTarget(
        key="example",
        company_name="Example GmbH",
        source_family_candidate="employer_origin:example",
        source_type_candidate="employer_origin_career_site",
        url="https://example.test/jobs",
        validation_reason="unit test",
    )

    def fake_fetcher(_: EmployerOriginTarget, __: int) -> FetchedPage:
        return FetchedPage(
            status_code=200,
            final_url="https://example.test/jobs",
            html="<html><title>Example</title><body>Remote Data Engineer personio</body></html>",
            html_bytes=80,
        )

    manifest = run_evaluation(
        export_dir=tmp_path,
        timeout_seconds=1,
        search_terms=("Data Engineer",),
        targets=(target,),
        fetcher=fake_fetcher,
    )

    assert manifest["database_writes"] is False
    assert manifest["detail_pages_fetched"] is False
    assert manifest["candidate_count"] == 1
    assert manifest["recommendation_counts"] == {"connector_candidate_after_manual_review": 1}
    assert (tmp_path / "employer_origin_source_validation.csv").exists()
    assert (tmp_path / "employer_origin_source_validation_manifest.json").exists()
