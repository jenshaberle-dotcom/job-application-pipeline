from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.export_historical_burden_archive import ARCHIVE_RETENTION_TRACK
from scripts.prepare_historical_burden_hot_store_removal import (
    ArchiveRecordReference,
    CurrentHotStoreState,
    build_manifest,
    build_removal_candidates,
    compute_sha256,
    export_review,
    load_archive_records,
    validate_archive_manifest,
)


def make_archive_record(raw_job_id: int = 1) -> ArchiveRecordReference:
    return ArchiveRecordReference(
        raw_job_id=raw_job_id,
        source_name="greenhouse:stripe",
        burden_category="greenhouse_without_current_matching_metadata",
        retention_track=ARCHIVE_RETENTION_TRACK,
        has_silver_job=False,
        external_job_id=f"job-{raw_job_id}",
        source_url=f"https://example.com/jobs/{raw_job_id}",
        fetched_at="2026-05-27T08:00:00+00:00",
        initial_profile_name="greenhouse_stripe",
        initial_search_term_snapshot="<multi-term_or_missing>",
        raw_data_bytes=100,
    )


def make_current_state(
    raw_job_id: int = 1,
    current_retention_track: str = ARCHIVE_RETENTION_TRACK,
    has_silver_job: bool = False,
) -> CurrentHotStoreState:
    return CurrentHotStoreState(
        raw_job_id=raw_job_id,
        source_name="greenhouse:stripe",
        initial_profile_name="greenhouse_stripe",
        initial_search_term_snapshot="<multi-term_or_missing>",
        current_burden_category="greenhouse_without_current_matching_metadata",
        current_retention_track=current_retention_track,
        has_silver_job=has_silver_job,
    )


def test_build_removal_candidates_marks_matching_archive_rows_as_eligible() -> None:
    archive_record = make_archive_record(1)
    current_states = {1: make_current_state(1)}

    candidates = build_removal_candidates([archive_record], current_states)

    assert len(candidates) == 1
    assert candidates[0].eligible_for_future_removal is True
    assert candidates[0].review_status == "eligible_after_archive_review"


def test_build_removal_candidates_blocks_rows_that_now_have_silver_evidence() -> None:
    archive_record = make_archive_record(1)
    current_states = {1: make_current_state(1, has_silver_job=True)}

    candidates = build_removal_candidates([archive_record], current_states)

    assert candidates[0].eligible_for_future_removal is False
    assert candidates[0].review_status == "blocked_silver_evidence_now_exists"


def test_build_removal_candidates_marks_absent_rows_as_non_actionable() -> None:
    archive_record = make_archive_record(1)

    candidates = build_removal_candidates([archive_record], current_states={})

    assert candidates[0].eligible_for_future_removal is False
    assert candidates[0].review_status == "already_absent_from_hot_store"


def test_load_archive_records_rejects_silver_backed_rows(tmp_path: Path) -> None:
    records_path = tmp_path / "records.jsonl"
    records_path.write_text(
        json.dumps(
            {
                "raw_job_id": 1,
                "source_name": "greenhouse:stripe",
                "burden_category": "greenhouse_without_current_matching_metadata",
                "retention_track": ARCHIVE_RETENTION_TRACK,
                "has_silver_job": True,
                "raw_data_bytes": 100,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Silver-backed"):
        load_archive_records(records_path)


def test_validate_archive_manifest_rejects_checksum_mismatch(tmp_path: Path) -> None:
    records_path = tmp_path / "historical_burden_archive_records.jsonl"
    records_path.write_text("{}\n", encoding="utf-8")

    manifest_path = tmp_path / "historical_burden_archive_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "database_cleanup_action": "none",
                "retention_track": ARCHIVE_RETENTION_TRACK,
                "silver_backed_rows": 0,
                "exports": {
                    "records_jsonl": {
                        "path": str(records_path),
                        "sha256": "not-the-real-hash",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checksum mismatch"):
        validate_archive_manifest(manifest_path)


def test_export_review_writes_candidates_and_manifest(tmp_path: Path) -> None:
    archive_record = make_archive_record(1)
    current_states = {1: make_current_state(1)}
    candidates = build_removal_candidates([archive_record], current_states)
    archive_manifest = {
        "generated_at_utc": "2026-05-27T09:55:52+00:00",
        "record_count": 1,
    }

    candidates_path, manifest_path = export_review(candidates, archive_manifest, tmp_path)

    assert candidates_path.exists()
    assert manifest_path.exists()

    with candidates_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert rows[0]["review_status"] == "eligible_after_archive_review"
    assert rows[0]["eligible_for_future_removal"] == "True"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["database_cleanup_action"] == "none"
    assert manifest["mode"] == "hot_store_removal_dry_run_only"
    assert manifest["candidate_count"] == 1
    assert manifest["eligible_for_future_removal_count"] == 1
    assert manifest["silver_backed_rows_now"] == 0
    assert manifest["exports"]["removal_candidates_csv"]["sha256"] == compute_sha256(candidates_path)


def test_build_manifest_counts_blocked_rows() -> None:
    archive_records = [make_archive_record(1), make_archive_record(2)]
    current_states = {
        1: make_current_state(1),
        2: make_current_state(2, has_silver_job=True),
    }
    candidates = build_removal_candidates(archive_records, current_states)
    csv_path = Path(__file__)

    manifest = build_manifest(
        candidates=candidates,
        archive_manifest={"generated_at_utc": "2026-05-27T09:55:52+00:00", "record_count": 2},
        candidates_path=csv_path,
    )

    assert manifest["candidate_count"] == 2
    assert manifest["eligible_for_future_removal_count"] == 1
    assert manifest["blocked_or_non_actionable_count"] == 1
    assert manifest["silver_backed_rows_now"] == 1
    assert manifest["review_status_counts"]["eligible_after_archive_review"] == 1
    assert manifest["review_status_counts"]["blocked_silver_evidence_now_exists"] == 1
