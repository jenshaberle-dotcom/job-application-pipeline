from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.export_historical_burden_archive import ARCHIVE_RETENTION_TRACK
from scripts.remove_historical_burden_from_hot_store import (
    EXECUTE_CONFIRMATION_ACTION,
    ConfirmationSettings,
    CurrentEligibilityResult,
    RemovalReviewCandidate,
    build_execution_manifest,
    compute_sha256,
    load_removal_review_candidates,
    select_eligible_review_candidates,
    validate_candidate_set,
    validate_current_eligibility,
    validate_execution_confirmations,
    validate_removal_review_manifest,
)
from scripts.prepare_historical_burden_hot_store_removal import CurrentHotStoreState


def make_candidate(
    raw_job_id: int = 1,
    source_name: str = "greenhouse:stripe",
    retention_track: str = ARCHIVE_RETENTION_TRACK,
    eligible_for_future_removal: bool = True,
    review_status: str = "eligible_after_archive_review",
    has_silver_job_now: bool = False,
    exists_in_hot_store: bool = True,
    still_archive_candidate: bool = True,
) -> RemovalReviewCandidate:
    return RemovalReviewCandidate(
        raw_job_id=raw_job_id,
        source_name=source_name,
        archived_burden_category="greenhouse_without_current_matching_metadata",
        current_burden_category="greenhouse_without_current_matching_metadata",
        retention_track=retention_track,
        exists_in_hot_store=exists_in_hot_store,
        has_silver_job_now=has_silver_job_now,
        still_archive_candidate=still_archive_candidate,
        eligible_for_future_removal=eligible_for_future_removal,
        review_status=review_status,
        external_job_id=f"job-{raw_job_id}",
        source_url=f"https://example.com/jobs/{raw_job_id}",
        fetched_at="2026-05-27T08:00:00+00:00",
        initial_profile_name="greenhouse_stripe",
        initial_search_term_snapshot="<multi-term_or_missing>",
        raw_data_bytes=100,
    )


def make_current_state(
    raw_job_id: int = 1,
    source_name: str = "greenhouse:stripe",
    current_retention_track: str = ARCHIVE_RETENTION_TRACK,
    has_silver_job: bool = False,
) -> CurrentHotStoreState:
    return CurrentHotStoreState(
        raw_job_id=raw_job_id,
        source_name=source_name,
        initial_profile_name="greenhouse_stripe",
        initial_search_term_snapshot="<multi-term_or_missing>",
        current_burden_category="greenhouse_without_current_matching_metadata",
        current_retention_track=current_retention_track,
        has_silver_job=has_silver_job,
    )


def write_candidates_csv(path: Path, candidates: list[RemovalReviewCandidate]) -> None:
    rows = [candidate.__dict__ for candidate in candidates]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_select_eligible_review_candidates_filters_strictly() -> None:
    candidates = [
        make_candidate(1),
        make_candidate(2, eligible_for_future_removal=False),
        make_candidate(3, review_status="blocked_silver_evidence_now_exists"),
        make_candidate(4, retention_track="delete_candidate_after_review"),
        make_candidate(5, has_silver_job_now=True),
        make_candidate(6, exists_in_hot_store=False),
        make_candidate(7, still_archive_candidate=False),
    ]

    eligible = select_eligible_review_candidates(candidates)

    assert [candidate.raw_job_id for candidate in eligible] == [1]


def test_validate_execution_confirmations_requires_noisy_exact_confirmations() -> None:
    candidates = [make_candidate(1), make_candidate(2, source_name="stepstone")]
    settings = ConfirmationSettings(
        confirm_retention_track=ARCHIVE_RETENTION_TRACK,
        confirm_candidate_count=2,
        confirm_candidates_sha256="abc123",
        confirm_cleanup_action=EXECUTE_CONFIRMATION_ACTION,
        allow_sources=frozenset({"greenhouse:stripe", "stepstone"}),
    )

    validate_execution_confirmations(
        execute=True,
        settings=settings,
        eligible_candidates=candidates,
        candidates_sha256="abc123",
    )


def test_validate_execution_confirmations_blocks_missing_source_confirmation() -> None:
    candidates = [make_candidate(1), make_candidate(2, source_name="stepstone")]
    settings = ConfirmationSettings(
        confirm_retention_track=ARCHIVE_RETENTION_TRACK,
        confirm_candidate_count=2,
        confirm_candidates_sha256="abc123",
        confirm_cleanup_action=EXECUTE_CONFIRMATION_ACTION,
        allow_sources=frozenset({"greenhouse:stripe"}),
    )

    with pytest.raises(ValueError, match="allow-source values must exactly match"):
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
        eligible_candidates=[make_candidate(1)],
        candidates_sha256="abc123",
    )


def test_validate_current_eligibility_blocks_rows_that_now_have_silver() -> None:
    candidate = make_candidate(1)
    results = validate_current_eligibility(
        [candidate],
        {1: make_current_state(1, has_silver_job=True)},
    )

    assert results[0].eligible_now is False
    assert results[0].status == "blocked_silver_evidence_now_exists"


def test_validate_current_eligibility_marks_matching_rows_eligible() -> None:
    candidate = make_candidate(1)
    results = validate_current_eligibility([candidate], {1: make_current_state(1)})

    assert results[0].eligible_now is True
    assert results[0].status == "eligible_for_guarded_hot_store_removal"


def test_validate_candidate_set_compares_manifest_counts() -> None:
    candidates = [make_candidate(1), make_candidate(2, eligible_for_future_removal=False)]
    eligible = select_eligible_review_candidates(candidates)

    validate_candidate_set(
        candidates,
        eligible,
        {"candidate_count": 2, "eligible_for_future_removal_count": 1},
    )

    with pytest.raises(ValueError, match="candidate_count does not match"):
        validate_candidate_set(
            candidates,
            eligible,
            {"candidate_count": 999, "eligible_for_future_removal_count": 1},
        )


def test_validate_removal_review_manifest_rejects_mutating_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "historical_burden_hot_store_removal_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "database_cleanup_action": "delete",
                "mode": "hot_store_removal_dry_run_only",
                "retention_track": ARCHIVE_RETENTION_TRACK,
                "silver_backed_rows_now": 0,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="database_cleanup_action=none"):
        validate_removal_review_manifest(manifest_path)


def test_validate_removal_review_manifest_checks_candidates_checksum(tmp_path: Path) -> None:
    candidates_path = tmp_path / "historical_burden_hot_store_removal_candidates.csv"
    write_candidates_csv(candidates_path, [make_candidate(1)])

    manifest_path = tmp_path / "historical_burden_hot_store_removal_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "database_cleanup_action": "none",
                "mode": "hot_store_removal_dry_run_only",
                "retention_track": ARCHIVE_RETENTION_TRACK,
                "silver_backed_rows_now": 0,
                "exports": {
                    "removal_candidates_csv": {
                        "path": str(candidates_path),
                        "sha256": compute_sha256(candidates_path),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    manifest, resolved_candidates_path = validate_removal_review_manifest(manifest_path)

    assert manifest["database_cleanup_action"] == "none"
    assert resolved_candidates_path == candidates_path
    assert load_removal_review_candidates(candidates_path)[0].raw_job_id == 1


def test_build_execution_manifest_keeps_dry_run_non_mutating(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.csv"
    plan_path.write_text("raw_job_id\n1\n", encoding="utf-8")
    result = CurrentEligibilityResult(
        candidate=make_candidate(1),
        eligible_now=True,
        status="eligible_for_guarded_hot_store_removal",
    )

    manifest = build_execution_manifest(
        execute=False,
        manifest={"generated_at_utc": "2026-05-27T10:00:00+00:00", "candidate_count": 1},
        review_candidates_sha256="abc123",
        current_results=[result],
        plan_path=plan_path,
        removal_result=None,
    )

    assert manifest["mode"] == "dry_run_only"
    assert manifest["database_cleanup_action"] == "none"
    assert manifest["eligible_now_count"] == 1
    assert manifest["executed_removal"] is False
