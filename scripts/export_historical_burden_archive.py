"""Export historical burden candidates for archival review.

This script supports the H2 cleanup/retention phase after the dry-run review
workflow has classified historical burden. It creates local archive artifacts for
rows that are candidates for archival before hot-store removal.

It never deletes, updates, archives or reclassifies database rows. The only side
effect is writing local files to the chosen export directory.

Usage:
    python -m scripts.export_historical_burden_archive
    python -m scripts.export_historical_burden_archive --export-dir exports/historical_burden_archive
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.review_historical_burden_candidates import (
    classify_review_action,
    classify_retention_track,
    format_bytes,
)
from src.config import get_database_config


ARCHIVE_RETENTION_TRACK = "archive_before_hot_store_removal_candidate"

ARCHIVE_CANDIDATES_SQL = """
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
    rj.raw_data,
    sj.id IS NOT NULL AS has_silver_job,
    COALESCE(spd.decision, '<none>') AS processing_decision,
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
LEFT JOIN silver_processing_decisions spd
    ON spd.raw_job_id = rj.id
ORDER BY
    rj.fetched_at,
    rj.id;
"""


@dataclass(frozen=True)
class HistoricalBurdenArchiveRecord:
    raw_job_id: int
    source_name: str
    external_job_id: str | None
    source_url: str | None
    fetched_at: Any
    ingestion_run_id: int | None
    search_profile_id: int | None
    initial_profile_name: str
    initial_search_term_snapshot: str
    burden_category: str
    retention_track: str
    review_action: str
    has_silver_job: bool
    processing_decision: str
    raw_data_bytes: int
    raw_data: Any


def json_default(value: Any) -> str | int | float:
    """Serialize DB values that are not JSON-native."""

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def record_from_row(row: dict[str, Any]) -> HistoricalBurdenArchiveRecord:
    burden_category = row["burden_category"]
    has_silver_job = bool(row["has_silver_job"])
    retention_track = classify_retention_track(
        burden_category=burden_category,
        has_silver_job=has_silver_job,
    )

    return HistoricalBurdenArchiveRecord(
        raw_job_id=row["raw_job_id"],
        source_name=row["source_name"],
        external_job_id=row["external_job_id"],
        source_url=row["source_url"],
        fetched_at=row["fetched_at"],
        ingestion_run_id=row["ingestion_run_id"],
        search_profile_id=row["search_profile_id"],
        initial_profile_name=row["initial_profile_name"],
        initial_search_term_snapshot=row["initial_search_term_snapshot"],
        burden_category=burden_category,
        retention_track=retention_track,
        review_action=classify_review_action(retention_track),
        has_silver_job=has_silver_job,
        processing_decision=row["processing_decision"],
        raw_data_bytes=row["raw_data_bytes"],
        raw_data=row["raw_data"],
    )


def load_archive_candidates(
    connection: psycopg.Connection,
) -> list[HistoricalBurdenArchiveRecord]:
    """Load only rows that are archive-before-hot-store-removal candidates."""

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(ARCHIVE_CANDIDATES_SQL)
        records = [record_from_row(dict(row)) for row in cursor.fetchall()]

    return [
        record
        for record in records
        if record.retention_track == ARCHIVE_RETENTION_TRACK
    ]


def record_to_archive_json(record: HistoricalBurdenArchiveRecord) -> dict[str, Any]:
    """Return a full archive row, including raw_data evidence."""

    return {
        "raw_job_id": record.raw_job_id,
        "source_name": record.source_name,
        "external_job_id": record.external_job_id,
        "source_url": record.source_url,
        "fetched_at": record.fetched_at,
        "ingestion_run_id": record.ingestion_run_id,
        "search_profile_id": record.search_profile_id,
        "initial_profile_name": record.initial_profile_name,
        "initial_search_term_snapshot": record.initial_search_term_snapshot,
        "burden_category": record.burden_category,
        "retention_track": record.retention_track,
        "review_action": record.review_action,
        "has_silver_job": record.has_silver_job,
        "processing_decision": record.processing_decision,
        "raw_data_bytes": record.raw_data_bytes,
        "raw_data": record.raw_data,
    }


def summarize_records(
    records: Iterable[HistoricalBurdenArchiveRecord],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for record in records:
        key = (record.burden_category, record.source_name)

        if key not in grouped:
            grouped[key] = {
                "burden_category": record.burden_category,
                "source_name": record.source_name,
                "retention_track": record.retention_track,
                "raw_jobs": 0,
                "raw_data_bytes": 0,
                "silver_backed_rows": 0,
                "included_decisions": 0,
                "skipped_decisions": 0,
                "first_fetched_at": record.fetched_at,
                "latest_fetched_at": record.fetched_at,
            }

        summary = grouped[key]
        summary["raw_jobs"] += 1
        summary["raw_data_bytes"] += record.raw_data_bytes
        summary["silver_backed_rows"] += int(record.has_silver_job)
        summary["included_decisions"] += int(record.processing_decision == "included")
        summary["skipped_decisions"] += int(record.processing_decision == "skipped")
        summary["first_fetched_at"] = min(summary["first_fetched_at"], record.fetched_at)
        summary["latest_fetched_at"] = max(summary["latest_fetched_at"], record.fetched_at)

    rows = list(grouped.values())
    rows.sort(key=lambda row: (-row["raw_jobs"], row["burden_category"], row["source_name"]))

    for row in rows:
        row["raw_data_size"] = format_bytes(row["raw_data_bytes"])

    return rows


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True, default=json_default))
            file.write("\n")


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_manifest(
    records: Sequence[HistoricalBurdenArchiveRecord],
    jsonl_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    source_counts = Counter(record.source_name for record in records)
    burden_counts = Counter(record.burden_category for record in records)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "local_export_only",
        "database_cleanup_action": "none",
        "retention_track": ARCHIVE_RETENTION_TRACK,
        "policy": (
            "historical burden is preserved as an archive artifact before any "
            "future hot-store removal review"
        ),
        "record_count": len(records),
        "raw_data_bytes": sum(record.raw_data_bytes for record in records),
        "raw_data_size": format_bytes(sum(record.raw_data_bytes for record in records)),
        "silver_backed_rows": sum(int(record.has_silver_job) for record in records),
        "source_counts": dict(source_counts),
        "burden_category_counts": dict(burden_counts),
        "exports": {
            "records_jsonl": {
                "path": str(jsonl_path),
                "size_bytes": jsonl_path.stat().st_size,
                "sha256": compute_sha256(jsonl_path),
            },
            "summary_csv": {
                "path": str(summary_path),
                "size_bytes": summary_path.stat().st_size,
                "sha256": compute_sha256(summary_path),
            },
        },
        "interpretation_boundary": [
            "This manifest proves local export, not deletion or archival in a remote store.",
            "Rows remain in the database until a separate reviewed removal workflow exists.",
            "Silver-backed rows must not be removed from the hot store by this policy.",
        ],
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
        encoding="utf-8",
    )


def export_archive(records: Sequence[HistoricalBurdenArchiveRecord], export_dir: Path) -> tuple[Path, Path, Path]:
    records_path = export_dir / "historical_burden_archive_records.jsonl"
    summary_path = export_dir / "historical_burden_archive_summary.csv"
    manifest_path = export_dir / "historical_burden_archive_manifest.json"

    archive_rows = [record_to_archive_json(record) for record in records]
    summary_rows = summarize_records(records)

    write_jsonl(records_path, archive_rows)
    write_csv(summary_path, summary_rows)
    write_manifest(
        manifest_path,
        build_manifest(
            records=records,
            jsonl_path=records_path,
            summary_path=summary_path,
        ),
    )

    return records_path, summary_path, manifest_path


def print_summary(records: Sequence[HistoricalBurdenArchiveRecord]) -> None:
    source_counts = Counter(record.source_name for record in records)
    burden_counts = Counter(record.burden_category for record in records)
    total_bytes = sum(record.raw_data_bytes for record in records)

    print()
    print("Historical Burden Archive Export")
    print("Mode: local export only")
    print("Database cleanup action: none")
    print(f"Retention track: {ARCHIVE_RETENTION_TRACK}")
    print(f"Archive candidate rows: {len(records)}")
    print(f"Archive candidate raw_data size: {format_bytes(total_bytes)}")
    print()
    print("Rows by source:")
    for source_name, count in source_counts.most_common():
        print(f"- {source_name}: {count}")
    print()
    print("Rows by burden category:")
    for burden_category, count in burden_counts.most_common():
        print(f"- {burden_category}: {count}")


def run_export(export_dir: Path) -> None:
    config = get_database_config()

    with psycopg.connect(**config) as connection:
        records = load_archive_candidates(connection)

    print_summary(records)
    records_path, summary_path, manifest_path = export_archive(records, export_dir)

    print()
    print("Exported archive files:")
    print(f"- {records_path}")
    print(f"- {summary_path}")
    print(f"- {manifest_path}")
    print()
    print("Interpretation boundary:")
    print("- This script does not remove rows from the database.")
    print("- This export is a prerequisite for future reviewed hot-store removal.")
    print("- Silver-backed rows are excluded from this archive candidate set.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/historical_burden_archive"),
        help="Local output directory for archive artifacts. The database remains read-only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_export(export_dir=args.export_dir)


if __name__ == "__main__":
    main()
