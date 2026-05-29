"""Guarded DB-backed hot-store removal for reviewed historical burden.

This command operates only on DB-backed historical-burden review batches. It does
not read local CSV files, manifest files or review artifacts as execution input.

Default mode is dry-run. Destructive hot-store removal requires:

1. a DB-backed review batch with status `approved`
2. explicit `--execute`
3. exact confirmation text

Approval is also explicit and updates only database review state. Generated
Markdown/JSON files are human-readable reports only.

Usage:
    python -m scripts.remove_historical_burden_from_hot_store --batch-id 2

    python -m scripts.remove_historical_burden_from_hot_store \
      --batch-id 2 \
      --approve \
      --confirm approve_historical_burden_hot_store_removal_batch

    python -m scripts.remove_historical_burden_from_hot_store \
      --batch-id 2 \
      --execute \
      --confirm remove_approved_historical_burden_from_hot_store
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scripts.export_historical_burden_archive import ARCHIVE_RETENTION_TRACK
from scripts.review_historical_burden_candidates import format_bytes
from src.config import get_database_config


DEFAULT_OUTPUT_DIR = Path("exports/historical_burden_hot_store_removal_execution")
EXECUTION_REPORT_FILENAME = "historical_burden_hot_store_removal_execution_report.md"
EXECUTION_MANIFEST_FILENAME = "historical_burden_hot_store_removal_execution_manifest.json"

APPROVE_CONFIRMATION_ACTION = "approve_historical_burden_hot_store_removal_batch"
EXECUTE_CONFIRMATION_ACTION = "remove_approved_historical_burden_from_hot_store"

ELIGIBLE_REVIEW_STATUS = "eligible_after_db_review"
READY_EXECUTION_STATUS = "ready_for_hot_store_removal"

LOAD_BATCH_SQL = """
SELECT
    id,
    created_at,
    updated_at,
    status,
    review_reason,
    retention_track,
    candidate_count,
    eligible_for_removal_count,
    blocked_or_non_actionable_count,
    silver_backed_rows,
    source_counts,
    burden_category_counts,
    review_status_counts,
    raw_data_bytes,
    metadata,
    decision_note,
    approved_at,
    executed_at,
    cancelled_at
FROM historical_burden_review_batches
WHERE id = %s;
"""

LOAD_REVIEW_ITEM_STATE_SQL = """
SELECT
    hbi.id AS review_item_id,
    hbi.batch_id,
    hbi.raw_job_id,
    hbi.source_name,
    hbi.external_job_id,
    hbi.source_url,
    hbi.fetched_at,
    hbi.ingestion_run_id,
    hbi.search_profile_id,
    hbi.initial_profile_name,
    hbi.initial_search_term_snapshot,
    hbi.burden_category,
    hbi.retention_track,
    hbi.exists_in_hot_store AS review_exists_in_hot_store,
    hbi.has_silver_job_now AS review_has_silver_job_now,
    hbi.still_archive_candidate,
    hbi.eligible_for_future_removal,
    hbi.review_status,
    hbi.raw_data_bytes,
    hbi.execution_status,
    rj.id IS NOT NULL AS current_exists_in_hot_store,
    rj.source_name AS current_source_name,
    sj.id IS NOT NULL AS current_has_silver_job
FROM historical_burden_review_items hbi
LEFT JOIN raw_jobs rj
    ON rj.id = hbi.raw_job_id
LEFT JOIN silver_jobs sj
    ON sj.raw_job_id = hbi.raw_job_id
WHERE hbi.batch_id = %s
ORDER BY hbi.raw_job_id;
"""

APPROVE_BATCH_SQL = """
UPDATE historical_burden_review_batches
SET
    status = 'approved',
    approved_at = COALESCE(approved_at, now()),
    updated_at = now(),
    decision_note = %s
WHERE id = %s
  AND status IN ('proposed', 'reviewed')
RETURNING id;
"""

DELETE_JOB_OBSERVATIONS_SQL = """
DELETE FROM job_observations
WHERE raw_job_id = ANY(%s);
"""

DELETE_SILVER_PROCESSING_DECISIONS_SQL = """
DELETE FROM silver_processing_decisions
WHERE raw_job_id = ANY(%s);
"""

DELETE_RAW_JOBS_SQL = """
DELETE FROM raw_jobs
WHERE id = ANY(%s)
RETURNING id;
"""

MARK_ITEMS_REMOVED_SQL = """
UPDATE historical_burden_review_items
SET
    exists_in_hot_store = false,
    execution_status = 'removed_from_hot_store',
    executed_at = now(),
    execution_note = %s
WHERE batch_id = %s
  AND raw_job_id = ANY(%s);
"""

MARK_BATCH_EXECUTED_SQL = """
UPDATE historical_burden_review_batches
SET
    status = 'executed',
    executed_at = now(),
    updated_at = now(),
    metadata = metadata || %s::jsonb
WHERE id = %s;
"""


@dataclass(frozen=True)
class RemovalPlanItem:
    review_item_id: int
    raw_job_id: int
    source_name: str
    burden_category: str
    retention_track: str
    review_status: str
    execution_status: str
    eligible_for_future_removal: bool
    current_exists_in_hot_store: bool
    current_has_silver_job: bool
    current_source_name: str | None
    block_reason: str | None
    source_url: str | None
    raw_data_bytes: int


@dataclass(frozen=True)
class RemovalPlan:
    batch_id: int
    batch_status: str
    review_reason: str
    retention_track: str
    candidate_count: int
    eligible_count: int
    blocked_count: int
    raw_data_bytes: int
    items: list[RemovalPlanItem]


@dataclass(frozen=True)
class RemovalExecutionResult:
    job_observations_deleted: int
    silver_processing_decisions_deleted: int
    raw_jobs_deleted: int
    deleted_raw_job_ids: list[int]


def json_default(value: Any) -> str | int | float:
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def make_json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=json_default))


def load_review_batch(
    connection: psycopg.Connection,
    batch_id: int,
) -> dict[str, Any]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(LOAD_BATCH_SQL, (batch_id,))
        batch = cursor.fetchone()

    if batch is None:
        raise ValueError(f"Historical-burden review batch does not exist: {batch_id}")

    return dict(batch)


def load_review_item_states(
    connection: psycopg.Connection,
    batch_id: int,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(LOAD_REVIEW_ITEM_STATE_SQL, (batch_id,))
        return [dict(row) for row in cursor.fetchall()]


def block_reason_for_row(row: dict[str, Any]) -> str | None:
    if row["execution_status"] != "not_executed":
        return "review_item_already_executed"

    if row["retention_track"] != ARCHIVE_RETENTION_TRACK:
        return "non_archive_retention_track"

    if row["review_status"] != ELIGIBLE_REVIEW_STATUS:
        return "review_status_not_eligible"

    if not row["eligible_for_future_removal"]:
        return "item_not_eligible_for_future_removal"

    if not row["current_exists_in_hot_store"]:
        return "raw_job_missing_from_hot_store"

    if row["current_source_name"] != row["source_name"]:
        return "source_name_changed"

    if row["current_has_silver_job"]:
        return "silver_job_now_exists"

    return None


def plan_item_from_row(row: dict[str, Any]) -> RemovalPlanItem:
    block_reason = block_reason_for_row(row)
    execution_status = READY_EXECUTION_STATUS if block_reason is None else "blocked"

    return RemovalPlanItem(
        review_item_id=int(row["review_item_id"]),
        raw_job_id=int(row["raw_job_id"]),
        source_name=row["source_name"],
        burden_category=row["burden_category"],
        retention_track=row["retention_track"],
        review_status=row["review_status"],
        execution_status=execution_status,
        eligible_for_future_removal=bool(row["eligible_for_future_removal"]),
        current_exists_in_hot_store=bool(row["current_exists_in_hot_store"]),
        current_has_silver_job=bool(row["current_has_silver_job"]),
        current_source_name=row.get("current_source_name"),
        block_reason=block_reason,
        source_url=row.get("source_url"),
        raw_data_bytes=int(row.get("raw_data_bytes") or 0),
    )


def build_removal_plan(
    batch: dict[str, Any],
    rows: Sequence[dict[str, Any]],
) -> RemovalPlan:
    items = [plan_item_from_row(row) for row in rows]
    eligible_count = sum(item.execution_status == READY_EXECUTION_STATUS for item in items)
    blocked_count = len(items) - eligible_count
    raw_data_bytes = sum(item.raw_data_bytes for item in items)

    return RemovalPlan(
        batch_id=int(batch["id"]),
        batch_status=batch["status"],
        review_reason=batch["review_reason"],
        retention_track=batch["retention_track"],
        candidate_count=len(items),
        eligible_count=eligible_count,
        blocked_count=blocked_count,
        raw_data_bytes=raw_data_bytes,
        items=items,
    )


def validate_batch_integrity(batch: dict[str, Any], plan: RemovalPlan) -> None:
    if batch["retention_track"] != ARCHIVE_RETENTION_TRACK:
        raise ValueError(
            "Review batch retention_track must be "
            f"{ARCHIVE_RETENTION_TRACK!r}, got {batch['retention_track']!r}"
        )

    if int(batch["candidate_count"]) != plan.candidate_count:
        raise ValueError(
            "Review batch candidate_count does not match review items: "
            f"{batch['candidate_count']} != {plan.candidate_count}"
        )

    if int(batch["silver_backed_rows"]) != 0:
        raise ValueError("Review batch must not include Silver-backed rows")


def validate_plan_for_approval(batch: dict[str, Any], plan: RemovalPlan) -> None:
    validate_batch_integrity(batch, plan)

    if batch["status"] not in {"proposed", "reviewed"}:
        raise ValueError(
            "Only proposed or reviewed batches can be approved; "
            f"current status is {batch['status']!r}"
        )

    if plan.candidate_count == 0:
        raise ValueError("Review batch has no candidates to approve")

    if plan.blocked_count:
        raise ValueError(
            "Review batch cannot be approved while revalidation has blocked rows"
        )


def validate_plan_for_execution(batch: dict[str, Any], plan: RemovalPlan) -> None:
    validate_batch_integrity(batch, plan)

    if batch["status"] != "approved":
        raise ValueError(
            "Hot-store removal requires an approved DB review batch; "
            f"current status is {batch['status']!r}"
        )

    if plan.candidate_count == 0:
        raise ValueError("Review batch has no candidates to execute")

    if plan.blocked_count:
        raise ValueError(
            "Hot-store removal cannot execute while revalidation has blocked rows"
        )

    if plan.eligible_count == 0:
        raise ValueError("No rows are eligible for hot-store removal")


def approve_review_batch(
    connection: psycopg.Connection,
    batch: dict[str, Any],
    plan: RemovalPlan,
    decision_note: str,
) -> None:
    validate_plan_for_approval(batch, plan)

    with connection.cursor() as cursor:
        cursor.execute(APPROVE_BATCH_SQL, (decision_note, plan.batch_id))
        approved = cursor.fetchone()

    if approved is None:
        raise ValueError(
            "Review batch approval did not update a row. "
            "Reload the batch and check its current status."
        )


def execute_hot_store_removal(
    connection: psycopg.Connection,
    batch: dict[str, Any],
    plan: RemovalPlan,
    execution_note: str,
) -> RemovalExecutionResult:
    validate_plan_for_execution(batch, plan)

    raw_job_ids = [
        item.raw_job_id
        for item in plan.items
        if item.execution_status == READY_EXECUTION_STATUS
    ]

    with connection.cursor() as cursor:
        cursor.execute(DELETE_JOB_OBSERVATIONS_SQL, (raw_job_ids,))
        job_observations_deleted = cursor.rowcount

        cursor.execute(DELETE_SILVER_PROCESSING_DECISIONS_SQL, (raw_job_ids,))
        silver_processing_decisions_deleted = cursor.rowcount

        cursor.execute(DELETE_RAW_JOBS_SQL, (raw_job_ids,))
        deleted_raw_job_ids = sorted(int(row[0]) for row in cursor.fetchall())

        if deleted_raw_job_ids != sorted(raw_job_ids):
            raise ValueError(
                "Deleted raw_jobs do not match approved DB review items. "
                f"expected={sorted(raw_job_ids)}, actual={deleted_raw_job_ids}"
            )

        cursor.execute(
            MARK_ITEMS_REMOVED_SQL,
            (execution_note, plan.batch_id, raw_job_ids),
        )

        cursor.execute(
            MARK_BATCH_EXECUTED_SQL,
            (
                Jsonb(
                    {
                        "last_execution": {
                            "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                            "raw_jobs_deleted": len(deleted_raw_job_ids),
                            "job_observations_deleted": job_observations_deleted,
                            "silver_processing_decisions_deleted": silver_processing_decisions_deleted,
                        }
                    }
                ),
                plan.batch_id,
            ),
        )

    return RemovalExecutionResult(
        job_observations_deleted=job_observations_deleted,
        silver_processing_decisions_deleted=silver_processing_decisions_deleted,
        raw_jobs_deleted=len(deleted_raw_job_ids),
        deleted_raw_job_ids=deleted_raw_job_ids,
    )


def plan_summary(plan: RemovalPlan) -> dict[str, Any]:
    source_counts = Counter(item.source_name for item in plan.items)
    burden_counts = Counter(item.burden_category for item in plan.items)
    execution_status_counts = Counter(item.execution_status for item in plan.items)
    block_reason_counts = Counter(
        item.block_reason or "ready"
        for item in plan.items
    )

    return {
        "batch_id": plan.batch_id,
        "batch_status": plan.batch_status,
        "candidate_count": plan.candidate_count,
        "eligible_count": plan.eligible_count,
        "blocked_count": plan.blocked_count,
        "raw_data_bytes": plan.raw_data_bytes,
        "raw_data_size": format_bytes(plan.raw_data_bytes),
        "source_counts": dict(source_counts),
        "burden_category_counts": dict(burden_counts),
        "execution_status_counts": dict(execution_status_counts),
        "block_reason_counts": dict(block_reason_counts),
    }


def build_execution_manifest(
    plan: RemovalPlan,
    mode: str,
    database_cleanup_action: str,
    result: RemovalExecutionResult | None = None,
) -> dict[str, Any]:
    summary = plan_summary(plan)
    manifest: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "database_cleanup_action": database_cleanup_action,
        "input_source": "approved_db_review_batch" if mode == "execute" else "db_review_batch",
        "batch_id": plan.batch_id,
        "batch_status": plan.batch_status,
        **summary,
        "output_boundary": [
            "This manifest is a human-readable report artifact.",
            "It is not a pipeline input.",
            "It is not an activation gate input.",
            "It is not a destructive-operation input.",
            "Execution decisions are read from database review state by batch_id.",
        ],
    }

    if result is not None:
        manifest["execution_result"] = asdict(result)

    return manifest


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            make_json_safe(payload),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_markdown_report(
    path: Path,
    plan: RemovalPlan,
    mode: str,
    database_cleanup_action: str,
    result: RemovalExecutionResult | None = None,
) -> None:
    summary = plan_summary(plan)

    lines = [
        "# Historical Burden Hot-Store Removal Execution Report",
        "",
        "## Boundary",
        "",
        "This report is generated from DB-backed review state.",
        "",
        "It is a human-readable report artifact only. It must not be used as a pipeline input, activation gate, destructive-operation input, migration input or cloud dependency.",
        "",
        "## Mode",
        "",
        f"- mode: `{mode}`",
        f"- database_cleanup_action: `{database_cleanup_action}`",
        f"- batch_id: `{plan.batch_id}`",
        f"- batch_status_at_load: `{plan.batch_status}`",
        "",
        "## Counts",
        "",
        f"- candidate_count: {summary['candidate_count']}",
        f"- eligible_count: {summary['eligible_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- raw_data_size: {summary['raw_data_size']}",
        "",
        "## Execution Status Counts",
        "",
    ]

    for status, count in sorted(summary["execution_status_counts"].items()):
        lines.append(f"- {status}: {count}")

    lines += ["", "## Block Reason Counts", ""]
    for reason, count in sorted(summary["block_reason_counts"].items()):
        lines.append(f"- {reason}: {count}")

    lines += ["", "## Source Counts", ""]
    for source_name, count in sorted(summary["source_counts"].items()):
        lines.append(f"- {source_name}: {count}")

    if result is not None:
        lines += [
            "",
            "## Execution Result",
            "",
            f"- raw_jobs_deleted: {result.raw_jobs_deleted}",
            f"- job_observations_deleted: {result.job_observations_deleted}",
            f"- silver_processing_decisions_deleted: {result.silver_processing_decisions_deleted}",
        ]

    lines += ["", "## Candidate Samples", ""]
    for item in plan.items[:25]:
        lines.append(f"- `{item.execution_status}` — raw_jobs {item.raw_job_id} — {item.source_name}")
        lines.append(f"  - burden_category: {item.burden_category}")
        lines.append(f"  - block_reason: {item.block_reason or '-'}")
        lines.append(f"  - source_url: {item.source_url or '-'}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_report_artifacts(
    output_dir: Path,
    plan: RemovalPlan,
    mode: str,
    database_cleanup_action: str,
    result: RemovalExecutionResult | None = None,
) -> tuple[Path, Path]:
    report_path = output_dir / EXECUTION_REPORT_FILENAME
    manifest_path = output_dir / EXECUTION_MANIFEST_FILENAME

    write_markdown_report(
        report_path,
        plan=plan,
        mode=mode,
        database_cleanup_action=database_cleanup_action,
        result=result,
    )
    write_json(
        manifest_path,
        build_execution_manifest(
            plan=plan,
            mode=mode,
            database_cleanup_action=database_cleanup_action,
            result=result,
        ),
    )

    return report_path, manifest_path


def load_plan(connection: psycopg.Connection, batch_id: int) -> tuple[dict[str, Any], RemovalPlan]:
    batch = load_review_batch(connection, batch_id)
    rows = load_review_item_states(connection, batch_id)
    plan = build_removal_plan(batch, rows)
    validate_batch_integrity(batch, plan)
    return batch, plan


def run_db_backed_removal(
    batch_id: int,
    output_dir: Path,
    approve: bool = False,
    execute: bool = False,
    confirmation: str | None = None,
    decision_note: str | None = None,
) -> tuple[RemovalPlan, RemovalExecutionResult | None, tuple[Path, Path]]:
    if approve and execute:
        raise ValueError("Choose either approve or execute, not both.")

    if approve and confirmation != APPROVE_CONFIRMATION_ACTION:
        raise ValueError(
            "Approval requires exact confirmation: "
            f"{APPROVE_CONFIRMATION_ACTION}"
        )

    if execute and confirmation != EXECUTE_CONFIRMATION_ACTION:
        raise ValueError(
            "Execution requires exact confirmation: "
            f"{EXECUTE_CONFIRMATION_ACTION}"
        )

    with psycopg.connect(**get_database_config()) as connection:
        batch, plan = load_plan(connection, batch_id)

        if approve:
            approve_review_batch(
                connection,
                batch=batch,
                plan=plan,
                decision_note=decision_note or "Approved via DB-backed guarded removal command.",
            )
            mode = "approve"
            database_cleanup_action = "none"
            result = None
        elif execute:
            result = execute_hot_store_removal(
                connection,
                batch=batch,
                plan=plan,
                execution_note=decision_note or "Executed via DB-backed guarded removal command.",
            )
            mode = "execute"
            database_cleanup_action = "delete_hot_store_rows"
        else:
            mode = "dry_run"
            database_cleanup_action = "none"
            result = None

    artifacts = write_report_artifacts(
        output_dir=output_dir,
        plan=plan,
        mode=mode,
        database_cleanup_action=database_cleanup_action,
        result=result,
    )

    return plan, result, artifacts


def print_summary(
    plan: RemovalPlan,
    result: RemovalExecutionResult | None,
    artifacts: tuple[Path, Path],
) -> None:
    summary = plan_summary(plan)

    print("Historical Burden Hot-Store Removal")
    print(f"batch_id: {plan.batch_id}")
    print(f"batch_status_at_load: {plan.batch_status}")
    print(f"candidate_count: {summary['candidate_count']}")
    print(f"eligible_count: {summary['eligible_count']}")
    print(f"blocked_count: {summary['blocked_count']}")
    print(f"raw_data_size: {summary['raw_data_size']}")

    if result is not None:
        print(f"raw_jobs_deleted: {result.raw_jobs_deleted}")
        print(f"job_observations_deleted: {result.job_observations_deleted}")
        print(
            "silver_processing_decisions_deleted: "
            f"{result.silver_processing_decisions_deleted}"
        )

    print("Exported report artifacts:")
    for path in artifacts:
        print(f"- {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Local output directory for human-readable report artifacts only.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Approve a proposed/reviewed DB batch without deleting rows.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute hot-store removal for an approved DB batch.",
    )
    parser.add_argument(
        "--confirm",
        help="Required exact confirmation text for approve or execute mode.",
    )
    parser.add_argument(
        "--decision-note",
        help="Optional approval/execution note stored in the database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan, result, artifacts = run_db_backed_removal(
        batch_id=args.batch_id,
        output_dir=args.output_dir,
        approve=args.approve,
        execute=args.execute,
        confirmation=args.confirm,
        decision_note=args.decision_note,
    )
    print_summary(plan, result, artifacts)


if __name__ == "__main__":
    main()
