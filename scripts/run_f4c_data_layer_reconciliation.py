"""Read-only F4C reconciliation for persisted Gold vs current Product jobs.

The Data Layers surface historically counted every persisted
``job_product_assessments`` row while the Control Center ``All jobs`` surface
consumes the current canonical Product readiness projection.  This proof makes
that population difference explicit before changing presentation semantics.

No rows are written and no provider/network action is performed.
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
from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def classify_non_current_gold(row: Mapping[str, object]) -> str:
    """Explain why one persisted Gold assessment is not in current Product jobs."""

    if row.get("is_representative") is False:
        return "non_representative_identity_member"
    lifecycle = str(row.get("lifecycle_status") or "unknown")
    if lifecycle != "active_confirmed":
        return f"lifecycle_{lifecycle}"
    return "unexplained_active_representative_gap"


def build_report(*, source_sha: str) -> dict[str, object]:
    payload = load_product_v1_payload(include_source_connector_overview=False)
    raw_jobs = payload.get("job_readiness")
    if not isinstance(raw_jobs, Sequence) or isinstance(raw_jobs, (str, bytes)):
        raise RuntimeError("F4C_PRODUCT_JOB_READINESS_MISSING")

    current_rows = [row for row in raw_jobs if isinstance(row, Mapping)]
    current_ids = {
        int(row["silver_job_id"])
        for row in current_rows
        if row.get("silver_job_id") is not None
    }
    if len(current_ids) != len(current_rows):
        raise RuntimeError("F4C_PRODUCT_JOB_IDENTITY_NOT_ONE_TO_ONE")

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
    non_current = [
        row for row in assessed_rows if int(row["silver_job_id"]) not in current_ids
    ]
    current_without_assessment = sorted(current_ids - assessed_ids)

    reason_counts: Counter[str] = Counter()
    bounded_rows: list[dict[str, object]] = []
    for row in non_current:
        reason = classify_non_current_gold(row)
        reason_counts[reason] += 1
        bounded_rows.append(
            {
                "silver_job_id": int(row["silver_job_id"]),
                "source_name": row.get("source_name"),
                "title": row.get("title"),
                "source_url": row.get("source_url"),
                "assessed_at": row.get("assessed_at"),
                "lifecycle_status": row.get("lifecycle_status"),
                "identity_kind": row.get("identity_kind"),
                "identity_group_size": row.get("identity_group_size"),
                "is_representative": row.get("is_representative"),
                "reason": reason,
            }
        )

    summary = {
        "persisted_gold_assessment_count": len(assessed_rows),
        "current_product_job_count": len(current_rows),
        "persisted_gold_not_current_product_count": len(non_current),
        "current_product_without_gold_assessment_count": len(current_without_assessment),
        "non_current_reason_counts": dict(sorted(reason_counts.items())),
        "unexplained_active_representative_gap_count": reason_counts[
            "unexplained_active_representative_gap"
        ],
    }
    return {
        "schema_version": "f4c.data_layer_reconciliation.v1",
        "source_sha": source_sha,
        "summary": summary,
        "persisted_gold_not_current_product": bounded_rows,
        "current_product_without_gold_assessment_ids": current_without_assessment,
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
