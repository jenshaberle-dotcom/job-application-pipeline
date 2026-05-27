from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.export_historical_burden_archive import (
    ARCHIVE_RETENTION_TRACK,
    HistoricalBurdenArchiveRecord,
    build_manifest,
    compute_sha256,
    export_archive,
    json_default,
    summarize_records,
)


def make_archive_record(
    raw_job_id: int,
    source_name: str = "greenhouse:stripe",
    burden_category: str = "greenhouse_without_current_matching_metadata",
    has_silver_job: bool = False,
) -> HistoricalBurdenArchiveRecord:
    return HistoricalBurdenArchiveRecord(
        raw_job_id=raw_job_id,
        source_name=source_name,
        external_job_id=f"job-{raw_job_id}",
        source_url=f"https://example.com/jobs/{raw_job_id}",
        fetched_at=datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc),
        ingestion_run_id=raw_job_id,
        search_profile_id=1,
        initial_profile_name="greenhouse_stripe",
        initial_search_term_snapshot="*",
        burden_category=burden_category,
        retention_track=ARCHIVE_RETENTION_TRACK,
        review_action="export and document; exclude from Trend/Gold calculations; remove from hot store after review",
        has_silver_job=has_silver_job,
        processing_decision="skipped",
        raw_data_bytes=100,
        raw_data={"id": raw_job_id, "title": "Example"},
    )


def test_json_default_serializes_datetime() -> None:
    value = datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc)

    assert json_default(value) == "2026-05-27T08:00:00+00:00"


def test_summarize_records_groups_by_burden_category_and_source() -> None:
    records = [
        make_archive_record(1),
        make_archive_record(2),
        make_archive_record(
            3,
            source_name="stepstone",
            burden_category="commercial_aggregator_history",
        ),
    ]

    summary_rows = summarize_records(records)

    assert len(summary_rows) == 2
    assert summary_rows[0]["raw_jobs"] == 2
    assert summary_rows[0]["source_name"] == "greenhouse:stripe"
    assert summary_rows[0]["retention_track"] == ARCHIVE_RETENTION_TRACK
    assert summary_rows[0]["silver_backed_rows"] == 0


def test_export_archive_writes_jsonl_summary_and_manifest(tmp_path: Path) -> None:
    records = [make_archive_record(1), make_archive_record(2)]

    records_path, summary_path, manifest_path = export_archive(records, tmp_path)

    assert records_path.exists()
    assert summary_path.exists()
    assert manifest_path.exists()

    jsonl_rows = [json.loads(line) for line in records_path.read_text().splitlines()]
    assert [row["raw_job_id"] for row in jsonl_rows] == [1, 2]
    assert jsonl_rows[0]["raw_data"] == {"id": 1, "title": "Example"}

    with summary_path.open(newline="", encoding="utf-8") as csv_file:
        summary_rows = list(csv.DictReader(csv_file))

    assert summary_rows[0]["retention_track"] == ARCHIVE_RETENTION_TRACK
    assert summary_rows[0]["raw_jobs"] == "2"

    manifest = json.loads(manifest_path.read_text())
    assert manifest["database_cleanup_action"] == "none"
    assert manifest["retention_track"] == ARCHIVE_RETENTION_TRACK
    assert manifest["record_count"] == 2
    assert manifest["silver_backed_rows"] == 0
    assert "sha256" in manifest["exports"]["records_jsonl"]


def test_build_manifest_records_hashes_and_counts(tmp_path: Path) -> None:
    records = [make_archive_record(1)]
    records_path = tmp_path / "records.jsonl"
    summary_path = tmp_path / "summary.csv"

    records_path.write_text('{"raw_job_id": 1}\n', encoding="utf-8")
    summary_path.write_text("raw_jobs\n1\n", encoding="utf-8")

    manifest = build_manifest(
        records=records,
        jsonl_path=records_path,
        summary_path=summary_path,
    )

    assert manifest["record_count"] == 1
    assert manifest["raw_data_bytes"] == 100
    assert manifest["source_counts"] == {"greenhouse:stripe": 1}
    assert manifest["exports"]["records_jsonl"]["sha256"] == compute_sha256(records_path)
