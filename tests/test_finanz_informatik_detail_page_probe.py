from pathlib import Path

from scripts.preview_finanz_informatik_detail_page_probe import (
    FetchedPage,
    ListingCandidate,
    evaluate_detail,
    load_listing_candidates,
    run_probe,
    strip_html,
)


def test_strip_html_removes_script_and_normalizes_text() -> None:
    html = "<html><script>ignore</script><body><h1>Product&nbsp;Owner</h1></body></html>"

    assert strip_html(html) == "Product Owner"


def test_load_listing_candidates_keeps_only_hannover_detail_candidates(tmp_path: Path) -> None:
    csv_path = tmp_path / "candidates.csv"
    csv_path.write_text(
        """source_url,candidate_url,candidate_path,location_signal,profile_terms,recommendation,reason,detail_fetch_needed_later
https://example.test,https://example.test/hannover/product-owner,/hannover/product-owner,hannover,product owner,strong_listing_candidate_for_review,strong,true
https://example.test,https://example.test/frankfurt/business-analyst,/frankfurt/business-analyst,frankfurt,business-analyst,defer_non_target_location_without_remote_signal,defer,false
https://example.test,https://example.test/hannover/software,/hannover/software,hannover,,job_candidate_low_profile_signal,low,true
""",
        encoding="utf-8",
    )

    candidates = load_listing_candidates(csv_path, max_detail_pages=3)

    assert [candidate.candidate_url for candidate in candidates] == [
        "https://example.test/hannover/product-owner",
        "https://example.test/hannover/software",
    ]


def test_evaluate_detail_detects_profile_and_location_signals() -> None:
    candidate = ListingCandidate(
        source_url="https://example.test/listing",
        candidate_url="https://example.test/detail",
        candidate_path="/detail",
        listing_recommendation="strong_listing_candidate_for_review",
        listing_location_signal="hannover",
        listing_profile_terms=("product owner",),
        listing_reason="unit test",
    )
    page = FetchedPage(
        source_url="https://example.test/detail",
        status_code=200,
        final_url="https://example.test/detail",
        html="<html><title>Product Owner</title><body>Product Owner Hannover hybrid SQL</body></html>",
        html_bytes=90,
    )

    row = evaluate_detail(candidate, page)

    assert row.page_title == "Product Owner"
    assert "product owner" in row.matched_profile_terms
    assert "hannover" in row.matched_location_terms
    assert "hybrid" in row.matched_location_terms
    assert row.recommendation == "detail_candidate_supports_future_preview"


def test_run_probe_writes_exports_without_live_network(tmp_path: Path) -> None:
    csv_path = tmp_path / "candidates.csv"
    csv_path.write_text(
        """source_url,candidate_url,candidate_path,location_signal,profile_terms,recommendation,reason,detail_fetch_needed_later
https://example.test,https://example.test/hannover/product-owner,/hannover/product-owner,hannover,product owner,strong_listing_candidate_for_review,strong,true
""",
        encoding="utf-8",
    )

    def fake_fetcher(url: str, _: int) -> FetchedPage:
        return FetchedPage(
            source_url=url,
            status_code=200,
            final_url=url,
            html="<html><title>Product Owner</title><body>Product Owner Hannover remote</body></html>",
            html_bytes=80,
        )

    manifest = run_probe(
        candidates_csv=csv_path,
        export_dir=tmp_path / "exports",
        max_detail_pages=3,
        timeout_seconds=1,
        fetcher=fake_fetcher,
    )

    assert manifest["database_writes"] is False
    assert manifest["raw_html_persisted"] is False
    assert manifest["connector_implemented"] is False
    assert manifest["request_count"] == 1
    assert manifest["recommendation_counts"] == {
        "detail_candidate_supports_future_preview": 1
    }
    assert (tmp_path / "exports" / "finanz_informatik_detail_page_probe.csv").exists()
    assert (tmp_path / "exports" / "finanz_informatik_detail_page_probe_manifest.json").exists()
    assert (tmp_path / "exports" / "finanz_informatik_detail_page_probe_review.md").exists()


def test_detail_exclusion_terms_ignore_global_navigation_noise() -> None:
    candidate = ListingCandidate(
        source_url="https://example.test/listing",
        candidate_url="https://example.test/hannover/product-owner",
        candidate_path="/hannover/product-owner",
        listing_recommendation="strong_listing_candidate_for_review",
        listing_location_signal="hannover",
        listing_profile_terms=("product owner",),
        listing_reason="unit test",
    )
    page = FetchedPage(
        source_url="https://example.test/hannover/product-owner",
        status_code=200,
        final_url="https://example.test/hannover/product-owner",
        html=(
            "<html><title>Product Owner Hannover</title>"
            "<body><main>Product Owner Hannover hybrid SQL</main>"
            "<nav>Duales Studium Ausbildung Trainee</nav></body></html>"
        ),
        html_bytes=140,
    )

    row = evaluate_detail(candidate, page)

    assert row.matched_exclusion_terms == ()
    assert row.recommendation == "detail_candidate_supports_future_preview"

