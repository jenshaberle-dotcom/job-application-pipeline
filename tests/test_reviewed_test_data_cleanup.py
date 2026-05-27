from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from scripts.cleanup_reviewed_test_data import (
    DELETE_RETENTION_TRACK,
    EXECUTE_CONFIRMATION_ACTION,
    TEST_DATA_CLEANUP_PLAN_FIELDNAMES,
    ConfirmationSettings,
    ReviewedTestDataCleanupCandidate,
    build_manifest,
    candidate_row,
    format_counter_for_console,
    select_reviewed_test_data_candidates,
    validate_execution_confirmations,
    write_csv,
)
from scripts.review_historical_burden_candidates import HistoricalBurdenCandidate


def make_burden_candidate(
    raw_job_id: int = 1,
    source_name: str = "manual_test",
    burden_category: str = "test_data",
    retention_track: str = DELETE_RETENTION_TRACK,
    has_silver_job: bool = False,
) -> HistoricalBurdenCandidate:
    return HistoricalBurdenCandidate(
        raw_job_id=raw_job_id,
        burden_category=burden_category,
        retention_track=retention_track,
        review_action="review manually; delete only with explicit approved cleanup command",
        source_name=source_name,
        initial_profile_name="test_profile",
        initial_search_term_snapshot="<multi-term_or_missing>",
        fetched_at="2026-05-27T08:00:00+00:00",
        external_job_id=None,
        has_silver_job=has_silver_job,
        processing_decision="<none>",
        has_matching_metadata=False,
        observation_count=0,
        raw_data_bytes=10,
        title_preview="Test Job",
        company_preview="Test Company",
        source_url="https://example.com/test",
    )


def make_cleanup_candidate(
    raw_job_id: int = 1,
    source_name: str = "manual_test",
    eligible_now: bool = True,
) -> ReviewedTestDataCleanupCandidate:
    return ReviewedTestDataCleanupCandidate(
        raw_job_id=raw_job_id,
        source_name=source_name,
        burden_category="test_data",
        retention_track=DELETE_RETENTION_TRACK,
        review_action="review manually; delete only with explicit approved cleanup command",
        external_job_id=None,
        source_url="https://example.com/test",
        fetched_at="2026-05-27T08:00:00+00:00",
        initial_profile_name="test_profile",
        initial_search_term_snapshot="<multi-term_or_missing>",
        has_silver_job=False,
        processing_decision="<none>",
        raw_data_bytes=10,
        title_preview="Test Job",
        company_preview="Test Company",
        eligible_now=eligible_now,
        plan_status=(
            "eligible_for_reviewed_test_data_cleanup"
            if eligible_now
            else "blocked_silver_evidence_now_exists"
        ),
    )


def test_select_reviewed_test_data_candidates_keeps_only_allowed_delete_track() -> None:
    candidates = [
        make_burden_candidate(1, source_name="manual_test"),
        make_burden_candidate(2, source_name="test"),
        make_burden_candidate(
            3,
            source_name="greenhouse:stripe",
            burden_category="greenhouse_without_current_matching_metadata",
            retention_track="archive_before_hot_store_removal_candidate",
        ),
        make_burden_candidate(
            4,
            source_name="manual_test",
            retention_track="retain_as_silver_evidence",
            has_silver_job=True,
        ),
        make_burden_candidate(5, source_name="other_test_source"),
    ]

    selected = select_reviewed_test_data_candidates(
        candidates,
        frozenset({"manual_test", "test"}),
    )

    assert [candidate.raw_job_id for candidate in selected] == [1, 2]
    assert all(candidate.retention_track == DELETE_RETENTION_TRACK for candidate in selected)
    assert all(candidate.eligible_now for candidate in selected)


def test_historical_burden_archive_candidates_are_not_selected() -> None:
    selected = select_reviewed_test_data_candidates(
        [
            make_burden_candidate(
                1,
                source_name="greenhouse:stripe",
                burden_category="greenhouse_without_current_matching_metadata",
                retention_track="archive_before_hot_store_removal_candidate",
            ),
            make_burden_candidate(
                2,
                source_name="stepstone",
                burden_category="commercial_aggregator_history",
                retention_track="archive_before_hot_store_removal_candidate",
            ),
        ],
        frozenset({"manual_test", "test", "greenhouse:stripe", "stepstone"}),
    )

    assert selected == []


def test_validate_execution_confirmations_requires_exact_values() -> None:
    candidates = [make_cleanup_candidate(1), make_cleanup_candidate(2, source_name="test")]
    settings = ConfirmationSettings(
        confirm_retention_track=DELETE_RETENTION_TRACK,
        confirm_candidate_count=2,
        confirm_candidates_sha256="abc123",
        confirm_cleanup_action=EXECUTE_CONFIRMATION_ACTION,
        allow_sources=frozenset({"manual_test", "test"}),
    )

    validate_execution_confirmations(
        execute=True,
        settings=settings,
        eligible_candidates=candidates,
        candidates_sha256="abc123",
    )


def test_validate_execution_confirmations_is_noop_in_dry_run() -> None:
    validate_execution_confirmations(
        execute=False,
        settings=ConfirmationSettings(
            confirm_retention_track=None,
            confirm_candidate_count=None,
            confirm_candidates_sha256=None,
            confirm_cleanup_action=None,
            allow_sources=frozenset(),
        ),
        eligible_candidates=[make_cleanup_candidate(1)],
        candidates_sha256="abc123",
    )


def test_validate_execution_confirmations_blocks_source_mismatch() -> None:
    candidates = [make_cleanup_candidate(1), make_cleanup_candidate(2, source_name="test")]
    settings = ConfirmationSettings(
        confirm_retention_track=DELETE_RETENTION_TRACK,
        confirm_candidate_count=2,
        confirm_candidates_sha256="abc123",
        confirm_cleanup_action=EXECUTE_CONFIRMATION_ACTION,
        allow_sources=frozenset({"manual_test"}),
    )

    with pytest.raises(ValueError, match="allow-source values must exactly match"):
        validate_execution_confirmations(
            execute=True,
            settings=settings,
            eligible_candidates=candidates,
            candidates_sha256="abc123",
        )


def test_validate_execution_confirmations_blocks_wrong_checksum() -> None:
    settings = ConfirmationSettings(
        confirm_retention_track=DELETE_RETENTION_TRACK,
        confirm_candidate_count=1,
        confirm_candidates_sha256="wrong",
        confirm_cleanup_action=EXECUTE_CONFIRMATION_ACTION,
        allow_sources=frozenset({"manual_test"}),
    )

    with pytest.raises(ValueError, match="confirm-candidates-sha256"):
        validate_execution_confirmations(
            execute=True,
            settings=settings,
            eligible_candidates=[make_cleanup_candidate(1)],
            candidates_sha256="abc123",
        )


def test_candidate_row_contains_execution_boundary_fields() -> None:
    row = candidate_row(make_cleanup_candidate(1))

    assert row["retention_track"] == DELETE_RETENTION_TRACK
    assert row["eligible_now"] is True
    assert row["plan_status"] == "eligible_for_reviewed_test_data_cleanup"


def test_build_manifest_keeps_dry_run_non_mutating(tmp_path: Path) -> None:
    plan_path = tmp_path / "reviewed_test_data_cleanup_plan.csv"
    plan_path.write_text("raw_job_id\n1\n", encoding="utf-8")

    manifest = build_manifest(
        execute=False,
        candidates=[make_cleanup_candidate(1)],
        plan_path=plan_path,
        plan_sha256="abc123",
        removal_result=None,
    )

    assert manifest["mode"] == "dry_run_only"
    assert manifest["database_cleanup_action"] == "none"
    assert manifest["retention_track"] == DELETE_RETENTION_TRACK
    assert manifest["candidate_count"] == 1
    assert manifest["eligible_now_count"] == 1
    assert manifest["executed_cleanup"] is False
    assert manifest["cleanup_result_status"] == "not_executed"
    assert manifest["cleanup_result"] is None
    assert manifest["interpretation_boundary"][0].startswith(
        "This workflow is for reviewed test/transient rows"
    )


def test_empty_manifest_has_explicit_not_executed_status(tmp_path: Path) -> None:
    plan_path = tmp_path / "reviewed_test_data_cleanup_plan.csv"
    write_csv(plan_path, [], TEST_DATA_CLEANUP_PLAN_FIELDNAMES)

    manifest = build_manifest(
        execute=False,
        candidates=[],
        plan_path=plan_path,
        plan_sha256="abc123",
        removal_result=None,
    )

    assert manifest["candidate_count"] == 0
    assert manifest["source_counts"] == {}
    assert manifest["plan_status_counts"] == {}
    assert manifest["cleanup_result_status"] == "not_executed"
    assert manifest["cleanup_result"] is None


def test_empty_cleanup_plan_csv_keeps_header(tmp_path: Path) -> None:
    plan_path = tmp_path / "reviewed_test_data_cleanup_plan.csv"

    write_csv(plan_path, [], TEST_DATA_CLEANUP_PLAN_FIELDNAMES)

    lines = plan_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert lines[0].split(",") == TEST_DATA_CLEANUP_PLAN_FIELDNAMES


def test_format_counter_for_console_uses_none_for_empty_counts() -> None:
    assert format_counter_for_console(Counter()) == "<none>"
