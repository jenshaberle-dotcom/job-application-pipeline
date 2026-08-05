from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_eon_requirement_inventory import (
    EXPECTED_RAW_JOB_ID,
    EXPECTED_SILVER_JOB_ID,
    load_exact_eon_binding,
)
from src.config import get_database_config
from src.search_intelligence.eon_requirement_heading_diagnostic import (
    diagnostic_payload,
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _description_from_binding(binding: Mapping[str, Any]) -> object:
    raw_data = binding.get("raw_data")
    if not isinstance(raw_data, Mapping):
        raise ValueError("E.ON raw_data must be an object")
    job = raw_data.get("job")
    if not isinstance(job, Mapping):
        raise ValueError("E.ON raw_data.job must be an object")
    return job.get("description")


def write_report(*, output_dir: Path, payload: Mapping[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_requirement_heading_diagnostic_{stamp}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose normalized heading candidates for the exact stored E.ON "
            "requirement inventory without mutating database state."
        )
    )
    parser.add_argument("--raw-job-id", type=int, default=EXPECTED_RAW_JOB_ID)
    parser.add_argument("--silver-job-id", type=int, default=EXPECTED_SILVER_JOB_ID)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    conn = connect()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
            binding = load_exact_eon_binding(
                conn,
                raw_job_id=args.raw_job_id,
                silver_job_id=args.silver_job_id,
            )
            payload = diagnostic_payload(_description_from_binding(binding))
        conn.rollback()
    finally:
        conn.close()

    report_path = write_report(output_dir=args.output_dir, payload=payload)

    print("E.ON requirement heading diagnostic")
    print("mode: read_only")
    print(f"raw_job_id: {EXPECTED_RAW_JOB_ID}")
    print(f"silver_job_id: {EXPECTED_SILVER_JOB_ID}")
    print(f"candidate_count: {payload['candidate_count']}")
    for candidate_number, candidate in enumerate(payload["candidates"], start=1):
        print(
            f"candidate_{candidate_number:02d}: "
            f"line_index={candidate['line_index']} | {candidate['ascii_repr']}"
        )
        characters = candidate["non_ascii_characters"]
        if not characters:
            print(f"candidate_{candidate_number:02d}_unicode: none")
            continue
        rendered = ", ".join(
            f"index={item['index']} {item['codepoint']} "
            f"{item['name']} category={item['category']}"
            for item in characters
        )
        print(f"candidate_{candidate_number:02d}_unicode: {rendered}")
    print("database_writes: 0")
    print("candidate_fact_reads: 0")
    print("capability_fit_decision_created: false")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
