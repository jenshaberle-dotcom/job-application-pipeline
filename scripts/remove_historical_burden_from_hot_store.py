"""Guarded hot-store removal command for archived historical burden.

This is the first workflow that can remove historical burden rows from the
local hot-store database, but only when explicitly executed with multiple
confirmations. By default it runs as a dry-run and writes a local execution-plan
artifact.

The command consumes the review artifact produced by:

    python -m scripts.prepare_historical_burden_hot_store_removal

Safety model:
- default mode performs no database mutation
- execute mode requires explicit confirmation flags
- only archive_before_hot_store_removal_candidate rows are eligible
- only rows with eligible_after_archive_review are eligible
- rows that now have Silver evidence are blocked
- rows whose current classification changed are blocked
- dependent Bronze-side review evidence is removed before raw_jobs

Usage:
    python -m scripts.remove_historical_burden_from_hot_store

    python -m scripts.remove_historical_burden_from_hot_store \
      --review-dir exports/historical_burden_hot_store_removal_review \
      --output-dir exports/historical_burden_hot_store_removal_execution

Execute mode intentionally requires noisy confirmations. Do not run execute mode
until the dry-run output has been reviewed and committed documentation exists.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.export_historical_burden_archive import (
    ARCHIVE_RETENTION_TRACK,
    json_default,
)
from scripts.prepare_historical_burden_hot_store_removal import (
    REMOVAL_CANDIDATES_FILENAME,
    REMOVAL_MANIFEST_FILENAME,
    compute_sha256,
    load_current_hot_store_state,
)
from scripts.review_historical_burden_candidates import format_bytes
from src.config import get_database_config


DEFAULT_REVIEW_DIR = Path("exports/historical_burden_hot_store_removal_review")
DEFAULT_OUTPUT_DIR = Path("exports/historical_burden_hot_store_removal_execution")

REMOVAL_PLAN_FILENAME = "historical_burden_hot_store_removal_execution_plan.csv"
REMOVAL_EXECUTION_MANIFEST_FILENAME = (
    "historical_burden_hot_store_removal_execution_manifest.json"
)

EXECUTE_CONFIRMATION_ACTION = "remove_archived_historical_burden_from_hot_store"
ELIGIBLE_REVIEW_STATUS = "eligible_after_archive_review"


@dataclass(frozen=True)
class RemovalReviewCandidate:
    raw_job_id: int
    source_name: str
    archived_burden_category: str
    current_burden_category: str
    retention_track: str
    exists_in_hot_store: bool
    has_silver_job_now: bool
    still_archive_candidate: bool
    eligible_for_future_removal: bool
    review_status: str
    external_job_id: str | None
    source_url: str | None
    fetched_at: str | None
    initial_profile_name: str
    initial_search_term_snapshot: str
    raw_data_bytes: int


@dataclass(frozen=True)
class CurrentEligibilityResult:
    candidate: RemovalReviewCandidate
    eligible_now: bool
    status: str


@dataclass(frozen=True)
class ConfirmationSettings:
    confirm_retention_track: str | None
    confirm_candidate_count: int | None
    confirm_candidates_sha256: str | None
    confirm_cleanup_action: str | None
    allow_sources: frozenset[str]


@dataclass(frozen=True)
class HotStoreRemovalResult:
    requested_raw_job_ids: int
    deleted_job_observations: int
    deleted_silver_processing_decisions: int
    deleted_raw_jobs: int


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"true", "t", "1", "yes", "y"}:
        return True
    if normalized in {"false", "f", "0", "no", "n"}:
        return False

    raise ValueError(f"Cannot parse boolean value: {value!r}")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_manifest_path(manifest_path: Path, path_from_manifest: str) -> Path:
    candidate = Path(path_from_manifest)

    if candidate.exists():
        return candidate

    relative_to_manifest = manifest_path.parent / candidate.name
    if relative_to_manifest.exists():
        return relative_to_manifest

    return candidate


def validate_removal_review_manifest(
    manifest_path: Path,
) -> tuple[dict[str, Any], Path]:
    manifest = read_json(manifest_path)

    if manifest.get("database_cleanup_action") != "none":
        raise ValueError("Removal review manifest must prove database_cleanup_action=none")

    if manifest.get("mode") != "hot_store_removal_dry_run_only":
        raise ValueError("Removal review manifest must come from dry-run-only mode")

    if manifest.get("retention_track") != ARCHIVE_RETENTION_TRACK:
        raise ValueError(
            "Removal review manifest retention_track must be "
            f"{ARCHIVE_RETENTION_TRACK!r}"
        )

    if manifest.get("silver_backed_rows_now") != 0:
        raise ValueError("Removal review manifest must not include Silver-backed rows")

    candidates_export = manifest.get("exports", {}).get("removal_candidates_csv", {})
    candidates_path_value = candidates_export.get("path")
    expected_sha256 = candidates_export.get("sha256")

    if not candidates_path_value or not expected_sha256:
        raise ValueError(
            "Removal review manifest must include removal_candidates_csv path and sha256"
        )

    candidates_path = resolve_manifest_path(manifest_path, candidates_path_value)
    if not candidates_path.exists():
        raise FileNotFoundError(f"Removal candidates CSV not found: {candidates_path}")

    actual_sha256 = compute_sha256(candidates_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "Removal candidates checksum mismatch: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

    return manifest, candidates_path


def load_removal_review_candidates(path: Path) -> list[RemovalReviewCandidate]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    candidates: list[RemovalReviewCandidate] = []

    for row in rows:
        candidates.append(
            RemovalReviewCandidate(
                raw_job_id=int(row["raw_job_id"]),
                source_name=row["source_name"],
                archived_burden_category=row["archived_burden_category"],
                current_burden_category=row["current_burden_category"],
                retention_track=row["retention_track"],
                exists_in_hot_store=parse_bool(row["exists_in_hot_store"]),
                has_silver_job_now=parse_bool(row["has_silver_job_now"]),
                still_archive_candidate=parse_bool(row["still_archive_candidate"]),
                eligible_for_future_removal=parse_bool(
                    row["eligible_for_future_removal"]
                ),
                review_status=row["review_status"],
                external_job_id=row.get("external_job_id") or None,
                source_url=row.get("source_url") or None,
                fetched_at=row.get("fetched_at") or None,
                initial_profile_name=row["initial_profile_name"],
                initial_search_term_snapshot=row["initial_search_term_snapshot"],
                raw_data_bytes=int(row.get("raw_data_bytes") or 0),
            )
        )

    return candidates


def select_eligible_review_candidates(
    candidates: Sequence[RemovalReviewCandidate],
) -> list[RemovalReviewCandidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.eligible_for_future_removal
        and candidate.review_status == ELIGIBLE_REVIEW_STATUS
        and candidate.retention_track == ARCHIVE_RETENTION_TRACK
        and candidate.exists_in_hot_store
        and not candidate.has_silver_job_now
        and candidate.still_archive_candidate
    ]


def validate_candidate_set(
    candidates: Sequence[RemovalReviewCandidate],
    eligible_candidates: Sequence[RemovalReviewCandidate],
    manifest: dict[str, Any],
) -> None:
    if manifest.get("candidate_count") != len(candidates):
        raise ValueError(
            "Removal review manifest candidate_count does not match CSV: "
            f"{manifest.get('candidate_count')} != {len(candidates)}"
        )

    if manifest.get("eligible_for_future_removal_count") != len(eligible_candidates):
        raise ValueError(
            "Removal review manifest eligible count does not match CSV: "
            f"{manifest.get('eligible_for_future_removal_count')} "
            f"!= {len(eligible_candidates)}"
        )

    non_archive_tracks = {
        candidate.retention_track
        for candidate in eligible_candidates
        if candidate.retention_track != ARCHIVE_RETENTION_TRACK
    }
    if non_archive_tracks:
        raise ValueError(
            "Eligible candidates contain unexpected retention tracks: "
            f"{sorted(non_archive_tracks)}"
        )

    duplicate_ids = [
        raw_job_id
        for raw_job_id, count in Counter(
            candidate.raw_job_id for candidate in eligible_candidates
        ).items()
        if count > 1
    ]
    if duplicate_ids:
        raise ValueError(f"Duplicate eligible raw_job_id values: {duplicate_ids[:10]}")


def validate_execution_confirmations(
    *,
    execute: bool,
    settings: ConfirmationSettings,
    eligible_candidates: Sequence[RemovalReviewCandidate],
    candidates_sha256: str,
) -> None:
    if not execute:
        return

    if settings.confirm_retention_track != ARCHIVE_RETENTION_TRACK:
        raise ValueError(
            "Execute mode requires --confirm-retention-track "
            f"{ARCHIVE_RETENTION_TRACK}"
        )

    if settings.confirm_candidate_count != len(eligible_candidates):
        raise ValueError(
            "Execute mode requires --confirm-candidate-count to match the "
            f"eligible candidate count ({len(eligible_candidates)})"
        )

    if settings.confirm_candidates_sha256 != candidates_sha256:
        raise ValueError(
            "Execute mode requires --confirm-candidates-sha256 to match the "
            "validated removal candidates CSV checksum"
        )

    if settings.confirm_cleanup_action != EXECUTE_CONFIRMATION_ACTION:
        raise ValueError(
            "Execute mode requires --confirm-cleanup-action "
            f"{EXECUTE_CONFIRMATION_ACTION}"
        )

    candidate_sources = {candidate.source_name for candidate in eligible_candidates}
    if not settings.allow_sources:
        raise ValueError("Execute mode requires at least one --allow-source value")

    if settings.allow_sources != candidate_sources:
        raise ValueError(
            "Execute mode --allow-source values must exactly match candidate sources: "
            f"expected {sorted(candidate_sources)}, got {sorted(settings.allow_sources)}"
        )


def validate_current_eligibility(
    candidates: Sequence[RemovalReviewCandidate],
    current_states: dict[int, Any],
) -> list[CurrentEligibilityResult]:
    results: list[CurrentEligibilityResult] = []

    for candidate in candidates:
        current_state = current_states.get(candidate.raw_job_id)

        if current_state is None:
            results.append(
                CurrentEligibilityResult(
                    candidate=candidate,
                    eligible_now=False,
                    status="blocked_missing_from_hot_store_now",
                )
            )
            continue

        if current_state.source_name != candidate.source_name:
            results.append(
                CurrentEligibilityResult(
                    candidate=candidate,
                    eligible_now=False,
                    status="blocked_source_mismatch_now",
                )
            )
            continue

        if current_state.has_silver_job:
            results.append(
                CurrentEligibilityResult(
                    candidate=candidate,
                    eligible_now=False,
                    status="blocked_silver_evidence_now_exists",
                )
            )
            continue

        if current_state.current_retention_track != ARCHIVE_RETENTION_TRACK:
            results.append(
                CurrentEligibilityResult(
                    candidate=candidate,
                    eligible_now=False,
                    status="blocked_current_classification_changed",
                )
            )
            continue

        results.append(
            CurrentEligibilityResult(
                candidate=candidate,
                eligible_now=True,
                status="eligible_for_guarded_hot_store_removal",
            )
        )

    return results


def plan_row(result: CurrentEligibilityResult) -> dict[str, Any]:
    candidate = result.candidate
    return {
        "raw_job_id": candidate.raw_job_id,
        "source_name": candidate.source_name,
        "archived_burden_category": candidate.archived_burden_category,
        "current_burden_category": candidate.current_burden_category,
        "retention_track": candidate.retention_track,
        "eligible_now": result.eligible_now,
        "plan_status": result.status,
        "external_job_id": candidate.external_job_id,
        "source_url": candidate.source_url,
        "fetched_at": candidate.fetched_at,
        "initial_profile_name": candidate.initial_profile_name,
        "initial_search_term_snapshot": candidate.initial_search_term_snapshot,
        "raw_data_bytes": candidate.raw_data_bytes,
    }


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


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


def execute_hot_store_removal(
    connection: psycopg.Connection,
    raw_job_ids: Sequence[int],
) -> HotStoreRemovalResult:
    if not raw_job_ids:
        return HotStoreRemovalResult(
            requested_raw_job_ids=0,
            deleted_job_observations=0,
            deleted_silver_processing_decisions=0,
            deleted_raw_jobs=0,
        )

    silver_count = count_silver_jobs(connection, raw_job_ids)
    if silver_count:
        raise ValueError(
            "Refusing hot-store removal because Silver-backed rows exist: "
            f"{silver_count}"
        )

    with connection.cursor(row_factory=dict_row) as cursor:
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

    return HotStoreRemovalResult(
        requested_raw_job_ids=len(raw_job_ids),
        deleted_job_observations=deleted_observations,
        deleted_silver_processing_decisions=deleted_decisions,
        deleted_raw_jobs=deleted_raw_jobs,
    )


def build_execution_manifest(
    *,
    execute: bool,
    manifest: dict[str, Any],
    review_candidates_sha256: str,
    current_results: Sequence[CurrentEligibilityResult],
    plan_path: Path,
    removal_result: HotStoreRemovalResult | None,
) -> dict[str, Any]:
    status_counts = Counter(result.status for result in current_results)
    source_counts = Counter(result.candidate.source_name for result in current_results)
    category_counts = Counter(
        result.candidate.archived_burden_category for result in current_results
    )
    eligible_now_count = sum(int(result.eligible_now) for result in current_results)
    raw_data_bytes = sum(result.candidate.raw_data_bytes for result in current_results)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "execute_guarded_hot_store_removal" if execute else "dry_run_only",
        "database_cleanup_action": (
            EXECUTE_CONFIRMATION_ACTION if execute else "none"
        ),
        "retention_track": ARCHIVE_RETENTION_TRACK,
        "source_review_manifest_generated_at_utc": manifest.get("generated_at_utc"),
        "source_review_candidate_count": manifest.get("candidate_count"),
        "source_review_candidates_sha256": review_candidates_sha256,
        "planned_candidate_count": len(current_results),
        "eligible_now_count": eligible_now_count,
        "blocked_now_count": len(current_results) - eligible_now_count,
        "plan_status_counts": dict(status_counts),
        "source_counts": dict(source_counts),
        "archived_burden_category_counts": dict(category_counts),
        "raw_data_bytes": raw_data_bytes,
        "raw_data_size": format_bytes(raw_data_bytes),
        "executed_removal": removal_result is not None,
        "removal_result": (
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
        "exports": {
            "execution_plan_csv": {
                "path": str(plan_path),
                "size_bytes": plan_path.stat().st_size,
                "sha256": compute_sha256(plan_path),
            }
        },
        "interpretation_boundary": [
            "Dry-run mode performs no database mutation.",
            "Execute mode requires explicit confirmation flags and validated review artifacts.",
            "Silver-backed rows and changed classifications are blocked before removal.",
            "This workflow removes only hot-store rows and their dependent Bronze-side review evidence; archive artifacts remain separate.",
        ],
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
        encoding="utf-8",
    )


def print_summary(
    *,
    execute: bool,
    current_results: Sequence[CurrentEligibilityResult],
    removal_result: HotStoreRemovalResult | None,
) -> None:
    status_counts = Counter(result.status for result in current_results)
    source_counts = Counter(result.candidate.source_name for result in current_results)
    eligible_now_count = sum(int(result.eligible_now) for result in current_results)

    print()
    print("Historical Burden Guarded Hot-Store Removal")
    print(f"Mode: {'EXECUTE' if execute else 'dry-run only'}")
    print(
        "Database cleanup action: "
        f"{EXECUTE_CONFIRMATION_ACTION if execute else 'none'}"
    )
    print(f"Retention track: {ARCHIVE_RETENTION_TRACK}")
    print(f"Planned candidates: {len(current_results)}")
    print(f"Eligible now: {eligible_now_count}")
    print(f"Blocked now: {len(current_results) - eligible_now_count}")
    print()
    print("Rows by source:")
    for source_name, count in source_counts.most_common():
        print(f"- {source_name}: {count}")
    print()
    print("Rows by plan status:")
    for status, count in status_counts.most_common():
        print(f"- {status}: {count}")

    if removal_result is not None:
        print()
        print("Executed removal:")
        print(f"- raw_jobs: {removal_result.deleted_raw_jobs}")
        print(f"- job_observations: {removal_result.deleted_job_observations}")
        print(
            "- silver_processing_decisions: "
            f"{removal_result.deleted_silver_processing_decisions}"
        )


def run_guarded_removal(
    *,
    review_dir: Path,
    output_dir: Path,
    execute: bool,
    confirmation_settings: ConfirmationSettings,
) -> None:
    manifest_path = review_dir / REMOVAL_MANIFEST_FILENAME
    manifest, candidates_path = validate_removal_review_manifest(manifest_path)
    review_candidates_sha256 = compute_sha256(candidates_path)

    candidates = load_removal_review_candidates(candidates_path)
    eligible_candidates = select_eligible_review_candidates(candidates)
    validate_candidate_set(candidates, eligible_candidates, manifest)

    validate_execution_confirmations(
        execute=execute,
        settings=confirmation_settings,
        eligible_candidates=eligible_candidates,
        candidates_sha256=review_candidates_sha256,
    )

    raw_job_ids = [candidate.raw_job_id for candidate in eligible_candidates]

    with psycopg.connect(**get_database_config()) as connection:
        current_states = load_current_hot_store_state(connection, raw_job_ids)
        current_results = validate_current_eligibility(
            eligible_candidates,
            current_states,
        )

        blocked_now_count = sum(int(not result.eligible_now) for result in current_results)
        if execute and blocked_now_count:
            raise ValueError(
                "Refusing execute mode because current eligibility changed; "
                f"blocked_now_count={blocked_now_count}"
            )

        plan_path = output_dir / REMOVAL_PLAN_FILENAME
        write_csv(plan_path, [plan_row(result) for result in current_results])

        removal_result: HotStoreRemovalResult | None = None
        if execute:
            removal_result = execute_hot_store_removal(connection, raw_job_ids)
            connection.commit()

    execution_manifest = build_execution_manifest(
        execute=execute,
        manifest=manifest,
        review_candidates_sha256=review_candidates_sha256,
        current_results=current_results,
        plan_path=plan_path,
        removal_result=removal_result,
    )
    execution_manifest_path = output_dir / REMOVAL_EXECUTION_MANIFEST_FILENAME
    write_manifest(execution_manifest_path, execution_manifest)

    print_summary(
        execute=execute,
        current_results=current_results,
        removal_result=removal_result,
    )
    print()
    print("Exported guarded hot-store removal files:")
    print(f"- {plan_path}")
    print(f"- {execution_manifest_path}")
    print()
    print("Interpretation boundary:")
    if execute:
        print("- Execute mode removed eligible rows from the hot-store database.")
        print("- Archive evidence remains in the previously generated archive artifacts.")
    else:
        print("- Dry-run mode did not remove rows from the database.")
        print("- Re-run with explicit execute confirmations only after review.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--review-dir",
        type=Path,
        default=DEFAULT_REVIEW_DIR,
        help="Directory containing the hot-store removal dry-run review manifest and CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Local output directory for guarded removal plan/execution artifacts.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually remove eligible rows from the hot store. Requires confirmation flags.",
    )
    parser.add_argument(
        "--confirm-retention-track",
        help="Required in execute mode. Must equal archive_before_hot_store_removal_candidate.",
    )
    parser.add_argument(
        "--confirm-candidate-count",
        type=int,
        help="Required in execute mode. Must match the current eligible candidate count.",
    )
    parser.add_argument(
        "--confirm-candidates-sha256",
        help="Required in execute mode. Must match the validated candidates CSV sha256.",
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
        help="Required in execute mode. Repeat once per expected candidate source.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    confirmation_settings = ConfirmationSettings(
        confirm_retention_track=args.confirm_retention_track,
        confirm_candidate_count=args.confirm_candidate_count,
        confirm_candidates_sha256=args.confirm_candidates_sha256,
        confirm_cleanup_action=args.confirm_cleanup_action,
        allow_sources=frozenset(args.allow_source),
    )
    run_guarded_removal(
        review_dir=args.review_dir,
        output_dir=args.output_dir,
        execute=args.execute,
        confirmation_settings=confirmation_settings,
    )


if __name__ == "__main__":
    main()
