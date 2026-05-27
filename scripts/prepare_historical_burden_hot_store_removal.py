"""Prepare a dry-run review for historical burden hot-store removal.

This script is the safety step after the local archive export workflow. It reads
an existing archive manifest and JSONL archive, validates the artifact, compares
archived raw_job_id values against the current hot-store database state, and
writes a review list for rows that may be eligible for future removal.

It never deletes, updates or archives database rows. The only side effect is
writing local review files to the chosen export directory.

Usage:
    python -m scripts.prepare_historical_burden_hot_store_removal
    python -m scripts.prepare_historical_burden_hot_store_removal \
      --archive-dir exports/historical_burden_archive \
      --export-dir exports/historical_burden_hot_store_removal_review
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Sequence
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
from scripts.review_historical_burden_candidates import (
    classify_retention_track,
    format_bytes,
)
from src.config import get_database_config


DEFAULT_ARCHIVE_DIR = Path("exports/historical_burden_archive")
DEFAULT_EXPORT_DIR = Path("exports/historical_burden_hot_store_removal_review")

ARCHIVE_RECORDS_FILENAME = "historical_burden_archive_records.jsonl"
ARCHIVE_MANIFEST_FILENAME = "historical_burden_archive_manifest.json"

REMOVAL_CANDIDATES_FILENAME = "historical_burden_hot_store_removal_candidates.csv"
REMOVAL_MANIFEST_FILENAME = "historical_burden_hot_store_removal_manifest.json"

CURRENT_HOT_STORE_STATE_SQL = """
SELECT
    rj.id AS raw_job_id,
    rj.source_name,
    rj.ingestion_run_id,
    rj.search_profile_id,
    COALESCE(sp.profile_name, '<missing_profile>') AS initial_profile_name,
    COALESCE(ir.search_term, '<multi-term_or_missing>') AS initial_search_term_snapshot,
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
    END AS current_burden_category
FROM raw_jobs rj
LEFT JOIN ingestion_runs ir
    ON ir.id = rj.ingestion_run_id
LEFT JOIN search_profiles sp
    ON sp.id = rj.search_profile_id
LEFT JOIN silver_jobs sj
    ON sj.raw_job_id = rj.id
WHERE rj.id = ANY(%s)
ORDER BY rj.id;
"""


@dataclass(frozen=True)
class ArchiveRecordReference:
    raw_job_id: int
    source_name: str
    burden_category: str
    retention_track: str
    has_silver_job: bool
    external_job_id: str | None
    source_url: str | None
    fetched_at: str | None
    initial_profile_name: str
    initial_search_term_snapshot: str
    raw_data_bytes: int


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


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def resolve_manifest_path(manifest_path: Path, path_from_manifest: str) -> Path:
    candidate = Path(path_from_manifest)

    if candidate.exists():
        return candidate

    relative_to_manifest = manifest_path.parent / candidate.name
    if relative_to_manifest.exists():
        return relative_to_manifest

    return candidate


def read_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_archive_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = read_manifest(manifest_path)

    if manifest.get("database_cleanup_action") != "none":
        raise ValueError("Archive manifest must prove database_cleanup_action=none")

    if manifest.get("retention_track") != ARCHIVE_RETENTION_TRACK:
        raise ValueError(
            "Archive manifest retention_track must be "
            f"{ARCHIVE_RETENTION_TRACK!r}"
        )

    if manifest.get("silver_backed_rows") != 0:
        raise ValueError("Archive manifest must not contain Silver-backed rows")

    records_export = manifest.get("exports", {}).get("records_jsonl", {})
    records_path_value = records_export.get("path")
    expected_sha256 = records_export.get("sha256")

    if not records_path_value or not expected_sha256:
        raise ValueError("Archive manifest must include records_jsonl path and sha256")

    records_path = resolve_manifest_path(manifest_path, records_path_value)
    if not records_path.exists():
        raise FileNotFoundError(f"Archive records file not found: {records_path}")

    actual_sha256 = compute_sha256(records_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "Archive records checksum mismatch: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

    return manifest


def load_archive_records(records_path: Path) -> list[ArchiveRecordReference]:
    records: list[ArchiveRecordReference] = []

    with records_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            raw = json.loads(line)
            retention_track = raw.get("retention_track")
            has_silver_job = bool(raw.get("has_silver_job"))

            if retention_track != ARCHIVE_RETENTION_TRACK:
                raise ValueError(
                    f"Line {line_number} has unexpected retention_track "
                    f"{retention_track!r}"
                )

            if has_silver_job:
                raise ValueError(
                    f"Line {line_number} is Silver-backed and must not be a "
                    "hot-store removal candidate"
                )

            records.append(
                ArchiveRecordReference(
                    raw_job_id=int(raw["raw_job_id"]),
                    source_name=raw["source_name"],
                    burden_category=raw["burden_category"],
                    retention_track=retention_track,
                    has_silver_job=has_silver_job,
                    external_job_id=raw.get("external_job_id"),
                    source_url=raw.get("source_url"),
                    fetched_at=raw.get("fetched_at"),
                    initial_profile_name=raw.get("initial_profile_name", "<missing_profile>"),
                    initial_search_term_snapshot=raw.get(
                        "initial_search_term_snapshot",
                        "<multi-term_or_missing>",
                    ),
                    raw_data_bytes=int(raw.get("raw_data_bytes") or 0),
                )
            )

    return records


def load_current_hot_store_state(
    connection: psycopg.Connection,
    raw_job_ids: Sequence[int],
) -> dict[int, CurrentHotStoreState]:
    if not raw_job_ids:
        return {}

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(CURRENT_HOT_STORE_STATE_SQL, (list(raw_job_ids),))
        rows = [dict(row) for row in cursor.fetchall()]

    states: dict[int, CurrentHotStoreState] = {}

    for row in rows:
        current_burden_category = row["current_burden_category"]
        has_silver_job = bool(row["has_silver_job"])
        current_retention_track = classify_retention_track(
            burden_category=current_burden_category,
            has_silver_job=has_silver_job,
        )

        states[row["raw_job_id"]] = CurrentHotStoreState(
            raw_job_id=row["raw_job_id"],
            source_name=row["source_name"],
            initial_profile_name=row["initial_profile_name"],
            initial_search_term_snapshot=row["initial_search_term_snapshot"],
            current_burden_category=current_burden_category,
            current_retention_track=current_retention_track,
            has_silver_job=has_silver_job,
        )

    return states


def classify_review_status(
    archive_record: ArchiveRecordReference,
    current_state: CurrentHotStoreState | None,
) -> tuple[bool, bool, bool, str]:
    if current_state is None:
        return False, False, False, "already_absent_from_hot_store"

    has_silver_job_now = current_state.has_silver_job
    still_archive_candidate = current_state.current_retention_track == ARCHIVE_RETENTION_TRACK

    if has_silver_job_now:
        return True, has_silver_job_now, still_archive_candidate, "blocked_silver_evidence_now_exists"

    if not still_archive_candidate:
        return True, has_silver_job_now, still_archive_candidate, "blocked_current_classification_changed"

    if current_state.source_name != archive_record.source_name:
        return True, has_silver_job_now, still_archive_candidate, "blocked_source_mismatch"

    return True, has_silver_job_now, still_archive_candidate, "eligible_after_archive_review"


def build_removal_candidates(
    archive_records: Sequence[ArchiveRecordReference],
    current_states: dict[int, CurrentHotStoreState],
) -> list[HotStoreRemovalCandidate]:
    candidates: list[HotStoreRemovalCandidate] = []

    for archive_record in archive_records:
        current_state = current_states.get(archive_record.raw_job_id)
        (
            exists_in_hot_store,
            has_silver_job_now,
            still_archive_candidate,
            review_status,
        ) = classify_review_status(archive_record, current_state)

        eligible_for_future_removal = review_status == "eligible_after_archive_review"

        candidates.append(
            HotStoreRemovalCandidate(
                raw_job_id=archive_record.raw_job_id,
                source_name=archive_record.source_name,
                archived_burden_category=archive_record.burden_category,
                current_burden_category=(
                    current_state.current_burden_category
                    if current_state is not None
                    else "<missing_from_hot_store>"
                ),
                retention_track=archive_record.retention_track,
                exists_in_hot_store=exists_in_hot_store,
                has_silver_job_now=has_silver_job_now,
                still_archive_candidate=still_archive_candidate,
                eligible_for_future_removal=eligible_for_future_removal,
                review_status=review_status,
                external_job_id=archive_record.external_job_id,
                source_url=archive_record.source_url,
                fetched_at=archive_record.fetched_at,
                initial_profile_name=archive_record.initial_profile_name,
                initial_search_term_snapshot=archive_record.initial_search_term_snapshot,
                raw_data_bytes=archive_record.raw_data_bytes,
            )
        )

    candidates.sort(key=lambda candidate: (candidate.source_name, candidate.raw_job_id))
    return candidates


def candidate_to_csv_row(candidate: HotStoreRemovalCandidate) -> dict[str, Any]:
    return {
        "raw_job_id": candidate.raw_job_id,
        "source_name": candidate.source_name,
        "archived_burden_category": candidate.archived_burden_category,
        "current_burden_category": candidate.current_burden_category,
        "retention_track": candidate.retention_track,
        "exists_in_hot_store": candidate.exists_in_hot_store,
        "has_silver_job_now": candidate.has_silver_job_now,
        "still_archive_candidate": candidate.still_archive_candidate,
        "eligible_for_future_removal": candidate.eligible_for_future_removal,
        "review_status": candidate.review_status,
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


def build_manifest(
    candidates: Sequence[HotStoreRemovalCandidate],
    archive_manifest: dict[str, Any],
    candidates_path: Path,
) -> dict[str, Any]:
    review_status_counts = Counter(candidate.review_status for candidate in candidates)
    source_counts = Counter(candidate.source_name for candidate in candidates)
    burden_counts = Counter(candidate.archived_burden_category for candidate in candidates)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "hot_store_removal_dry_run_only",
        "database_cleanup_action": "none",
        "retention_track": ARCHIVE_RETENTION_TRACK,
        "archive_manifest_generated_at_utc": archive_manifest.get("generated_at_utc"),
        "archive_record_count": archive_manifest.get("record_count"),
        "candidate_count": len(candidates),
        "eligible_for_future_removal_count": sum(
            int(candidate.eligible_for_future_removal)
            for candidate in candidates
        ),
        "blocked_or_non_actionable_count": sum(
            int(not candidate.eligible_for_future_removal)
            for candidate in candidates
        ),
        "silver_backed_rows_now": sum(
            int(candidate.has_silver_job_now)
            for candidate in candidates
        ),
        "review_status_counts": dict(review_status_counts),
        "source_counts": dict(source_counts),
        "archived_burden_category_counts": dict(burden_counts),
        "raw_data_bytes": sum(candidate.raw_data_bytes for candidate in candidates),
        "raw_data_size": format_bytes(sum(candidate.raw_data_bytes for candidate in candidates)),
        "exports": {
            "removal_candidates_csv": {
                "path": str(candidates_path),
                "size_bytes": candidates_path.stat().st_size,
                "sha256": compute_sha256(candidates_path),
            }
        },
        "interpretation_boundary": [
            "This manifest is a dry-run review artifact, not a deletion record.",
            "Rows remain in the database until a separate explicit cleanup workflow exists.",
            "Only rows with eligible_for_future_removal=true may be considered by a future reviewed removal step.",
            "Silver-backed rows must remain blocked from hot-store removal.",
        ],
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=json_default) + "\n",
        encoding="utf-8",
    )


def export_review(
    candidates: Sequence[HotStoreRemovalCandidate],
    archive_manifest: dict[str, Any],
    export_dir: Path,
) -> tuple[Path, Path]:
    candidates_path = export_dir / REMOVAL_CANDIDATES_FILENAME
    manifest_path = export_dir / REMOVAL_MANIFEST_FILENAME

    write_csv(
        candidates_path,
        [candidate_to_csv_row(candidate) for candidate in candidates],
    )
    write_manifest(
        manifest_path,
        build_manifest(
            candidates=candidates,
            archive_manifest=archive_manifest,
            candidates_path=candidates_path,
        ),
    )

    return candidates_path, manifest_path


def print_summary(candidates: Sequence[HotStoreRemovalCandidate]) -> None:
    review_status_counts = Counter(candidate.review_status for candidate in candidates)
    source_counts = Counter(candidate.source_name for candidate in candidates)

    print()
    print("Historical Burden Hot-Store Removal Dry-Run")
    print("Mode: dry-run only")
    print("Database cleanup action: none")
    print(f"Retention track: {ARCHIVE_RETENTION_TRACK}")
    print(f"Archived rows reviewed: {len(candidates)}")
    print(
        "Eligible for future removal: "
        f"{sum(int(candidate.eligible_for_future_removal) for candidate in candidates)}"
    )
    print(
        "Blocked or non-actionable: "
        f"{sum(int(not candidate.eligible_for_future_removal) for candidate in candidates)}"
    )
    print()
    print("Rows by source:")
    for source_name, count in source_counts.most_common():
        print(f"- {source_name}: {count}")
    print()
    print("Rows by review status:")
    for review_status, count in review_status_counts.most_common():
        print(f"- {review_status}: {count}")


def run_review(archive_dir: Path, export_dir: Path) -> None:
    manifest_path = archive_dir / ARCHIVE_MANIFEST_FILENAME
    records_path = archive_dir / ARCHIVE_RECORDS_FILENAME

    archive_manifest = validate_archive_manifest(manifest_path)
    archive_records = load_archive_records(records_path)

    if archive_manifest.get("record_count") != len(archive_records):
        raise ValueError(
            "Archive manifest record_count does not match archive records file: "
            f"{archive_manifest.get('record_count')} != {len(archive_records)}"
        )

    raw_job_ids = [record.raw_job_id for record in archive_records]

    with psycopg.connect(**get_database_config()) as connection:
        current_states = load_current_hot_store_state(connection, raw_job_ids)

    candidates = build_removal_candidates(
        archive_records=archive_records,
        current_states=current_states,
    )

    print_summary(candidates)
    candidates_path, removal_manifest_path = export_review(
        candidates=candidates,
        archive_manifest=archive_manifest,
        export_dir=export_dir,
    )

    print()
    print("Exported hot-store removal review files:")
    print(f"- {candidates_path}")
    print(f"- {removal_manifest_path}")
    print()
    print("Interpretation boundary:")
    print("- This script does not remove rows from the database.")
    print("- This script requires a validated archive export first.")
    print("- Eligible rows still require a separate explicit cleanup workflow.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
        help="Directory containing historical burden archive records and manifest.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Local output directory for the hot-store removal dry-run review.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_review(archive_dir=args.archive_dir, export_dir=args.export_dir)


if __name__ == "__main__":
    main()
