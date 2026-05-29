from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.export_historical_burden_archive import ARCHIVE_RETENTION_TRACK
from scripts.remove_historical_burden_from_hot_store import (
    APPROVE_CONFIRMATION_ACTION,
    ELIGIBLE_REVIEW_STATUS,
    EXECUTE_CONFIRMATION_ACTION,
    READY_EXECUTION_STATUS,
    RemovalExecutionResult,
    build_execution_manifest,
    build_removal_plan,
    validate_plan_for_approval,
    validate_plan_for_execution,
    write_report_artifacts,
)


def make_batch(status: str = "proposed", candidate_count: int = 1) -> dict[str, object]:
    return {
        "id": 42,
        "status": status,
        "review_reason": "unit test",
        "retention_track": ARCHIVE_RETENTION_TRACK,
        "candidate_count": candidate_count,
        "silver_backed_rows": 0,
    }


def make_row(
    raw_job_id: int = 1,
    current_exists_in_hot_store: bool = True,
    current_has_silver_job: bool = False,
    review_status: str = ELIGIBLE_REVIEW_STATUS,
    eligible_for_future_removal: bool = True,
    execution_status: str = "not_executed",
    retention_track: str = ARCHIVE_RETENTION_TRACK,
    source_name: str = "greenhouse:stripe",
    current_source_name: str | None = "greenhouse:stripe",
) -> dict[str, object]:
    return {
        "review_item_id": raw_job_id + 1000,
        "batch_id": 42,
        "raw_job_id": raw_job_id,
        "source_name": source_name,
        "external_job_id": f"job-{raw_job_id}",
        "source_url": f"https://example.com/jobs/{raw_job_id}",
        "fetched_at": None,
        "ingestion_run_id": None,
        "search_profile_id": None,
        "initial_profile_name": "greenhouse_stripe",
        "initial_search_term_snapshot": "<multi-term_or_missing>",
        "burden_category": "greenhouse_without_current_matching_metadata",
        "retention_track": retention_track,
        "review_exists_in_hot_store": True,
        "review_has_silver_job_now": False,
        "still_archive_candidate": True,
        "eligible_for_future_removal": eligible_for_future_removal,
        "review_status": review_status,
        "raw_data_bytes": 100,
        "execution_status": execution_status,
        "current_exists_in_hot_store": current_exists_in_hot_store,
        "current_source_name": current_source_name,
        "current_has_silver_job": current_has_silver_job,
    }


def test_build_removal_plan_marks_ready_items() -> None:
    batch = make_batch()
    plan = build_removal_plan(batch, [make_row()])

    assert plan.batch_id == 42
    assert plan.batch_status == "proposed"
    assert plan.candidate_count == 1
    assert plan.eligible_count == 1
    assert plan.blocked_count == 0
    assert plan.items[0].execution_status == READY_EXECUTION_STATUS
    assert plan.items[0].block_reason is None


def test_build_removal_plan_blocks_changed_or_unsafe_rows() -> None:
    batch = make_batch(candidate_count=4)
    plan = build_removal_plan(
        batch,
        [
            make_row(1, current_exists_in_hot_store=False),
            make_row(2, current_has_silver_job=True),
            make_row(3, review_status="manual_review_required"),
            make_row(4, current_source_name="stepstone"),
        ],
    )

    assert plan.eligible_count == 0
    assert plan.blocked_count == 4
    assert {item.block_reason for item in plan.items} == {
        "raw_job_missing_from_hot_store",
        "silver_job_now_exists",
        "review_status_not_eligible",
        "source_name_changed",
    }


def test_validate_plan_for_approval_requires_proposed_or_reviewed_clean_batch() -> None:
    plan = build_removal_plan(make_batch(status="proposed"), [make_row()])
    validate_plan_for_approval(make_batch(status="proposed"), plan)
    validate_plan_for_approval(make_batch(status="reviewed"), plan)

    with pytest.raises(ValueError, match="Only proposed or reviewed"):
        validate_plan_for_approval(make_batch(status="approved"), plan)

    blocked_plan = build_removal_plan(
        make_batch(status="proposed"),
        [make_row(current_has_silver_job=True)],
    )
    with pytest.raises(ValueError, match="blocked rows"):
        validate_plan_for_approval(make_batch(status="proposed"), blocked_plan)


def test_validate_plan_for_execution_requires_approved_clean_batch() -> None:
    approved_batch = make_batch(status="approved")
    plan = build_removal_plan(approved_batch, [make_row()])
    validate_plan_for_execution(approved_batch, plan)

    with pytest.raises(ValueError, match="requires an approved"):
        validate_plan_for_execution(make_batch(status="proposed"), plan)

    blocked_plan = build_removal_plan(
        approved_batch,
        [make_row(current_has_silver_job=True)],
    )
    with pytest.raises(ValueError, match="blocked rows"):
        validate_plan_for_execution(approved_batch, blocked_plan)


def test_build_execution_manifest_is_db_backed_and_output_only() -> None:
    plan = build_removal_plan(make_batch(status="approved"), [make_row()])
    manifest = build_execution_manifest(
        plan=plan,
        mode="dry_run",
        database_cleanup_action="none",
    )

    text = json.dumps(manifest)

    assert manifest["input_source"] == "db_review_batch"
    assert manifest["batch_id"] == 42
    assert "removal_candidates_csv" not in text
    assert "review_dir" not in text
    assert "not a destructive-operation input" in " ".join(manifest["output_boundary"])


def test_build_execution_manifest_includes_execution_result_without_csv() -> None:
    plan = build_removal_plan(make_batch(status="approved"), [make_row()])
    result = RemovalExecutionResult(
        job_observations_deleted=2,
        silver_processing_decisions_deleted=1,
        raw_jobs_deleted=1,
        deleted_raw_job_ids=[1],
    )

    manifest = build_execution_manifest(
        plan=plan,
        mode="execute",
        database_cleanup_action="delete_hot_store_rows",
        result=result,
    )

    assert manifest["input_source"] == "approved_db_review_batch"
    assert manifest["execution_result"]["raw_jobs_deleted"] == 1
    assert "removal_candidates_csv" not in json.dumps(manifest)


def test_write_report_artifacts_writes_markdown_and_json_only(tmp_path: Path) -> None:
    plan = build_removal_plan(make_batch(status="approved"), [make_row()])

    report_path, manifest_path = write_report_artifacts(
        output_dir=tmp_path,
        plan=plan,
        mode="dry_run",
        database_cleanup_action="none",
    )

    assert report_path.exists()
    assert manifest_path.exists()
    assert not list(tmp_path.glob("*.csv"))

    report = report_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "DB-backed review state" in report
    assert manifest["input_source"] == "db_review_batch"
    assert "removal_candidates_csv" not in manifest_path.read_text(encoding="utf-8")


def test_confirmation_constants_are_explicit() -> None:
    assert APPROVE_CONFIRMATION_ACTION == "approve_historical_burden_hot_store_removal_batch"
    assert EXECUTE_CONFIRMATION_ACTION == "remove_approved_historical_burden_from_hot_store"
