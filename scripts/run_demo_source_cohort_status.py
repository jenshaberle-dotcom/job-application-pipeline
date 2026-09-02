"""Read-only DEMO-001 status for the qualified Eraneos / 1KOMMA5° cohort.

The runner reports where the already-ingested live cohort currently sits between
Silver, lifecycle authority, Product V1 assessment/readiness and the Control Center
Top-5. It never writes database state, calls a provider, activates a source, or
creates ranking/application truth.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from scripts.run_product_v1_control_center import load_product_v1_payload
from src.config import get_database_config
from src.search_intelligence.product_v1_contenders import classify_role_title


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "demo_source_cohort_status.json"
COHORT_SOURCES = ("personio:eraneos", "personio:1komma5grad")

READINESS_ORDER = {
    "rankable": 0,
    "ranking_policy_required": 1,
    "hard_filter_evidence_required": 2,
    "assessment_required": 3,
    "activity_evidence_required": 4,
    "origin_validation_required": 5,
    "blocked_hard_filter": 6,
    "blocked_inactive": 7,
    "blocked_origin": 8,
}


def _read_rows() -> list[dict[str, object]]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT
                    silver_job_id,
                    title,
                    company_name,
                    city,
                    country,
                    publication_date,
                    source_name,
                    source_url,
                    canonical_source_type,
                    origin_validation_status,
                    activity_status,
                    hard_filter_status,
                    profile_direction_score,
                    data_focus_score,
                    reliability_focus_score,
                    evidence_quality_score,
                    overall_quality_score,
                    product_readiness_status,
                    lifecycle_status,
                    last_positive_observed_at,
                    last_health_checked_at,
                    lifecycle_evidence_reason,
                    latest_health_outcome,
                    latest_health_coverage,
                    assessment_activity_status
                FROM gold_product_v1_job_readiness
                WHERE source_name = ANY(%s)
                ORDER BY source_name, silver_job_id
                """,
                (list(COHORT_SOURCES),),
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return rows


def _role_signal(title: object) -> dict[str, object] | None:
    signal = classify_role_title(str(title or ""))
    if signal is None:
        return None
    return {
        "tier": signal.tier,
        "family": signal.family,
        "signals": list(signal.signals),
    }


def _compact_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "silver_job_id": row.get("silver_job_id"),
        "source_name": row.get("source_name"),
        "company_name": row.get("company_name"),
        "title": row.get("title"),
        "city": row.get("city"),
        "country": row.get("country"),
        "source_url": row.get("source_url"),
        "canonical_source_type": row.get("canonical_source_type"),
        "role_signal": _role_signal(row.get("title")),
        "lifecycle_status": row.get("lifecycle_status"),
        "last_positive_observed_at": row.get("last_positive_observed_at"),
        "last_health_checked_at": row.get("last_health_checked_at"),
        "origin_validation_status": row.get("origin_validation_status"),
        "activity_status": row.get("activity_status"),
        "hard_filter_status": row.get("hard_filter_status"),
        "profile_direction_score": row.get("profile_direction_score"),
        "data_focus_score": row.get("data_focus_score"),
        "reliability_focus_score": row.get("reliability_focus_score"),
        "evidence_quality_score": row.get("evidence_quality_score"),
        "overall_quality_score": row.get("overall_quality_score"),
        "product_readiness_status": row.get("product_readiness_status"),
    }


def summarize_status(
    rows: Sequence[Mapping[str, object]],
    top_jobs: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    compact = [_compact_row(row) for row in rows]
    current = [
        row for row in compact if row.get("lifecycle_status") == "active_confirmed"
    ]
    profile_relevant = [row for row in current if row.get("role_signal") is not None]
    readiness_counts = Counter(
        str(row.get("product_readiness_status") or "unknown") for row in current
    )
    cohort_top = [
        dict(row)
        for row in top_jobs
        if str(row.get("source_name") or "") in COHORT_SOURCES
    ]

    ordered = sorted(
        profile_relevant,
        key=lambda row: (
            READINESS_ORDER.get(
                str(row.get("product_readiness_status") or "unknown"), 99
            ),
            -float(row.get("overall_quality_score") or 0.0),
            int(row.get("silver_job_id") or 0),
        ),
    )

    if not current:
        next_gate = "lifecycle_current_activity"
    elif any(row.get("origin_validation_status") is None for row in profile_relevant):
        next_gate = "product_v1_assessment_materialization"
    elif any(
        row.get("hard_filter_status") == "unknown" for row in profile_relevant
    ):
        next_gate = "hard_filter_evidence"
    elif any(
        row.get("product_readiness_status") == "assessment_required"
        for row in profile_relevant
    ):
        next_gate = "ranking_assessment_scores"
    elif any(
        row.get("product_readiness_status") == "rankable" for row in profile_relevant
    ) and not cohort_top:
        next_gate = "top5_policy_result"
    elif cohort_top:
        next_gate = "application_readiness"
    else:
        next_gate = "review_current_product_truth"

    return {
        "schema": "job_application_pipeline.demo_source_cohort_status.v1",
        "sources": list(COHORT_SOURCES),
        "summary": {
            "silver_job_count": len(compact),
            "current_active_count": len(current),
            "profile_relevant_current_count": len(profile_relevant),
            "cohort_top5_count": len(cohort_top),
            "readiness_counts_current": dict(sorted(readiness_counts.items())),
            "next_gate": next_gate,
        },
        "profile_relevant_current_jobs": ordered,
        "all_current_jobs": current,
        "cohort_top_jobs": cohort_top,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "network_requests": 0,
            "provider_or_llm_requests": 0,
            "source_activation": False,
            "assessment_mutation": False,
            "ranking_or_top5_mutation": False,
            "application_or_submission_writes": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = _read_rows()
    payload = load_product_v1_payload()
    raw_top = payload.get("top_jobs")
    top_jobs = (
        [row for row in raw_top if isinstance(row, Mapping)]
        if isinstance(raw_top, list)
        else []
    )
    report = summarize_status(rows, top_jobs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("============================================")
    print("DEMO SOURCE COHORT STATUS")
    print("============================================")
    print(f"SILVER={summary['silver_job_count']}")
    print(f"CURRENT_ACTIVE={summary['current_active_count']}")
    print(f"PROFILE_RELEVANT_CURRENT={summary['profile_relevant_current_count']}")
    print(f"COHORT_TOP5={summary['cohort_top5_count']}")
    print(
        "READINESS_COUNTS="
        + json.dumps(summary["readiness_counts_current"], sort_keys=True)
    )
    print(f"NEXT_GATE={summary['next_gate']}")
    for row in report["profile_relevant_current_jobs"]:
        print(
            "JOB="
            f"{row.get('silver_job_id')}|{row.get('source_name')}|"
            f"{row.get('product_readiness_status')}|{row.get('title')}"
        )
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("DEMO_SOURCE_COHORT_STATUS=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
