"""Prepare a DB-backed review batch for historical-burden hot-store removal.

This script creates a database-backed review batch for historical burden rows that
may later be eligible for guarded hot-store removal.

It does not delete, update or archive raw_jobs. Generated Markdown/JSON files are
human-readable review artifacts only. They are not pipeline inputs, activation
gates, execution inputs, migration inputs or cloud dependencies.

Usage:
    python -m scripts.prepare_historical_burden_hot_store_removal
    python -m scripts.prepare_historical_burden_hot_store_removal \
      --export-dir exports/historical_burden_hot_store_removal_review
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scripts.export_historical_burden_archive import ARCHIVE_RETENTION_TRACK
from scripts.review_historical_burden_candidates import (
    classify_retention_track,
    format_bytes,
)
from src.config import get_database_config


DEFAULT_EXPORT_DIR = Path("exports/historical_burden_hot_store_removal_review")

REVIEW_MANIFEST_FILENAME = "historical_burden_hot_store_removal_review_manifest.json"
REVIEW_MARKDOWN_FILENAME = "historical_burden_hot_store_removal_review.md"


REVIEW_REASON = (
    "DB-backed historical burden hot-store removal review. "
    "No local candidate file is used as execution input."
)

LOAD_REVIEW_CANDIDATE_ROWS_SQL = """
SELECT
    rj.id AS raw_job_id,
    rj.source_name,
    rj.external_job_id,
    rj.source_url,
    rj.fetched_at,
    rj.ingestion_run_id,
    rj.search_profile_id,
    COALESCE(sp.profile_name, '<missing_profile>') AS initial_profile_name,
    COALESCE(ir.search_term, '<multi-term_or_missing>') AS initial_search_term_snapshot,
    pg_column_size(rj.raw_data) AS raw_data_bytes,
    sj.id IS NOT NULL AS has_silver_job,
    CASE
        WHEN rj.source_name IN ('manual_test', 'test')
            THEN 'test_data'
        WHEN COALESCE(sp.profile_name, '') ILIKE '%%test%%'
            THEN 'possible_test_data'
        WHEN rj.ingestion_run_id IS NULL OR rj.search_profile_id IS NULL
            THEN 'missing_lineage'
        WHEN rj.source_name LIKE 'greenhouse:%%' AND ir.search_term = '*'
            THEN 'greenhouse_legacy_wildcard'
        WHEN rj.source_name LIKE 'greenhouse:%%' AND NOT (rj.raw_data ? 'matching')
            THEN 'greenhouse_without_current_matching_metadata'
        WHEN rj.source_name LIKE 'personio:%%' AND NOT (rj.raw_data ? 'matching')
            THEN 'personio_without_current_matching_metadata'
        WHEN rj.source_name = 'stepstone'
            THEN 'commercial_aggregator_history'
        ELSE 'ordinary_operational_history'
    END AS burden_category
FROM raw_jobs rj
LEFT JOIN ingestion_runs ir
    ON ir.id = rj.ingestion_run_id
LEFT JOIN search_profiles sp
    ON sp.id = rj.search_profile_id
LEFT JOIN silver_jobs sj
    ON sj.raw_job_id = rj.id
ORDER BY
    rj.fetched_at,
    rj.id;
"""

INSERT_REVIEW_BATCH_SQL = """
INSERT INTO historical_burden_review_batches (
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
    metadata
)
VALUES (
    'proposed',
    %(review_reason)s,
    %(retention_track)s,
    %(candidate_count)s,
    %(eligible_for_removal_count)s,
    %(blocked_or_non_actionable_count)s,
    %(silver_backed_rows)s,
    %(source_counts)s,
    %(burden_category_counts)s,
    %(review_status_counts)s,
    %(raw_data_bytes)s,
    %(metadata)s
)
RETURNING id;
"""

INSERT_REVIEW_ITEM_SQL = """
INSERT INTO historical_burden_review_items (
    batch_id,
    raw_job_id,
    source_name,
    external_job_id,
    source_url,
    fetched_at,
    ingestion_run_id,
    search_profile_id,
    initial_profile_name,
    initial_search_term_snapshot,
    burden_category,
    retention_track,
    exists_in_hot_store,
    has_silver_job_now,
    still_archive_candidate,
    eligible_for_future_removal,
    review_status,
    raw_data_bytes,
    item_snapshot
)
VALUES (
    %(batch_id)s,
    %(raw_job_id)s,
    %(source_name)s,
    %(external_job_id)s,
    %(source_url)s,
    %(fetched_at)s,
    %(ingestion_run_id)s,
    %(search_profile_id)s,
    %(initial_profile_name)s,
    %(initial_search_term_snapshot)s,
    %(burden_category)s,
    %(retention_track)s,
    %(exists_in_hot_store)s,
    %(has_silver_job_now)s,
    %(still_archive_candidate)s,
    %(eligible_for_future_removal)s,
    %(review_status)s,
    %(raw_data_bytes)s,
    %(item_snapshot)s
);
"""


@dataclass(frozen=True)
class CurrentHotStoreState:
    raw_job_id: int
    source_name: str
    initial_profile_name: str
    initial_search_term_snapshot: str
    current_burden_category: str
    current_retention_track: str
    has_silver_job: bool


@dataclass(frozen=True)
class HotStoreRemovalCandidate:
    raw_job_id: int
    source_name: str
    burden_category: str
    retention_track: str
    exists_in_hot_store: bool
    has_silver_job_now: bool
    still_archive_candidate: bool
    eligible_for_future_removal: bool
    review_status: str
    external_job_id: str | None
    source_url: str | None
    fetched_at: Any
    ingestion_run_id: int | None
    search_profile_id: int | None
    initial_profile_name: str
    initial_search_term_snapshot: str
    raw_data_bytes: int


def json_default(value: Any) -> str | int | float:
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_current_hot_store_candidates(
    connection: psycopg.Connection,
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(LOAD_REVIEW_CANDIDATE_ROWS_SQL)
        return [dict(row) for row in cursor.fetchall()]


def candidate_from_row(row: dict[str, Any]) -> HotStoreRemovalCandidate | None:
    burden_category = row["burden_category"]
    has_silver_job_now = bool(row["has_silver_job"])
    retention_track = classify_retention_track(
        burden_category=burden_category,
        has_silver_job=has_silver_job_now,
    )

    if retention_track != ARCHIVE_RETENTION_TRACK:
        return None

    review_status = "eligible_after_db_review"
    exists_in_hot_store = True
    still_archive_candidate = True
    eligible_for_future_removal = True

    return HotStoreRemovalCandidate(
        raw_job_id=int(row["raw_job_id"]),
        source_name=row["source_name"],
        burden_category=burden_category,
        retention_track=retention_track,
        exists_in_hot_store=exists_in_hot_store,
        has_silver_job_now=has_silver_job_now,
        still_archive_candidate=still_archive_candidate,
        eligible_for_future_removal=eligible_for_future_removal,
        review_status=review_status,
        external_job_id=row.get("external_job_id"),
        source_url=row.get("source_url"),
        fetched_at=row.get("fetched_at"),
        ingestion_run_id=row.get("ingestion_run_id"),
        search_profile_id=row.get("search_profile_id"),
        initial_profile_name=row.get("initial_profile_name", "<missing_profile>"),
        initial_search_term_snapshot=row.get(
            "initial_search_term_snapshot",
            "<multi-term_or_missing>",
        ),
        raw_data_bytes=int(row.get("raw_data_bytes") or 0),
    )


def build_removal_candidates(
    rows: Sequence[dict[str, Any]],
) -> list[HotStoreRemovalCandidate]:
    candidates = [
        candidate
        for row in rows
        if (candidate := candidate_from_row(row)) is not None
    ]
    candidates.sort(key=lambda candidate: (candidate.source_name, candidate.raw_job_id))
    return candidates


def build_review_summary(
    candidates: Sequence[HotStoreRemovalCandidate],
) -> dict[str, Any]:
    review_status_counts = Counter(candidate.review_status for candidate in candidates)
    source_counts = Counter(candidate.source_name for candidate in candidates)
    burden_counts = Counter(candidate.burden_category for candidate in candidates)

    return {
        "candidate_count": len(candidates),
        "eligible_for_removal_count": sum(
            int(candidate.eligible_for_future_removal)
            for candidate in candidates
        ),
        "blocked_or_non_actionable_count": sum(
            int(not candidate.eligible_for_future_removal)
            for candidate in candidates
        ),
        "silver_backed_rows": sum(
            int(candidate.has_silver_job_now)
            for candidate in candidates
        ),
        "source_counts": dict(source_counts),
        "burden_category_counts": dict(burden_counts),
        "review_status_counts": dict(review_status_counts),
        "raw_data_bytes": sum(candidate.raw_data_bytes for candidate in candidates),
        "raw_data_size": format_bytes(sum(candidate.raw_data_bytes for candidate in candidates)),
    }


def make_json_safe(value: Any) -> Any:
    """Convert dataclass snapshots to JSON-safe values before storing JSONB."""
    return json.loads(json.dumps(value, default=json_default))


def candidate_to_db_row(
    batch_id: int,
    candidate: HotStoreRemovalCandidate,
) -> dict[str, Any]:
    snapshot = make_json_safe(asdict(candidate))
    return {
        "batch_id": batch_id,
        "raw_job_id": candidate.raw_job_id,
        "source_name": candidate.source_name,
        "external_job_id": candidate.external_job_id,
        "source_url": candidate.source_url,
        "fetched_at": candidate.fetched_at,
        "ingestion_run_id": candidate.ingestion_run_id,
        "search_profile_id": candidate.search_profile_id,
        "initial_profile_name": candidate.initial_profile_name,
        "initial_search_term_snapshot": candidate.initial_search_term_snapshot,
        "burden_category": candidate.burden_category,
        "retention_track": candidate.retention_track,
        "exists_in_hot_store": candidate.exists_in_hot_store,
        "has_silver_job_now": candidate.has_silver_job_now,
        "still_archive_candidate": candidate.still_archive_candidate,
        "eligible_for_future_removal": candidate.eligible_for_future_removal,
        "review_status": candidate.review_status,
        "raw_data_bytes": candidate.raw_data_bytes,
        "item_snapshot": Jsonb(snapshot),
    }


def persist_review_batch(
    connection: psycopg.Connection,
    candidates: Sequence[HotStoreRemovalCandidate],
    review_reason: str,
) -> int:
    summary = build_review_summary(candidates)
    metadata = {
        "mode": "db_backed_historical_burden_hot_store_removal_review",
        "database_cleanup_action": "none",
        "generated_by": "scripts.prepare_historical_burden_hot_store_removal",
        "interpretation_boundary": [
            "This batch is proposed review state only.",
            "It does not approve hot-store removal.",
            "Execution must read approved DB state, not local files.",
        ],
    }

    with connection.cursor() as cursor:
        cursor.execute(
            INSERT_REVIEW_BATCH_SQL,
            {
                "review_reason": review_reason,
                "retention_track": ARCHIVE_RETENTION_TRACK,
                "candidate_count": summary["candidate_count"],
                "eligible_for_removal_count": summary["eligible_for_removal_count"],
                "blocked_or_non_actionable_count": summary["blocked_or_non_actionable_count"],
                "silver_backed_rows": summary["silver_backed_rows"],
                "source_counts": Jsonb(summary["source_counts"]),
                "burden_category_counts": Jsonb(summary["burden_category_counts"]),
                "review_status_counts": Jsonb(summary["review_status_counts"]),
                "raw_data_bytes": summary["raw_data_bytes"],
                "metadata": Jsonb(metadata),
            },
        )
        batch_id = int(cursor.fetchone()[0])

        for candidate in candidates:
            cursor.execute(INSERT_REVIEW_ITEM_SQL, candidate_to_db_row(batch_id, candidate))

    return batch_id


def build_manifest(
    batch_id: int,
    candidates: Sequence[HotStoreRemovalCandidate],
    review_reason: str,
) -> dict[str, Any]:
    summary = build_review_summary(candidates)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "db_backed_hot_store_removal_review",
        "database_cleanup_action": "none",
        "batch_id": batch_id,
        "review_reason": review_reason,
        "retention_track": ARCHIVE_RETENTION_TRACK,
        **summary,
        "output_boundary": [
            "This manifest is a human-readable review artifact.",
            "It is not a pipeline input.",
            "It is not an activation gate input.",
            "It is not a destructive-operation input.",
            "Future execution must read approved DB state by batch_id.",
        ],
    }


def candidate_to_review_row(candidate: HotStoreRemovalCandidate) -> dict[str, Any]:
    return {
        "raw_job_id": candidate.raw_job_id,
        "source_name": candidate.source_name,
        "burden_category": candidate.burden_category,
        "retention_track": candidate.retention_track,
        "eligible_for_future_removal": candidate.eligible_for_future_removal,
        "review_status": candidate.review_status,
        "external_job_id": candidate.external_job_id,
        "source_url": candidate.source_url,
        "fetched_at": candidate.fetched_at,
        "initial_profile_name": candidate.initial_profile_name,
        "initial_search_term_snapshot": candidate.initial_search_term_snapshot,
        "raw_data_bytes": candidate.raw_data_bytes,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
        encoding="utf-8",
    )


def write_markdown_review(
    path: Path,
    batch_id: int,
    candidates: Sequence[HotStoreRemovalCandidate],
    review_reason: str,
) -> None:
    summary = build_review_summary(candidates)

    lines = [
        "# Historical Burden Hot-Store Removal Review",
        "",
        "## Boundary",
        "",
        "This review is DB-backed. It does not delete, update or archive database rows.",
        "",
        "Generated files are review artifacts only. They must not be used as pipeline inputs, activation gates, destructive-operation inputs, migration inputs or cloud dependencies.",
        "",
        "## Batch",
        "",
        f"- batch_id: `{batch_id}`",
        f"- review_reason: {review_reason}",
        f"- retention_track: `{ARCHIVE_RETENTION_TRACK}`",
        "- status at creation: `proposed`",
        "",
        "## Counts",
        "",
        f"- candidate_count: {summary['candidate_count']}",
        f"- eligible_for_removal_count: {summary['eligible_for_removal_count']}",
        f"- blocked_or_non_actionable_count: {summary['blocked_or_non_actionable_count']}",
        f"- silver_backed_rows: {summary['silver_backed_rows']}",
        f"- raw_data_size: {summary['raw_data_size']}",
        "",
        "## Review Status Counts",
        "",
    ]

    for status, count in sorted(summary["review_status_counts"].items()):
        lines.append(f"- {status}: {count}")

    lines += ["", "## Source Counts", ""]
    for source_name, count in sorted(summary["source_counts"].items()):
        lines.append(f"- {source_name}: {count}")

    lines += [
        "",
        "## Candidate Samples",
        "",
    ]

    for candidate in candidates[:25]:
        lines.append(f"- `{candidate.review_status}` — raw_jobs {candidate.raw_job_id} — {candidate.source_name}")
        lines.append(f"  - burden_category: {candidate.burden_category}")
        lines.append(f"  - source_url: {candidate.source_url or '-'}")
        lines.append(f"  - profile/search term: {candidate.initial_profile_name} / {candidate.initial_search_term_snapshot}")

    lines += [
        "",
        "## Next Step Boundary",
        "",
        "A later execution step must require an explicitly approved DB batch.",
        "It must not read this Markdown file or the JSON manifest as execution input.",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_review_artifacts(
    export_dir: Path,
    batch_id: int,
    candidates: Sequence[HotStoreRemovalCandidate],
    review_reason: str,
) -> tuple[Path, Path]:
    manifest_path = export_dir / REVIEW_MANIFEST_FILENAME
    markdown_path = export_dir / REVIEW_MARKDOWN_FILENAME

    write_manifest(
        manifest_path,
        build_manifest(
            batch_id=batch_id,
            candidates=candidates,
            review_reason=review_reason,
        ),
    )
    write_markdown_review(
        markdown_path,
        batch_id=batch_id,
        candidates=candidates,
        review_reason=review_reason,
    )

    return markdown_path, manifest_path


def print_summary(batch_id: int, candidates: Sequence[HotStoreRemovalCandidate]) -> None:
    summary = build_review_summary(candidates)

    print()
    print("Historical Burden Hot-Store Removal Review")
    print("Mode: DB-backed review batch")
    print("Database cleanup action: none")
    print(f"Batch ID: {batch_id}")
    print(f"Retention track: {ARCHIVE_RETENTION_TRACK}")
    print(f"Candidate rows: {summary['candidate_count']}")
    print(f"Eligible for future removal: {summary['eligible_for_removal_count']}")
    print(f"Blocked or non-actionable: {summary['blocked_or_non_actionable_count']}")
    print()
    print("Rows by source:")
    for source_name, count in sorted(summary["source_counts"].items()):
        print(f"- {source_name}: {count}")
    print()
    print("Rows by review status:")
    for review_status, count in sorted(summary["review_status_counts"].items()):
        print(f"- {review_status}: {count}")


def run_review(export_dir: Path, review_reason: str) -> None:
    with psycopg.connect(**get_database_config()) as connection:
        rows = load_current_hot_store_candidates(connection)
        candidates = build_removal_candidates(rows)
        batch_id = persist_review_batch(
            connection=connection,
            candidates=candidates,
            review_reason=review_reason,
        )

    markdown_path, manifest_path = write_review_artifacts(
        export_dir=export_dir,
        batch_id=batch_id,
        candidates=candidates,
        review_reason=review_reason,
    )

    print_summary(batch_id, candidates)
    print()
    print("Exported review artifacts:")
    print(f"- {markdown_path}")
    print(f"- {manifest_path}")
    print()
    print("Interpretation boundary:")
    print("- This script does not remove rows from the database.")
    print("- This script creates proposed DB review state.")
    print("- Generated files are review artifacts only.")
    print("- A later execution step must read approved DB state by batch_id.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Local output directory for human-readable review artifacts only.",
    )
    parser.add_argument(
        "--review-reason",
        default=REVIEW_REASON,
        help="Reason stored on the DB-backed review batch.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_review(export_dir=args.export_dir, review_reason=args.review_reason)


if __name__ == "__main__":
    main()
