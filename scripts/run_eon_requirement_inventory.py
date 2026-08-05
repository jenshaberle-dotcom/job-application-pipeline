from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.ingestion.eon_controlled_pilot import EXPECTED_TITLE
from src.search_intelligence.eon_product_v1_assessment import bind_eon_job
from src.search_intelligence.eon_requirement_inventory import (
    INVENTORY_KEY,
    REPORT_SCHEMA,
    EonRequirementInventory,
    build_eon_requirement_inventory,
)


EXPECTED_RAW_JOB_ID = 26342
EXPECTED_SILVER_JOB_ID = 466


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_exact_eon_binding(
    conn: psycopg.Connection[Any],
    *,
    raw_job_id: int,
    silver_job_id: int,
) -> Mapping[str, Any]:
    if raw_job_id != EXPECTED_RAW_JOB_ID or silver_job_id != EXPECTED_SILVER_JOB_ID:
        raise ValueError("runner is bound to the exact E.ON pilot IDs")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                r.id AS raw_job_id,
                s.id AS silver_job_id,
                r.source_name,
                r.external_job_id,
                r.raw_data,
                s.title,
                s.canonical_source_type
            FROM raw_jobs r
            JOIN silver_jobs s
              ON s.raw_job_id = r.id
            WHERE r.id = %s
              AND s.id = %s
            """,
            (raw_job_id, silver_job_id),
        )
        rows = cur.fetchall()

    if len(rows) != 1:
        raise ValueError(
            "expected exactly one joined raw/Silver E.ON job, "
            f"found {len(rows)}"
        )

    row = rows[0]
    bind_eon_job(
        row=row,
        expected_raw_job_id=raw_job_id,
        expected_silver_job_id=silver_job_id,
    )
    return row


def build_inventory_from_binding(
    binding: Mapping[str, Any],
) -> EonRequirementInventory:
    raw_data = binding["raw_data"]
    if not isinstance(raw_data, Mapping):
        raise ValueError("E.ON raw_data must be an object")
    job = raw_data.get("job")
    if not isinstance(job, Mapping):
        raise ValueError("E.ON raw_data.job must be an object")
    _require(job.get("title") == EXPECTED_TITLE, "stored E.ON job title mismatch")
    return build_eon_requirement_inventory(
        description=job.get("description"),
        title=job.get("title"),
    )


def write_report(
    *,
    output_dir: Path,
    inventory: EonRequirementInventory,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_requirement_inventory_{stamp}.json"
    payload = {
        "schema_version": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "mode": "read_only",
        "raw_job_id": EXPECTED_RAW_JOB_ID,
        "silver_job_id": EXPECTED_SILVER_JOB_ID,
        "inventory": inventory.canonical_payload(),
        "family_counts": inventory.family_counts(),
        "boundaries": {
            "database_writes": 0,
            "candidate_fact_reads": 0,
            "candidate_fact_writes": 0,
            "capability_fit_decision_created": False,
            "assessment_mutation": False,
            "readiness_mutation": False,
            "ranking_scores_created": False,
            "weekly_hours_inferred": False,
            "network_requests": 0,
            "provider_requests": 0,
            "source_or_scheduler_activation": False,
            "application_action_performed": False,
        },
    }
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Project the exact stored E.ON profile requirements read-only."
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
            inventory = build_inventory_from_binding(binding)
        conn.rollback()
    finally:
        conn.close()

    report_path = write_report(
        output_dir=args.output_dir,
        inventory=inventory,
    )

    print("E.ON requirement inventory")
    print("mode: read_only")
    print(f"inventory_key: {INVENTORY_KEY}")
    print(f"raw_job_id: {EXPECTED_RAW_JOB_ID}")
    print(f"silver_job_id: {EXPECTED_SILVER_JOB_ID}")
    print(f"section_heading: {inventory.section_heading}")
    print(f"description_sha256: {inventory.description_sha256}")
    print(f"section_sha256: {inventory.section_sha256}")
    print(f"statement_count: {len(inventory.statements)}")
    print(
        "family_counts: "
        + ", ".join(
            f"{family}={count}"
            for family, count in inventory.family_counts().items()
        )
    )
    for statement in inventory.statements:
        print(
            f"statement_{statement.order:02d}: "
            f"[{statement.family}] "
            f"{statement.statement_key} | {statement.text}"
        )
    print("database_writes: 0")
    print("candidate_fact_reads: 0")
    print("capability_fit_decision_created: false")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
