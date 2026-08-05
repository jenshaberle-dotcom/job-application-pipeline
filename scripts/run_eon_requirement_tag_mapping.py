from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.run_eon_requirement_inventory import (
    EXPECTED_RAW_JOB_ID,
    EXPECTED_SILVER_JOB_ID,
    build_inventory_from_binding,
    connect,
    load_exact_eon_binding,
)
from src.search_intelligence.eon_requirement_tag_mapping import (
    REPORT_SCHEMA,
    EonRequirementTagMap,
    build_eon_requirement_tag_map,
)


def write_report(
    *,
    output_dir: Path,
    tag_map: EonRequirementTagMap,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"eon_requirement_tag_map_{stamp}.json"
    payload: Mapping[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "mode": "read_only",
        "raw_job_id": EXPECTED_RAW_JOB_ID,
        "silver_job_id": EXPECTED_SILVER_JOB_ID,
        "tag_map": tag_map.canonical_payload(),
        "unique_tags": list(tag_map.unique_tags()),
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
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Map the exact proven E.ON requirement inventory to canonical review tags "
            "without comparing Candidate Facts or mutating database state."
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
            inventory = build_inventory_from_binding(binding)
            tag_map = build_eon_requirement_tag_map(inventory)
        conn.rollback()
    finally:
        conn.close()

    report_path = write_report(output_dir=args.output_dir, tag_map=tag_map)

    print("E.ON requirement tag map")
    print("mode: read_only")
    print(f"tag_map_key: {tag_map.tag_map_key}")
    print(f"inventory_key: {tag_map.inventory_key}")
    print(f"raw_job_id: {EXPECTED_RAW_JOB_ID}")
    print(f"silver_job_id: {EXPECTED_SILVER_JOB_ID}")
    print(f"description_sha256: {tag_map.description_sha256}")
    print(f"section_sha256: {tag_map.section_sha256}")
    print(f"tag_map_sha256: {tag_map.tag_map_sha256}")
    print(f"statement_count: {len(tag_map.mappings)}")
    print(f"unique_tag_count: {len(tag_map.unique_tags())}")
    for mapping in tag_map.mappings:
        print(
            f"mapping_{mapping.order:02d}: {mapping.statement_key} | "
            f"expectation={mapping.source_expectation_class} | "
            f"obligation={mapping.obligation_strength} | "
            f"tags={','.join(mapping.tags)} | {mapping.text}"
        )
    print("database_writes: 0")
    print("candidate_fact_reads: 0")
    print("capability_fit_decision_created: false")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
