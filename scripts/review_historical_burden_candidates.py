"""Review historical burden candidates without modifying database rows.

This script supports the H2 cleanup/retention phase. It classifies persisted
Bronze records into conservative review categories and optionally exports CSV
review files. It never deletes, updates, archives or reclassifies database rows.

Usage:
    python -m scripts.review_historical_burden_candidates
    python -m scripts.review_historical_burden_candidates --detail-limit 50
    python -m scripts.review_historical_burden_candidates --export-dir exports/historical_burden_review
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


BASE_CANDIDATES_SQL = """
WITH observation_counts AS (
    SELECT
        raw_job_id,
        COUNT(*) AS observation_count
    FROM job_observations
    GROUP BY raw_job_id
)
SELECT
    rj.id AS raw_job_id,
    rj.source_name,
    COALESCE(sp.profile_name, '<missing_profile>') AS initial_profile_name,
    COALESCE(ir.search_term, '<multi-term_or_missing>') AS initial_search_term_snapshot,
    rj.external_job_id,
    rj.source_url,
    rj.fetched_at,
    pg_column_size(rj.raw_data) AS raw_data_bytes,
    rj.raw_data ? 'matching' AS has_matching_metadata,
    COALESCE(oc.observation_count, 0) AS observation_count,
    sj.id IS NOT NULL AS has_silver_job,
    COALESCE(spd.decision, '<none>') AS processing_decision,
    COALESCE(
        rj.raw_data #>> '{result_card,title}',
        rj.raw_data #>> '{job,title}',
        rj.raw_data #>> '{job,titel}',
        rj.raw_data ->> 'title',
        '<missing>'
    ) AS title_preview,
    COALESCE(
        rj.raw_data #>> '{result_card,company_name}',
        rj.raw_data #>> '{job,company_name}',
        rj.raw_data #>> '{job,arbeitgeber}',
        rj.raw_data ->> 'company_name',
        '<missing>'
    ) AS company_preview,
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
LEFT JOIN observation_counts oc
    ON oc.raw_job_id = rj.id
LEFT JOIN silver_jobs sj
    ON sj.raw_job_id = rj.id
LEFT JOIN silver_processing_decisions spd
    ON spd.raw_job_id = rj.id
ORDER BY
    rj.fetched_at,
    rj.id;
"""


@dataclass(frozen=True)
class HistoricalBurdenCandidate:
    raw_job_id: int
    burden_category: str
    retention_track: str
    review_action: str
    source_name: str
    initial_profile_name: str
    initial_search_term_snapshot: str
    fetched_at: Any
    external_job_id: str | None
    has_silver_job: bool
    processing_decision: str
    has_matching_metadata: bool
    observation_count: int
    raw_data_bytes: int
    title_preview: str
    company_preview: str
    source_url: str


def classify_retention_track(burden_category: str, has_silver_job: bool) -> str:
    """Return the conservative retention track for a candidate.

    Silver evidence always wins over burden category because deleting or moving
    a raw row that backs a Silver row would destroy canonical evidence.
    """

    if has_silver_job:
        return "retain_as_silver_evidence"

    if burden_category in {"test_data", "possible_test_data"}:
        return "delete_candidate_after_review"

    if burden_category == "missing_lineage":
        return "review_lineage_before_action"

    if burden_category in {
        "greenhouse_legacy_wildcard",
        "greenhouse_without_current_matching_metadata",
        "commercial_aggregator_history",
    }:
        return "archive_before_hot_store_removal_candidate"

    if burden_category == "personio_without_current_matching_metadata":
        return "review_matching_metadata_before_action"

    return "retain_operational_history"


def classify_review_action(retention_track: str) -> str:
    """Translate retention tracks into safe next actions."""

    if retention_track == "retain_as_silver_evidence":
        return "keep; raw row supports Silver evidence"

    if retention_track == "delete_candidate_after_review":
        return "review manually; delete only with explicit approved cleanup command"

    if retention_track == "review_lineage_before_action":
        return "inspect lineage; decide retain, archive or delete later"

    if retention_track == "archive_before_hot_store_removal_candidate":
        return "candidate for archive or trend exclusion; do not delete by default"

    if retention_track == "review_matching_metadata_before_action":
        return "review local matching semantics before retention decision"

    return "keep as ordinary operational history"


def shorten_text(value: Any, max_length: int = 90) -> str:
    if value is None:
        return ""

    normalized = " ".join(str(value).split())

    if len(normalized) <= max_length:
        return normalized

    return normalized[: max_length - 3] + "..."


def format_bytes(size_bytes: int) -> str:
    value = float(size_bytes)
    units = ["bytes", "kB", "MB", "GB"]

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "bytes":
                return f"{int(value)} bytes"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{size_bytes} bytes"


def candidate_from_row(row: dict[str, Any]) -> HistoricalBurdenCandidate:
    burden_category = row["burden_category"]
    has_silver_job = bool(row["has_silver_job"])
    retention_track = classify_retention_track(
        burden_category=burden_category,
        has_silver_job=has_silver_job,
    )

    return HistoricalBurdenCandidate(
        raw_job_id=row["raw_job_id"],
        burden_category=burden_category,
        retention_track=retention_track,
        review_action=classify_review_action(retention_track),
        source_name=row["source_name"],
        initial_profile_name=row["initial_profile_name"],
        initial_search_term_snapshot=row["initial_search_term_snapshot"],
        fetched_at=row["fetched_at"],
        external_job_id=row["external_job_id"],
        has_silver_job=has_silver_job,
        processing_decision=row["processing_decision"],
        has_matching_metadata=bool(row["has_matching_metadata"]),
        observation_count=row["observation_count"],
        raw_data_bytes=row["raw_data_bytes"],
        title_preview=shorten_text(row["title_preview"]),
        company_preview=shorten_text(row["company_preview"]),
        source_url=row["source_url"],
    )


def load_candidates(connection: psycopg.Connection) -> list[HistoricalBurdenCandidate]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(BASE_CANDIDATES_SQL)
        return [candidate_from_row(dict(row)) for row in cursor.fetchall()]


def summarize_candidates(
    candidates: Iterable[HistoricalBurdenCandidate],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for candidate in candidates:
        key = (
            candidate.burden_category,
            candidate.retention_track,
            candidate.review_action,
            candidate.source_name,
        )

        if key not in grouped:
            grouped[key] = {
                "burden_category": candidate.burden_category,
                "retention_track": candidate.retention_track,
                "review_action": candidate.review_action,
                "source_name": candidate.source_name,
                "raw_jobs": 0,
                "raw_data_bytes": 0,
                "silver_backed_rows": 0,
                "included_decisions": 0,
                "skipped_decisions": 0,
                "observations": 0,
                "first_fetched_at": candidate.fetched_at,
                "latest_fetched_at": candidate.fetched_at,
            }

        summary = grouped[key]
        summary["raw_jobs"] += 1
        summary["raw_data_bytes"] += candidate.raw_data_bytes
        summary["silver_backed_rows"] += int(candidate.has_silver_job)
        summary["included_decisions"] += int(candidate.processing_decision == "included")
        summary["skipped_decisions"] += int(candidate.processing_decision == "skipped")
        summary["observations"] += candidate.observation_count
        summary["first_fetched_at"] = min(summary["first_fetched_at"], candidate.fetched_at)
        summary["latest_fetched_at"] = max(summary["latest_fetched_at"], candidate.fetched_at)

    rows = list(grouped.values())
    rows.sort(
        key=lambda row: (
            -row["raw_jobs"],
            row["burden_category"],
            row["source_name"],
        )
    )

    for row in rows:
        row["raw_data_size"] = format_bytes(row["raw_data_bytes"])

    return rows


def candidate_to_row(candidate: HistoricalBurdenCandidate) -> dict[str, Any]:
    return {
        "raw_job_id": candidate.raw_job_id,
        "burden_category": candidate.burden_category,
        "retention_track": candidate.retention_track,
        "review_action": candidate.review_action,
        "source_name": candidate.source_name,
        "initial_profile_name": candidate.initial_profile_name,
        "initial_search_term_snapshot": candidate.initial_search_term_snapshot,
        "fetched_at": candidate.fetched_at,
        "external_job_id": candidate.external_job_id,
        "has_silver_job": candidate.has_silver_job,
        "processing_decision": candidate.processing_decision,
        "has_matching_metadata": candidate.has_matching_metadata,
        "observation_count": candidate.observation_count,
        "raw_data_bytes": candidate.raw_data_bytes,
        "title_preview": candidate.title_preview,
        "company_preview": candidate.company_preview,
        "source_url": candidate.source_url,
    }


def rows_to_table(rows: Sequence[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    if not rows:
        return [], []

    headers = list(rows[0].keys())
    return headers, [[row[header] for header in headers] for row in rows]


def print_table(headers: list[str], rows: Sequence[Sequence[Any]]) -> None:
    if not rows:
        print("No rows.")
        return

    widths = [
        max(len(header), *(len(str(row[index])) for row in rows))
        for index, header in enumerate(headers)
    ]

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in rows:
        print(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))


def print_section(title: str, rows: Sequence[dict[str, Any]]) -> None:
    print()
    print(f"=== {title} ===")
    print()

    headers, table_rows = rows_to_table(rows)
    if not headers:
        print("No rows.")
        return

    print_table(headers, table_rows)


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("")
        return

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_review_files(
    export_dir: Path,
    summary_rows: Sequence[dict[str, Any]],
    detail_rows: Sequence[dict[str, Any]],
) -> tuple[Path, Path]:
    summary_path = export_dir / "historical_burden_review_summary.csv"
    detail_path = export_dir / "historical_burden_review_candidates.csv"

    write_csv(summary_path, summary_rows)
    write_csv(detail_path, detail_rows)

    return summary_path, detail_path


def get_detail_candidates(
    candidates: Sequence[HistoricalBurdenCandidate],
    include_ordinary: bool,
    detail_limit: int,
) -> list[HistoricalBurdenCandidate]:
    include_ordinary_effective = include_ordinary or detail_limit <= 0

    filtered = [
        candidate
        for candidate in candidates
        if include_ordinary_effective
        or candidate.retention_track != "retain_operational_history"
    ]

    filtered.sort(
        key=lambda candidate: (
            candidate.retention_track == "retain_operational_history",
            candidate.retention_track,
            candidate.burden_category,
            candidate.source_name,
            candidate.fetched_at,
            candidate.raw_job_id,
        )
    )

    if detail_limit <= 0:
        return filtered

    return filtered[:detail_limit]


def run_review(
    detail_limit: int,
    include_ordinary: bool,
    export_dir: Path | None,
) -> None:
    config = get_database_config()

    with psycopg.connect(**config) as connection:
        candidates = load_candidates(connection)

    summary_rows = summarize_candidates(candidates)
    detail_candidates = get_detail_candidates(
        candidates=candidates,
        include_ordinary=include_ordinary,
        detail_limit=detail_limit,
    )
    detail_rows = [candidate_to_row(candidate) for candidate in detail_candidates]

    print()
    print("Historical Burden Retention Review")
    print("Mode: dry-run")
    print("Database cleanup action: none")
    print("Local export action:", "enabled" if export_dir else "disabled")

    print_section("Retention Summary by Category/Track/Source", summary_rows)
    print_section("Review Candidate Details", detail_rows)

    if export_dir:
        summary_path, detail_path = export_review_files(
            export_dir=export_dir,
            summary_rows=summary_rows,
            detail_rows=detail_rows,
        )
        print()
        print("Exported review files:")
        print(f"- {summary_path}")
        print(f"- {detail_path}")

    print()
    print("Interpretation boundary:")
    print("- This script is a dry-run review aid, not a cleanup command.")
    print("- Silver-backed raw rows are always retained as evidence.")
    print("- Archive/delete actions require a separate reviewed implementation.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=50,
        help="Maximum number of detailed candidate rows to print/export. Use 0 for all rows, including ordinary operational history.",
    )
    parser.add_argument(
        "--include-ordinary",
        action="store_true",
        help="Include ordinary operational history rows in the detail output.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="Optional directory for CSV review exports. The database remains read-only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_review(
        detail_limit=args.detail_limit,
        include_ordinary=args.include_ordinary,
        export_dir=args.export_dir,
    )


if __name__ == "__main__":
    main()
