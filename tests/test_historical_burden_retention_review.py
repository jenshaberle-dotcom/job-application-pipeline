from scripts.review_historical_burden_candidates import (
    HistoricalBurdenCandidate,
    classify_retention_track,
    classify_review_action,
    format_bytes,
    get_detail_candidates,
    shorten_text,
)


def test_silver_backed_rows_are_always_retained_as_evidence() -> None:
    assert (
        classify_retention_track(
            burden_category="greenhouse_legacy_wildcard",
            has_silver_job=True,
        )
        == "retain_as_silver_evidence"
    )


def test_test_data_requires_explicit_review_before_delete() -> None:
    retention_track = classify_retention_track(
        burden_category="test_data",
        has_silver_job=False,
    )

    assert retention_track == "delete_candidate_after_review"
    assert "explicit approved cleanup command" in classify_review_action(retention_track)


def test_aggregator_history_is_archive_or_trend_exclusion_candidate() -> None:
    assert (
        classify_retention_track(
            burden_category="commercial_aggregator_history",
            has_silver_job=False,
        )
        == "archive_before_hot_store_removal_candidate"
    )


def test_greenhouse_full_fetch_history_is_not_delete_candidate() -> None:
    for burden_category in {
        "greenhouse_legacy_wildcard",
        "greenhouse_without_current_matching_metadata",
    }:
        retention_track = classify_retention_track(
            burden_category=burden_category,
            has_silver_job=False,
        )

        assert retention_track == "archive_before_hot_store_removal_candidate"
        assert retention_track != "delete_candidate_after_review"


def test_missing_lineage_is_not_deleted_automatically() -> None:
    assert (
        classify_retention_track(
            burden_category="missing_lineage",
            has_silver_job=False,
        )
        == "review_lineage_before_action"
    )


def test_ordinary_history_is_retained_by_default() -> None:
    assert (
        classify_retention_track(
            burden_category="ordinary_operational_history",
            has_silver_job=False,
        )
        == "retain_operational_history"
    )


def make_candidate(
    raw_job_id: int,
    retention_track: str,
) -> HistoricalBurdenCandidate:
    return HistoricalBurdenCandidate(
        raw_job_id=raw_job_id,
        burden_category="ordinary_operational_history",
        retention_track=retention_track,
        review_action="test action",
        source_name="test_source",
        initial_profile_name="test_profile",
        initial_search_term_snapshot="Data Engineer",
        fetched_at="2026-05-27T08:00:00+00:00",
        external_job_id=None,
        has_silver_job=False,
        processing_decision="<none>",
        has_matching_metadata=False,
        observation_count=0,
        raw_data_bytes=1,
        title_preview="Data Engineer",
        company_preview="Example Company",
        source_url="https://example.com/job",
    )


def test_default_detail_output_excludes_ordinary_history() -> None:
    candidates = [
        make_candidate(1, "retain_operational_history"),
        make_candidate(2, "archive_before_hot_store_removal_candidate"),
    ]

    detail_candidates = get_detail_candidates(
        candidates=candidates,
        include_ordinary=False,
        detail_limit=50,
    )

    assert [candidate.raw_job_id for candidate in detail_candidates] == [2]


def test_detail_limit_zero_includes_all_rows_for_export_consistency() -> None:
    candidates = [
        make_candidate(1, "retain_operational_history"),
        make_candidate(2, "archive_before_hot_store_removal_candidate"),
    ]

    detail_candidates = get_detail_candidates(
        candidates=candidates,
        include_ordinary=False,
        detail_limit=0,
    )

    assert {candidate.raw_job_id for candidate in detail_candidates} == {1, 2}


def test_format_bytes_uses_human_readable_units() -> None:
    assert format_bytes(512) == "512 bytes"
    assert format_bytes(2048) == "2.0 kB"


def test_shorten_text_normalizes_whitespace_and_truncates() -> None:
    assert shorten_text("Data\nEngineer", max_length=50) == "Data Engineer"
    assert shorten_text("abcdefghij", max_length=8) == "abcde..."
