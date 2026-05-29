from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.export_historical_burden_archive import ARCHIVE_RETENTION_TRACK
from scripts.prepare_historical_burden_hot_store_removal import (
    HotStoreRemovalCandidate,
    build_manifest,
    build_removal_candidates,
    build_review_summary,
    candidate_to_db_row,
    write_review_artifacts,
)


def make_db_row(
    raw_job_id: int = 1,
    source_name: str = "greenhouse:stripe",
    burden_category: str = "greenhouse_without_current_matching_metadata",
    has_silver_job: bool = False,
) -> dict[str, object]:
    return {
        "raw_job_id": raw_job_id,
        "source_name": source_name,
        "external_job_id": f"job-{raw_job_id}",
        "source_url": f"https://example.com/jobs/{raw_job_id}",
        "fetched_at": datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc),
        "ingestion_run_id": 10,
        "search_profile_id": 20,
        "initial_profile_name": "greenhouse_stripe",
        "initial_search_term_snapshot": "<multi-term_or_missing>",
        "raw_data_bytes": 100,
        "has_silver_job": has_silver_job,
        "burden_category": burden_category,
    }


def make_candidate(raw_job_id: int = 1) -> HotStoreRemovalCandidate:
    candidates = build_removal_candidates([make_db_row(raw_job_id=raw_job_id)])
    assert len(candidates) == 1
    return candidates[0]


def test_build_removal_candidates_filters_to_archive_retention_track() -> None:
    rows = [
        make_db_row(1),
        make_db_row(2, source_name="bundesagentur_fuer_arbeit", burden_category="ordinary_operational_history"),
        make_db_row(3, has_silver_job=True),
    ]

    candidates = build_removal_candidates(rows)

    assert [candidate.raw_job_id for candidate in candidates] == [1]
    assert candidates[0].retention_track == ARCHIVE_RETENTION_TRACK
    assert candidates[0].review_status == "eligible_after_db_review"
    assert candidates[0].eligible_for_future_removal is True


def test_build_review_summary_counts_candidates() -> None:
    candidates = [make_candidate(1), make_candidate(2)]

    summary = build_review_summary(candidates)

    assert summary["candidate_count"] == 2
    assert summary["eligible_for_removal_count"] == 2
    assert summary["blocked_or_non_actionable_count"] == 0
    assert summary["silver_backed_rows"] == 0
    assert summary["source_counts"] == {"greenhouse:stripe": 2}
    assert summary["review_status_counts"] == {"eligible_after_db_review": 2}


def test_build_manifest_is_output_only_and_references_batch_id() -> None:
    candidates = [make_candidate(1)]

    manifest = build_manifest(
        batch_id=42,
        candidates=candidates,
        review_reason="unit test",
    )

    assert manifest["mode"] == "db_backed_hot_store_removal_review"
    assert manifest["database_cleanup_action"] == "none"
    assert manifest["batch_id"] == 42
    assert "exports" not in manifest
    assert "removal_candidates_csv" not in json.dumps(manifest)
    assert "not a destructive-operation input" in " ".join(manifest["output_boundary"])


def test_candidate_to_db_row_keeps_snapshot_without_requiring_raw_jobs_fk() -> None:
    candidate = make_candidate(1)

    row = candidate_to_db_row(batch_id=42, candidate=candidate)

    assert row["batch_id"] == 42
    assert row["raw_job_id"] == 1
    assert row["review_status"] == "eligible_after_db_review"
    assert row["eligible_for_future_removal"] is True
    assert row["item_snapshot"].obj["raw_job_id"] == 1


def test_write_review_artifacts_writes_markdown_and_json_without_csv(tmp_path: Path) -> None:
    candidates = [make_candidate(1)]

    markdown_path, manifest_path = write_review_artifacts(
        export_dir=tmp_path,
        batch_id=42,
        candidates=candidates,
        review_reason="unit test",
    )

    assert markdown_path.exists()
    assert manifest_path.exists()
    assert not list(tmp_path.glob("*.csv"))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert manifest["batch_id"] == 42
    assert "removal_candidates_csv" not in manifest_path.read_text(encoding="utf-8")
    assert "must not be used as pipeline inputs" in markdown
