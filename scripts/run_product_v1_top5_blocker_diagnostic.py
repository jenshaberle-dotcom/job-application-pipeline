"""Read-only diagnostic for current Product V1 Top-5 blockers.

This runner reads only current Product V1 authority views. It does not refresh
assessments, write hard-filter reviews, create ranking authority, mutate
applications, call providers, or change source/scheduler state.

Its purpose is to identify the exact population-level reason why the current
authoritative Top-5 projection is empty and to expose component-level hard-filter
states for the highest-affinity current jobs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


SCHEMA = "job_application_pipeline.product_v1_top5_blocker_diagnostic.v1"
DEFAULT_OUTPUT = Path(".runtime/diagnostics/product_v1_top5_blockers.json")
EXCLUDED_AGGREGATOR_SOURCES = ("bundesagentur_fuer_arbeit", "stepstone")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _component_unknowns(row: Mapping[str, object]) -> list[str]:
    components = (
        ("employment", row.get("employment_status")),
        ("languages", row.get("language_status")),
        ("weekly_hours", row.get("weekly_hours_status")),
        ("seniority_and_capability_fit", row.get("seniority_status")),
    )
    return [
        name
        for name, status in components
        if str(status or "") == "manual_review_required"
    ]


def _read_current_rows(conn: psycopg.Connection[Any]) -> list[dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                readiness.silver_job_id,
                readiness.company_name,
                readiness.title,
                readiness.source_name,
                readiness.source_url,
                readiness.overall_quality_score,
                readiness.affinity_authority_status,
                readiness.lifecycle_status,
                readiness.origin_validation_status,
                readiness.product_readiness_status,
                readiness.hard_filter_status,
                assessment.capability_fit_status,
                hard_filter.employment_status,
                hard_filter.language_status,
                hard_filter.weekly_hours_status,
                hard_filter.seniority_status,
                hard_filter.deterministic_hard_filter_status,
                hard_filter.operator_review_decision,
                hard_filter.operator_review_valid,
                hard_filter.hard_filter_reasons,
                hard_filter.policy_version
            FROM gold_product_v1_job_readiness readiness
            LEFT JOIN job_product_assessments assessment
              ON assessment.silver_job_id = readiness.silver_job_id
            LEFT JOIN gold_product_v1_hard_filter_evaluation hard_filter
              ON hard_filter.silver_job_id = readiness.silver_job_id
            WHERE readiness.source_name <> ALL(%s)
            ORDER BY
                readiness.overall_quality_score DESC NULLS LAST,
                readiness.silver_job_id
            """,
            (list(EXCLUDED_AGGREGATOR_SOURCES),),
        )
        return [dict(row) for row in cur.fetchall()]


def _read_policy(conn: psycopg.Connection[Any]) -> dict[str, object]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                status,
                policy_version,
                minimum_quality_score,
                top_job_limit,
                comparable_score_delta
            FROM product_v1_ranking_policy
            WHERE policy_key = 'default'
            """
        )
        row = cur.fetchone()
        return dict(row or {})


def _read_top_count(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS count FROM gold_product_v1_top_jobs")
        row = cur.fetchone()
        return int((row or {}).get("count") or 0)


def build_report(
    *,
    rows: list[dict[str, object]],
    ranking_policy: Mapping[str, object],
    top_job_count: int,
    detail_limit: int,
) -> dict[str, object]:
    readiness_counts = Counter(
        str(row.get("product_readiness_status") or "unknown") for row in rows
    )
    hard_filter_counts = Counter(
        str(row.get("hard_filter_status") or "unknown") for row in rows
    )
    component_counts = {
        "employment": Counter(
            str(row.get("employment_status") or "missing") for row in rows
        ),
        "languages": Counter(
            str(row.get("language_status") or "missing") for row in rows
        ),
        "weekly_hours": Counter(
            str(row.get("weekly_hours_status") or "missing") for row in rows
        ),
        "seniority_and_capability_fit": Counter(
            str(row.get("seniority_status") or "missing") for row in rows
        ),
    }

    current_active = [
        row for row in rows if row.get("lifecycle_status") == "active_confirmed"
    ]
    hard_filter_unknown = [
        row
        for row in current_active
        if row.get("product_readiness_status") == "hard_filter_evidence_required"
    ]
    assessment_required = [
        row
        for row in current_active
        if row.get("product_readiness_status") == "assessment_required"
    ]
    blocked_hard_filter = [
        row
        for row in current_active
        if row.get("product_readiness_status") == "blocked_hard_filter"
    ]
    rankable = [
        row for row in current_active if row.get("product_readiness_status") == "rankable"
    ]

    def expose(row: Mapping[str, object]) -> dict[str, object]:
        return {
            "silver_job_id": row.get("silver_job_id"),
            "company_name": row.get("company_name"),
            "title": row.get("title"),
            "source_name": row.get("source_name"),
            "overall_quality_score": row.get("overall_quality_score"),
            "affinity_authority_status": row.get("affinity_authority_status"),
            "lifecycle_status": row.get("lifecycle_status"),
            "origin_validation_status": row.get("origin_validation_status"),
            "product_readiness_status": row.get("product_readiness_status"),
            "hard_filter_status": row.get("hard_filter_status"),
            "deterministic_hard_filter_status": row.get(
                "deterministic_hard_filter_status"
            ),
            "capability_fit_status": row.get("capability_fit_status"),
            "employment_status": row.get("employment_status"),
            "language_status": row.get("language_status"),
            "weekly_hours_status": row.get("weekly_hours_status"),
            "seniority_status": row.get("seniority_status"),
            "operator_review_decision": row.get("operator_review_decision"),
            "operator_review_valid": row.get("operator_review_valid"),
            "unknown_components": _component_unknowns(row),
            "hard_filter_reasons": row.get("hard_filter_reasons"),
            "policy_version": row.get("policy_version"),
        }

    highest_affinity_blocked = [
        expose(row)
        for row in hard_filter_unknown[:detail_limit]
    ]
    valuny = [
        expose(row)
        for row in rows
        if "valuny" in str(row.get("company_name") or "").casefold()
    ]

    return {
        "schema": SCHEMA,
        "status": "read_only_complete",
        "ranking_policy": dict(ranking_policy),
        "summary": {
            "review_scope_job_count": len(rows),
            "current_active_count": len(current_active),
            "rankable_count": len(rankable),
            "top_job_count": top_job_count,
            "hard_filter_evidence_required_count": len(hard_filter_unknown),
            "assessment_required_count": len(assessment_required),
            "blocked_hard_filter_count": len(blocked_hard_filter),
            "affinity_authoritative_count": sum(
                row.get("affinity_authority_status") == "authoritative"
                for row in current_active
            ),
        },
        "readiness_counts": dict(readiness_counts),
        "hard_filter_counts": dict(hard_filter_counts),
        "hard_filter_component_counts": {
            name: dict(counter) for name, counter in component_counts.items()
        },
        "highest_affinity_hard_filter_blocked": highest_affinity_blocked,
        "valuny": valuny,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "network_requests": 0,
            "provider_requests": 0,
            "hard_filter_reviews_written": 0,
            "ranking_or_top5_writes": 0,
            "application_or_submission_actions": 0,
            "source_or_scheduler_mutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail-limit", type=int, default=20)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.detail_limit <= 100:
        raise SystemExit("--detail-limit must be between 1 and 100")

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        rows = _read_current_rows(conn)
        policy = _read_policy(conn)
        top_count = _read_top_count(conn)
        conn.rollback()

    report = build_report(
        rows=rows,
        ranking_policy=policy,
        top_job_count=top_count,
        detail_limit=args.detail_limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("=== PRODUCT V1 TOP-5 BLOCKER DIAGNOSTIC ===")
    print(f"REVIEW_SCOPE={summary['review_scope_job_count']}")
    print(f"CURRENT_ACTIVE={summary['current_active_count']}")
    print(f"RANKABLE={summary['rankable_count']}")
    print(f"TOP5={summary['top_job_count']}")
    print(
        "HARD_FILTER_EVIDENCE_REQUIRED="
        f"{summary['hard_filter_evidence_required_count']}"
    )
    print(f"ASSESSMENT_REQUIRED={summary['assessment_required_count']}")
    print(f"BLOCKED_HARD_FILTER={summary['blocked_hard_filter_count']}")
    for name, counts in report["hard_filter_component_counts"].items():
        print(
            "COMPONENT="
            f"{name}|"
            + ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))
        )
    for row in report["highest_affinity_hard_filter_blocked"]:
        print(
            "BLOCKED_JOB="
            f"{row['silver_job_id']}|score={row['overall_quality_score']}|"
            f"capability={row['capability_fit_status']}|"
            f"employment={row['employment_status']}|"
            f"languages={row['language_status']}|"
            f"hours={row['weekly_hours_status']}|"
            f"seniority={row['seniority_status']}|"
            f"unknown={','.join(row['unknown_components'])}|"
            f"{row['company_name']}|{row['title']}"
        )
    for row in report["valuny"]:
        print(
            "VALUNY="
            f"{row['silver_job_id']}|score={row['overall_quality_score']}|"
            f"readiness={row['product_readiness_status']}|"
            f"capability={row['capability_fit_status']}|"
            f"employment={row['employment_status']}|"
            f"languages={row['language_status']}|"
            f"hours={row['weekly_hours_status']}|"
            f"seniority={row['seniority_status']}|"
            f"unknown={','.join(row['unknown_components'])}|{row['title']}"
        )
    print("DATABASE_WRITES=0")
    print("NETWORK_REQUESTS=0")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_TOP5_BLOCKER_DIAGNOSTIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
