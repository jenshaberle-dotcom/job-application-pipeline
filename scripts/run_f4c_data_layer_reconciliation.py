"""Read-only F4C reconciliation for persisted Gold vs the All-jobs projection.

The Data Layers surface counts every persisted ``job_product_assessments`` row.
The Control Center ``All jobs`` surface does not consume the raw Product readiness
population directly: it consumes the operator presentation projection, which keeps
current Employer-Origin review rows, applies profile/geography scope and collapses
only exact safe duplicate identities.

This proof makes those populations and every Gold row outside All jobs explicit
before presentation semantics are changed. No rows are written and no provider or
network action is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from scripts.product_v1_control_center_base import load_product_v1_payload
from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator
from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


OPERATOR_BUCKETS = {
    "historical_jobs": "historical_job",
    "out_of_profile_jobs": "out_of_profile_job",
    "discovery_source_jobs": "discovery_source_job",
    "duplicate_origin_jobs": "duplicate_origin_job",
}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _ids(rows: Sequence[Mapping[str, Any]]) -> set[int]:
    result: set[int] = set()
    for row in rows:
        raw_id = row.get("silver_job_id")
        if raw_id is None:
            continue
        try:
            result.add(int(raw_id))
        except (TypeError, ValueError):
            continue
    return result


def classify_non_current_gold(
    row: Mapping[str, object], *, operator_bucket: str | None = None
) -> str:
    """Explain why one persisted Gold assessment is outside All jobs."""

    if operator_bucket:
        return operator_bucket
    if row.get("is_representative") is False:
        return "non_representative_identity_member"
    lifecycle = str(row.get("lifecycle_status") or "unknown")
    if lifecycle != "active_confirmed":
        return f"lifecycle_{lifecycle}"
    return "unexplained_active_representative_gap"


def build_report(*, source_sha: str) -> dict[str, object]:
    core = load_product_v1_payload(include_source_connector_overview=False)
    base_rows = _rows(core.get("job_readiness"))
    base_ids = _ids(base_rows)
    if len(base_ids) != len(base_rows):
        raise RuntimeError("F4C_BASE_PRODUCT_JOB_IDENTITY_NOT_ONE_TO_ONE")

    operator = enrich_product_payload_for_operator(core)
    all_job_rows = _rows(operator.get("job_readiness"))
    all_job_ids = _ids(all_job_rows)
    if len(all_job_ids) != len(all_job_rows):
        raise RuntimeError("F4C_ALL_JOBS_IDENTITY_NOT_ONE_TO_ONE")
    if not all_job_ids.issubset(base_ids):
        raise RuntimeError("F4C_ALL_JOBS_NOT_SUBSET_OF_BASE_READINESS")

    bucket_by_id: dict[int, str] = {}
    bucket_counts: dict[str, int] = {}
    for key, reason in OPERATOR_BUCKETS.items():
        bucket_rows = _rows(operator.get(key))
        bucket_ids = _ids(bucket_rows)
        bucket_counts[key] = len(bucket_rows)
        for silver_job_id in bucket_ids:
            bucket_by_id.setdefault(silver_job_id, reason)

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(),
        row_factory=dict_row,
    ) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT
                        assessment.silver_job_id,
                        assessment.assessed_at,
                        silver.source_name,
                        silver.title,
                        silver.source_url,
                        lifecycle.lifecycle_status,
                        identity.identity_kind,
                        identity.identity_group_size,
                        identity.is_representative
                    FROM job_product_assessments assessment
                    JOIN silver_jobs silver
                      ON silver.id = assessment.silver_job_id
                    LEFT JOIN gold_job_lifecycle_health lifecycle
                      ON lifecycle.silver_job_id = assessment.silver_job_id
                    LEFT JOIN gold_vacancy_identity identity
                      ON identity.silver_job_id = assessment.silver_job_id
                    ORDER BY assessment.silver_job_id
                    """
                )
                assessed_rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()

    assessed_ids = {int(row["silver_job_id"]) for row in assessed_rows}
    gold_in_all_jobs = assessed_ids & all_job_ids
    gold_outside_all_jobs = [
        row for row in assessed_rows if int(row["silver_job_id"]) not in all_job_ids
    ]
    all_jobs_without_gold = sorted(all_job_ids - assessed_ids)

    reason_counts: Counter[str] = Counter()
    bounded_rows: list[dict[str, object]] = []
    for row in gold_outside_all_jobs:
        silver_job_id = int(row["silver_job_id"])
        reason = classify_non_current_gold(
            row,
            operator_bucket=bucket_by_id.get(silver_job_id),
        )
        reason_counts[reason] += 1
        bounded_rows.append(
            {
                "silver_job_id": silver_job_id,
                "source_name": row.get("source_name"),
                "title": row.get("title"),
                "source_url": row.get("source_url"),
                "assessed_at": row.get("assessed_at"),
                "lifecycle_status": row.get("lifecycle_status"),
                "identity_kind": row.get("identity_kind"),
                "identity_group_size": row.get("identity_group_size"),
                "is_representative": row.get("is_representative"),
                "operator_bucket": bucket_by_id.get(silver_job_id),
                "reason": reason,
            }
        )

    summary = {
        "base_product_readiness_count": len(base_rows),
        "operator_all_jobs_count": len(all_job_rows),
        "operator_bucket_counts": bucket_counts,
        "persisted_gold_assessment_count": len(assessed_rows),
        "persisted_gold_in_all_jobs_count": len(gold_in_all_jobs),
        "persisted_gold_outside_all_jobs_count": len(gold_outside_all_jobs),
        "all_jobs_without_gold_assessment_count": len(all_jobs_without_gold),
        "gold_outside_all_jobs_reason_counts": dict(sorted(reason_counts.items())),
        "unexplained_active_representative_gap_count": reason_counts[
            "unexplained_active_representative_gap"
        ],
    }
    return {
        "schema_version": "f4c.data_layer_reconciliation.v2",
        "source_sha": source_sha,
        "summary": summary,
        "persisted_gold_outside_all_jobs": bounded_rows,
        "all_jobs_without_gold_assessment_ids": all_jobs_without_gold,
        "boundaries": {
            "db_writes": 0,
            "provider_calls": 0,
            "network_probes": 0,
            "ranking_authority_changed": False,
            "application_authority_changed": False,
            "source_activation_changed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(source_sha=args.source_sha)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
