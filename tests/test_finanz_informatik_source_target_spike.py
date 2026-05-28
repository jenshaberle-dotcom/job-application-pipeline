from pathlib import Path

from scripts.preview_finanz_informatik_source_target_spike import (
    ExtractedLink,
    FetchedPage,
    candidate_from_link,
    classify_path,
    extract_links,
    recommendation_for_candidate,
    run_spike,
)


def test_extract_links_normalizes_relative_links() -> None:
    html = '<a href="/de/karriere/offene-stellen/hannover/data-engineer-m-w-d">Data Engineer</a>'

    links = extract_links(html, "https://www.f-i.de/de/karriere/offene-stellen")

    assert len(links) == 1
    assert links[0].absolute_url == "https://www.f-i.de/de/karriere/offene-stellen/hannover/data-engineer-m-w-d"
    assert links[0].text == "Data Engineer"


def test_classify_path_applies_url_gates() -> None:
    assert (
        classify_path("https://www.f-i.de/de/karriere/offene-stellen/hannover/data-engineer-m-w-d")
        == "origin_open_position_candidate"
    )
    assert (
        classify_path("https://www.f-i.de/de/karriere/duales-studium-ausbildung/hannover/test")
        == "training_or_dual_study_exclude"
    )
    assert classify_path("https://www.linkedin.com/company/example") == "external_non_job"
    assert (
        classify_path("https://finanz-informatik.onapply.de/details/123.html")
        == "onapply_detail_candidate_manual_review_only"
    )


def test_recommendation_excludes_training_even_with_profile_terms() -> None:
    recommendation, _ = recommendation_for_candidate(
        path_class="training_or_dual_study_exclude",
        profile_terms=("data",),
        exclusion_terms=("duales-studium",),
        lower_value_scope_terms=(),
        location="hannover",
    )

    assert recommendation == "exclude_training_student_or_entry_level"


def test_candidate_with_hannover_profile_signal_is_strong_review_candidate() -> None:
    link = ExtractedLink(
        source_url="https://www.f-i.de/de/karriere/offene-stellen",
        href="/de/karriere/offene-stellen/hannover/data-engineer-m-w-d",
        absolute_url="https://www.f-i.de/de/karriere/offene-stellen/hannover/data-engineer-m-w-d",
        text="Data Engineer m/w/d",
    )

    candidate = candidate_from_link(link)

    assert candidate.path_class == "origin_open_position_candidate"
    assert candidate.location_signal == "hannover"
    assert candidate.profile_terms
    assert candidate.recommendation == "strong_listing_candidate_for_review"
    assert candidate.detail_fetch_needed_later is True


def test_candidate_with_secondary_location_without_remote_signal_is_deferred() -> None:
    link = ExtractedLink(
        source_url="https://www.f-i.de/de/karriere/offene-stellen",
        href="/de/karriere/offene-stellen/frankfurt/business-analyst-m-w-d",
        absolute_url="https://www.f-i.de/de/karriere/offene-stellen/frankfurt/business-analyst-m-w-d",
        text="Business Analyst m/w/d",
    )

    candidate = candidate_from_link(link)

    assert candidate.path_class == "origin_open_position_candidate"
    assert candidate.location_signal == "frankfurt"
    assert candidate.profile_terms
    assert candidate.recommendation == "defer_non_target_location_without_remote_signal"
    assert candidate.detail_fetch_needed_later is False


def test_candidate_with_remote_signal_is_strong_review_candidate() -> None:
    link = ExtractedLink(
        source_url="https://www.f-i.de/de/karriere/offene-stellen",
        href="/de/karriere/offene-stellen/deutschland/data-engineer-remote-m-w-d",
        absolute_url="https://www.f-i.de/de/karriere/offene-stellen/deutschland/data-engineer-remote-m-w-d",
        text="Data Engineer remote m/w/d",
    )

    candidate = candidate_from_link(link)

    assert candidate.location_signal == "remote; deutschland"
    assert candidate.profile_terms
    assert candidate.recommendation == "strong_listing_candidate_for_review"
    assert candidate.detail_fetch_needed_later is True


def test_run_spike_writes_exports_without_network(tmp_path: Path) -> None:
    def fake_fetcher(url: str, _: int) -> FetchedPage:
        return FetchedPage(
            source_url=url,
            status_code=200,
            final_url=url,
            html="""
                <a href="/de/karriere/offene-stellen/hannover/data-engineer-m-w-d">Data Engineer m/w/d</a>
                <a href="/de/karriere/duales-studium-ausbildung/hannover/duales-studium-informatik">Duales Studium Informatik</a>
                <a href="https://finanz-informatik.onapply.de/details/123.html">Business Analyst</a>
            """,
            html_bytes=300,
        )

    manifest = run_spike(
        export_dir=tmp_path,
        source_urls=("https://www.f-i.de/de/karriere/offene-stellen",),
        timeout_seconds=1,
        fetcher=fake_fetcher,
    )

    assert manifest["database_writes"] is False
    assert manifest["detail_pages_fetched"] is False
    assert manifest["raw_html_persisted"] is False
    assert manifest["connector_implemented"] is False
    assert manifest["source_target_activated"] is False
    assert manifest["candidate_count"] == 3
    assert (tmp_path / "finanz_informatik_spike_candidates.csv").exists()
    assert (tmp_path / "finanz_informatik_spike_relevance_summary.csv").exists()
    assert (tmp_path / "finanz_informatik_spike_manifest.json").exists()
    assert (tmp_path / "finanz_informatik_spike_review.md").exists()


def test_secondary_location_low_profile_candidate_is_deferred() -> None:
    link = ExtractedLink(
        source_url="https://www.f-i.de/de/karriere/offene-stellen",
        href="/de/karriere/offene-stellen/muenster/it-spezialist-anwendungsbetreuer-m-w-d",
        absolute_url="https://www.f-i.de/de/karriere/offene-stellen/muenster/it-spezialist-anwendungsbetreuer-m-w-d",
        text="IT Spezialist Anwendungsbetreuer m/w/d",
    )

    candidate = candidate_from_link(link)

    assert candidate.path_class == "origin_open_position_candidate"
    assert candidate.location_signal == "muenster"
    assert candidate.profile_terms == ()
    assert candidate.recommendation == "defer_non_target_location_without_remote_signal"
    assert candidate.detail_fetch_needed_later is False

