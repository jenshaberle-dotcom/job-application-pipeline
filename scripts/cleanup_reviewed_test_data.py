"""Guarded cleanup command for reviewed test/transient Bronze rows.

This workflow is intentionally separate from historical-burden archive removal.
It targets only rows classified as delete_candidate_after_review, such as
manual_test/test source rows, and defaults to dry-run mode.

Safety model:
- default mode performs no database mutation
- execute mode requires explicit confirmation flags
- only delete_candidate_after_review rows are eligible
- Silver-backed rows are always blocked
- allowed source names must be explicit in execute mode

Usage:
    python -m scripts.cleanup_reviewed_test_data

    python -m scripts.cleanup_reviewed_test_data \
      --output-dir exports/reviewed_test_data_cleanup

Execute mode intentionally requires noisy confirmations. Run the dry-run first,
review the exported plan and manifest, then provide exact confirmation values.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from scripts.prepare_historical_burden_hot_store_removal import compute_sha256
from scripts.review_historical_burden_candidates import (
    HistoricalBurdenCandidate,
    format_bytes,
    load_candidates,
)
from src.config import get_database_config


DEFAULT_OUTPUT_DIR = Path("exports/reviewed_test_data_cleanup")
DEFAULT_DRY_RUN_SOURCES = frozenset({"manual_test", "test"})

DELETE_RETENTION_TRACK = "delete_candidate_after_review"
EXECUTE_CONFIRMATION_ACTION = "delete_reviewed_test_data_from_hot_store"

TEST_DATA_CLEANUP_PLAN_FILENAME = "reviewed_test_data_cleanup_plan.csv"
TEST_DATA_CLEANUP_MANIFEST_FILENAME = "reviewed_test_data_cleanup_manifest.json"

TEST_DATA_CLEANUP_PLAN_FIELDNAMES = [
    "raw_job_id",
    "source_name",
    "burden_category",
    "retention_track",
    "review_action",
    "eligible_now",
    "plan_status",
    "external_job_id",
    "source_url",
    "fetched_at",
    "initial_profile_name",
    "initial_search_term_snapshot",
    "has_silver_job",
    "processing_decision",
    "raw_data_bytes",
    "title_preview",
    "company_preview",
]


@dataclass(frozen=True)
class ConfirmationSettings:
    confirm_retention_track: str | None
    confirm_candidate_count: int | None
    confirm_candidates_sha256: str | None
    confirm_cleanup_action: str | None
    allow_sources: frozenset[str]


@dataclass(frozen=True)
class TestDataCleanupResult:
    requested_raw_job_ids: int
    deleted_job_observations: int
    deleted_silver_processing_decisions: int
    deleted_raw_jobs: int


@dataclass(frozen=True)
class ReviewedTestDataCleanupCandidate:
    raw_job_id: int
    source_name: str
    burden_category: str
    retention_track: str
    review_action: str
    external_job_id: str | None
    source_url: str | None
    fetched_at: Any
    initial_profile_name: str
    initial_search_term_snapshot: str
    has_silver_job: bool
    processing_decision: str
    raw_data_bytes: int
    title_preview: str
    company_preview: str
    eligible_now: bool
    plan_status: str


def candidate_from_burden_candidate(
    candidate: HistoricalBurdenCandidate,
) -> ReviewedTestDataCleanupCandidate:
    if candidate.has_silver_job:
        eligible_now = False
        plan_status = "blocked_silver_evidence_now_exists"
    elif candidate.retention_track != DELETE_RETENTION_TRACK:
        eligible_now = False
        plan_status = "blocked_not_delete_candidate_after_review"
    else:
        eligible_now = True
        plan_status = "eligible_for_reviewed_test_data_cleanup"

    return ReviewedTestDataCleanupCandidate(
        raw_job_id=candidate.raw_job_id,
        source_name=candidate.source_name,
        burden_category=candidate.burden_category,
        retention_track=candidate.retention_track,
        review_action=candidate.review_action,
        external_job_id=candidate.external_job_id,
        source_url=candidate.source_url,
        fetched_at=candidate.fetched_at,
        initial_profile_name=candidate.initial_profile_name,
        initial_search_term_snapshot=candidate.initial_search_term_snapshot,
        has_silver_job=candidate.has_silver_job,
        processing_decision=candidate.processing_decision,
        raw_data_bytes=candidate.raw_data_bytes,
        title_preview=candidate.title_preview,
        company_preview=candidate.company_preview,
        eligible_now=eligible_now,
        plan_status=plan_status,
    )


def select_reviewed_test_data_candidates(
    candidates: Iterable[HistoricalBurdenCandidate],
    allowed_sources: frozenset[str],
) -> list[ReviewedTestDataCleanupCandidate]:
    selected: list[ReviewedTestDataCleanupCandidate] = []

    for candidate in candidates:
        if candidate.source_name not in allowed_sources:
            continue
        if candidate.retention_track != DELETE_RETENTION_TRACK:
            continue

        selected.append(candidate_from_burden_candidate(candidate))

    return selected


def candidate_row(candidate: ReviewedTestDataCleanupCandidate) -> dict[str, Any]:
    return {
        "raw_job_id": candidate.raw_job_id,
        "source_name": candidate.source_name,
        "burden_category": candidate.burden_category,
        "retention_track": candidate.retention_track,
        "review_action": candidate.review_action,
        "eligible_now": candidate.eligible_now,
        "plan_status": candidate.plan_status,
        "external_job_id": candidate.external_job_id,
        "source_url": candidate.source_url,
        "fetched_at": candidate.fetched_at,
        "initial_profile_name": candidate.initial_profile_name,
        "initial_search_term_snapshot": candidate.initial_search_term_snapshot,
        "has_silver_job": candidate.has_silver_job,
        "processing_decision": candidate.processing_decision,
        "raw_data_bytes": candidate.raw_data_bytes,
        "title_preview": candidate.title_preview,
        "company_preview": candidate.company_preview,
    }


def write_csv(
    path: Path,
    rows: Sequence[dict[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")


def count_silver_jobs(connection: psycopg.Connection, raw_job_ids: Sequence[int]) -> int:
    if not raw_job_ids:
        return 0

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM silver_jobs WHERE raw_job_id = ANY(%s);",
            (list(raw_job_ids),),
        )
        value = cursor.fetchone()[0]

    return int(value)


def execute_reviewed_test_data_cleanup(
    connection: psycopg.Connection,
    raw_job_ids: Sequence[int],
) -> TestDataCleanupResult:
    if not raw_job_ids:
        return TestDataCleanupResult(
            requested_raw_job_ids=0,
            deleted_job_observations=0,
            deleted_silver_processing_decisions=0,
            deleted_raw_jobs=0,
        )

    silver_count = count_silver_jobs(connection, raw_job_ids)
    if silver_count:
        raise ValueError(
            "Refusing test-data cleanup because Silver-backed rows exist: "
            f"{silver_count}"
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH candidate_ids AS (
                SELECT unnest(%s::bigint[]) AS raw_job_id
            )
            DELETE FROM job_observations jo
            USING candidate_ids c
            WHERE jo.raw_job_id = c.raw_job_id
            RETURNING jo.id;
            """,
            (list(raw_job_ids),),
        )
        deleted_observations = len(cursor.fetchall())

        cursor.execute(
            """
            WITH candidate_ids AS (
                SELECT unnest(%s::bigint[]) AS raw_job_id
            )
            DELETE FROM silver_processing_decisions spd
            USING candidate_ids c
            WHERE spd.raw_job_id = c.raw_job_id
            RETURNING spd.id;
            """,
            (list(raw_job_ids),),
        )
        deleted_decisions = len(cursor.fetchall())

        cursor.execute(
            """
            WITH candidate_ids AS (
                SELECT unnest(%s::bigint[]) AS raw_job_id
            )
            DELETE FROM raw_jobs rj
            USING candidate_ids c
            WHERE rj.id = c.raw_job_id
            RETURNING rj.id;
            """,
            (list(raw_job_ids),),
        )
        deleted_raw_jobs = len(cursor.fetchall())

    if deleted_raw_jobs != len(raw_job_ids):
        raise ValueError(
            "Deleted raw_jobs count does not match requested ids: "
            f"{deleted_raw_jobs} != {len(raw_job_ids)}"
        )

    return TestDataCleanupResult(
        requested_raw_job_ids=len(raw_job_ids),
        deleted_job_observations=deleted_observations,
        deleted_silver_processing_decisions=deleted_decisions,
        deleted_raw_jobs=deleted_raw_jobs,
    )


def validate_execution_confirmations(
    *,
    execute: bool,
    settings: ConfirmationSettings,
    eligible_candidates: Sequence[ReviewedTestDataCleanupCandidate],
    candidates_sha256: str,
) -> None:
    if not execute:
        return

    if settings.confirm_retention_track != DELETE_RETENTION_TRACK:
        raise ValueError(
            "Execute mode requires --confirm-retention-track "
            f"{DELETE_RETENTION_TRACK}"
        )

    if settings.confirm_candidate_count != len(eligible_candidates):
        raise ValueError(
            "Execute mode requires --confirm-candidate-count to match the "
            f"eligible candidate count ({len(eligible_candidates)})"
        )

    if settings.confirm_candidates_sha256 != candidates_sha256:
        raise ValueError(
            "Execute mode requires --confirm-candidates-sha256 to match the "
            "generated cleanup plan CSV checksum"
        )

    if settings.confirm_cleanup_action != EXECUTE_CONFIRMATION_ACTION:
        raise ValueError(
            "Execute mode requires --confirm-cleanup-action "
            f"{EXECUTE_CONFIRMATION_ACTION}"
        )

    if not settings.allow_sources:
        raise ValueError("Execute mode requires at least one --allow-source value")

    candidate_sources = {candidate.source_name for candidate in eligible_candidates}
    if settings.allow_sources != candidate_sources:
        raise ValueError(
            "Execute mode --allow-source values must exactly match candidate sources: "
            f"expected {sorted(candidate_sources)}, got {sorted(settings.allow_sources)}"
        )


def build_manifest(
    *,
    execute: bool,
    candidates: Sequence[ReviewedTestDataCleanupCandidate],
    plan_path: Path,
    plan_sha256: str,
    removal_result: TestDataCleanupResult | None,
) -> dict[str, Any]:
    eligible_count = sum(int(candidate.eligible_now) for candidate in candidates)
    raw_data_bytes = sum(candidate.raw_data_bytes for candidate in candidates)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "execute_reviewed_test_data_cleanup" if execute else "dry_run_only",
        "database_cleanup_action": EXECUTE_CONFIRMATION_ACTION if execute else "none",
        "retention_track": DELETE_RETENTION_TRACK,
        "candidate_count": len(candidates),
        "eligible_now_count": eligible_count,
        "blocked_now_count": len(candidates) - eligible_count,
        "source_counts": dict(Counter(candidate.source_name for candidate in candidates)),
        "burden_category_counts": dict(Counter(candidate.burden_category for candidate in candidates)),
        "plan_status_counts": dict(Counter(candidate.plan_status for candidate in candidates)),
        "silver_backed_rows": sum(int(candidate.has_silver_job) for candidate in candidates),
        "raw_data_bytes": raw_data_bytes,
        "raw_data_size": format_bytes(raw_data_bytes),
        "exports": {
            "cleanup_plan_csv": {
                "path": str(plan_path),
                "sha256": plan_sha256,
                "size_bytes": plan_path.stat().st_size,
            }
        },
        "executed_cleanup": removal_result is not None,
        "cleanup_result_status": "executed" if removal_result is not None else "not_executed",
        "cleanup_result": (
            {
                "requested_raw_job_ids": removal_result.requested_raw_job_ids,
                "deleted_job_observations": removal_result.deleted_job_observations,
                "deleted_silver_processing_decisions": (
                    removal_result.deleted_silver_processing_decisions
                ),
                "deleted_raw_jobs": removal_result.deleted_raw_jobs,
            }
            if removal_result is not None
            else None
        ),
        "interpretation_boundary": [
            "This workflow is for reviewed test/transient rows, not historical burden archive candidates.",
            "archive_before_hot_store_removal_candidate rows must be handled by the separate archive/removal workflow.",
            "Silver-backed rows must remain blocked from cleanup.",
        ],
    }


def format_counter_for_console(counter: Counter[str]) -> str:
    if not counter:
        return "<none>"

    return str(dict(counter))


def print_summary(
    *,
    execute: bool,
    candidates: Sequence[ReviewedTestDataCleanupCandidate],
    removal_result: TestDataCleanupResult | None,
) -> None:
    eligible_count = sum(int(candidate.eligible_now) for candidate in candidates)
    source_counts = Counter(candidate.source_name for candidate in candidates)
    status_counts = Counter(candidate.plan_status for candidate in candidates)

    print("Reviewed Test Data Cleanup")
    print("Mode:", "execute" if execute else "dry-run only")
    print("Database cleanup action:", EXECUTE_CONFIRMATION_ACTION if execute else "none")
    print("Retention track:", DELETE_RETENTION_TRACK)
    print("Candidate rows:", len(candidates))
    print("Eligible now:", eligible_count)
    print("Blocked now:", len(candidates) - eligible_count)
    print("Source counts:", format_counter_for_console(source_counts))
    print("Plan status counts:", format_counter_for_console(status_counts))
    print(
        "Cleanup result:",
        "not executed" if removal_result is None else "executed",
    )

    if removal_result is not None:
        print("Deleted raw_jobs:", removal_result.deleted_raw_jobs)
        print("Deleted job_observations:", removal_result.deleted_job_observations)
        print(
            "Deleted silver_processing_decisions:",
            removal_result.deleted_silver_processing_decisions,
        )


def run_cleanup(
    *,
    output_dir: Path,
    execute: bool,
    effective_allowed_sources: frozenset[str],
    confirmation_settings: ConfirmationSettings,
) -> None:
    with psycopg.connect(**get_database_config()) as connection:
        burden_candidates = load_candidates(connection)
        cleanup_candidates = select_reviewed_test_data_candidates(
            candidates=burden_candidates,
            allowed_sources=effective_allowed_sources,
        )

        blocked_count = sum(int(not candidate.eligible_now) for candidate in cleanup_candidates)
        if execute and blocked_count:
            raise ValueError(
                "Refusing execute mode because cleanup candidates are blocked; "
                f"blocked_count={blocked_count}"
            )

        plan_path = output_dir / TEST_DATA_CLEANUP_PLAN_FILENAME
        write_csv(
            plan_path,
            [candidate_row(candidate) for candidate in cleanup_candidates],
            TEST_DATA_CLEANUP_PLAN_FIELDNAMES,
        )
        plan_sha256 = compute_sha256(plan_path)

        eligible_candidates = [
            candidate for candidate in cleanup_candidates if candidate.eligible_now
        ]
        validate_execution_confirmations(
            execute=execute,
            settings=confirmation_settings,
            eligible_candidates=eligible_candidates,
            candidates_sha256=plan_sha256,
        )

        removal_result: TestDataCleanupResult | None = None
        if execute:
            removal_result = execute_reviewed_test_data_cleanup(
                connection,
                [candidate.raw_job_id for candidate in eligible_candidates],
            )
            connection.commit()

    manifest = build_manifest(
        execute=execute,
        candidates=cleanup_candidates,
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        removal_result=removal_result,
    )
    manifest_path = output_dir / TEST_DATA_CLEANUP_MANIFEST_FILENAME
    write_manifest(manifest_path, manifest)

    print_summary(
        execute=execute,
        candidates=cleanup_candidates,
        removal_result=removal_result,
    )
    print()
    print("Exported reviewed test-data cleanup files:")
    print(f"- {plan_path}")
    print(f"- {manifest_path}")
    print()
    print("Interpretation boundary:")
    if execute:
        print("- Execute mode removed only reviewed test/transient rows.")
        print("- Historical burden archive candidates were not touched.")
    else:
        print("- Dry-run mode did not remove rows from the database.")
        print("- Re-run with explicit execute confirmations only after review.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Local output directory for reviewed test-data cleanup artifacts.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete eligible reviewed test-data rows. Requires confirmation flags.",
    )
    parser.add_argument(
        "--confirm-retention-track",
        help="Required in execute mode. Must equal delete_candidate_after_review.",
    )
    parser.add_argument(
        "--confirm-candidate-count",
        type=int,
        help="Required in execute mode. Must match the current eligible candidate count.",
    )
    parser.add_argument(
        "--confirm-candidates-sha256",
        help="Required in execute mode. Must match the generated cleanup plan CSV sha256.",
    )
    parser.add_argument(
        "--confirm-cleanup-action",
        help=(
            "Required in execute mode. Must equal "
            f"{EXECUTE_CONFIRMATION_ACTION}."
        ),
    )
    parser.add_argument(
        "--allow-source",
        action="append",
        default=[],
        help="Required in execute mode. Repeat once per expected test/transient source.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    explicit_allowed_sources = frozenset(args.allow_source)
    effective_allowed_sources = explicit_allowed_sources or DEFAULT_DRY_RUN_SOURCES

    confirmation_settings = ConfirmationSettings(
        confirm_retention_track=args.confirm_retention_track,
        confirm_candidate_count=args.confirm_candidate_count,
        confirm_candidates_sha256=args.confirm_candidates_sha256,
        confirm_cleanup_action=args.confirm_cleanup_action,
        allow_sources=explicit_allowed_sources,
    )

    run_cleanup(
        output_dir=args.output_dir,
        execute=args.execute,
        effective_allowed_sources=effective_allowed_sources,
        confirmation_settings=confirmation_settings,
    )


if __name__ == "__main__":
    main()
