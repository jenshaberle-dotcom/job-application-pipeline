"""Bounded DEMO-001 Product V1 refill through existing authority gates.

The runner targets the real live/refill cohort discovered by
``run_demo_001_rankable_refill_scout``. It may create only two existing reviewed
Product states:

1. Candidate-Fact-backed capability-fit reviews where approved Candidate Facts have
   exact capability-tag matches on the live employer-origin vacancy detail.
2. Deterministic ranking-score reviews, but only after the canonical hard-filter
   view reports ``passed``.

It never auto-passes or writes a hard-filter operator review. Missing/unknown/failed
hard-filter evidence therefore remains fail-closed. It never forces rank, Top-5,
application, submission, source activation or lifecycle state.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from scripts import run_product_v1_capability_fit_review as capability_review
from scripts import run_product_v1_ranking_score_review as ranking_review
from scripts.run_demo_001_rankable_refill_scout import (
    _load_candidate_facts,
    _load_rows,
    scout,
)
from scripts.run_product_v1_assessment_materialization import (
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from src.job_lifecycle_health import OUTCOME_SEEN_ACTIVE
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "demo_001_rankable_refill_apply.json"
APPROVAL_TOKEN = "DEMO-001-RANKABLE-REFILL-001"
DEFAULT_TARGET_RANKABLE = 5
DEFAULT_CANDIDATE_CAP = 7


class DemoRankableRefillStop(RuntimeError):
    """Fail closed when the bounded refill cannot preserve Product authority."""


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
        raise DemoRankableRefillStop(message)


def _load_profile_sha256(conn: psycopg.Connection[Any]) -> str:
    profile = capability_review.load_profile(conn)
    return profile.payload_sha256


def _selected_candidates(
    rows: Sequence[Mapping[str, object]],
    *,
    candidate_cap: int,
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for row in rows:
        if row.get("live_outcome") != OUTCOME_SEEN_ACTIVE:
            continue
        if not bool(row.get("role_relevant")):
            continue
        matches = row.get("candidate_fact_matches")
        if not isinstance(matches, list) or not matches:
            continue
        selected.append(dict(row))
        if len(selected) >= candidate_cap:
            break
    return selected


def _capability_requests(
    selected: Sequence[Mapping[str, object]],
) -> tuple[capability_review.ReviewRequest, ...]:
    reviews: list[capability_review.ReviewRequest] = []
    for row in selected:
        if str(row.get("product_readiness_status") or "") == "rankable":
            continue
        matches = row.get("candidate_fact_matches")
        _require(isinstance(matches, list) and bool(matches), "candidate fact matches disappeared")
        fact_keys = tuple(
            sorted(
                {
                    str(item.get("fact_key") or "").strip()
                    for item in matches
                    if isinstance(item, Mapping) and str(item.get("fact_key") or "").strip()
                }
            )
        )
        tags = sorted(
            {
                str(tag)
                for item in matches
                if isinstance(item, Mapping)
                for tag in (item.get("matched_capability_tags") or [])
                if str(tag).strip()
            }
        )
        _require(bool(fact_keys), f"no approved Candidate Fact keys for {row.get('silver_job_id')}")
        _require(bool(tags), f"no exact vacancy capability tags for {row.get('silver_job_id')}")
        rationale = (
            "Approved Candidate Facts match exact live vacancy capability tags: "
            + ", ".join(tags[:10])
        )
        reviews.append(
            capability_review.ReviewRequest(
                silver_job_id=int(row["silver_job_id"]),
                decision="passed",
                rationale=rationale,
                candidate_fact_keys=fact_keys,
            )
        )
    return tuple(reviews)


def _hard_filter_rows(
    conn: psycopg.Connection[Any], silver_job_ids: Sequence[int]
) -> dict[int, dict[str, object]]:
    if not silver_job_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                readiness.silver_job_id,
                readiness.company_name,
                readiness.title,
                readiness.product_readiness_status,
                assessment.capability_fit_status,
                hard_filter.employment_status,
                hard_filter.language_status,
                hard_filter.weekly_hours_status,
                hard_filter.seniority_status,
                hard_filter.deterministic_hard_filter_status,
                hard_filter.hard_filter_status,
                hard_filter.hard_filter_reasons
            FROM gold_product_v1_job_readiness readiness
            JOIN job_product_assessments assessment
              ON assessment.silver_job_id = readiness.silver_job_id
            JOIN gold_product_v1_hard_filter_evaluation hard_filter
              ON hard_filter.silver_job_id = readiness.silver_job_id
            WHERE readiness.silver_job_id = ANY(%s)
            ORDER BY readiness.silver_job_id
            """,
            (list(silver_job_ids),),
        )
        return {int(row["silver_job_id"]): dict(row) for row in cur.fetchall()}


def _ranking_items(
    conn: psycopg.Connection[Any], silver_job_ids: Sequence[int]
) -> tuple[ranking_review.RankingPolicy, list[ranking_review.RankingPlanItem]]:
    policy = ranking_review.load_policy(conn)
    rows = ranking_review.load_current_rows(conn, silver_job_ids)
    items: list[ranking_review.RankingPlanItem] = []
    for silver_job_id in silver_job_ids:
        row = rows.get(silver_job_id)
        _require(row is not None, f"ranking row missing: {silver_job_id}")
        if str(row.get("hard_filter_status") or "") != "passed":
            continue
        source_url = str(row.get("source_url") or "")
        final_url, _page_title, detail_text = fetch_public_https_detail_text(source_url)
        items.append(
            ranking_review.build_plan_item(
                row=row,
                policy=policy,
                final_url=final_url,
                detail_text=detail_text,
            )
        )
    return policy, items


def _final_status(conn: psycopg.Connection[Any], silver_job_ids: Sequence[int]) -> dict[str, object]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                silver_job_id,
                company_name,
                title,
                product_readiness_status,
                hard_filter_status,
                overall_quality_score
            FROM gold_product_v1_job_readiness
            WHERE silver_job_id = ANY(%s)
            ORDER BY overall_quality_score DESC NULLS LAST, silver_job_id
            """,
            (list(silver_job_ids),),
        )
        cohort = [dict(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT count(*) AS count FROM gold_product_v1_job_readiness WHERE product_readiness_status = 'rankable'"
        )
        total_rankable = int(cur.fetchone()["count"])
        cur.execute(
            "SELECT count(*) AS count FROM gold_product_v1_top_jobs"
        )
        top_jobs = int(cur.fetchone()["count"])
    return {
        "total_rankable": total_rankable,
        "top_jobs": top_jobs,
        "cohort": cohort,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-rankable", type=int, default=DEFAULT_TARGET_RANKABLE)
    parser.add_argument("--candidate-cap", type=int, default=DEFAULT_CANDIDATE_CAP)
    parser.add_argument("--reviewed-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _require(1 <= args.target_rankable <= 25, "--target-rankable must be between 1 and 25")
    _require(1 <= args.candidate_cap <= 15, "--candidate-cap must be between 1 and 15")
    reviewed_by = str(args.reviewed_by or "").strip()
    _require(bool(reviewed_by), "--reviewed-by must not be blank")
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid DEMO-001 refill approval token")

    authorized = sorted(
        authorized_recurring_employer_origin_sources(JobIngestionRepository())
    )
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        facts = _load_candidate_facts(conn)
        rows = _load_rows(conn, authorized_sources=authorized, limit=max(30, args.candidate_cap * 4))
        profile_sha256 = _load_profile_sha256(conn)
        conn.rollback()

    live_rows = scout(rows=rows, facts=facts)
    selected = _selected_candidates(live_rows, candidate_cap=args.candidate_cap)
    _require(bool(selected), "no live Candidate-Fact-backed refill candidates")
    selected_ids = [int(row["silver_job_id"]) for row in selected]
    cap_requests = _capability_requests(selected)

    report: dict[str, object] = {
        "schema": "job_application_pipeline.demo_001_rankable_refill_apply.v1",
        "mode": "apply" if args.apply else "plan",
        "target_rankable": args.target_rankable,
        "candidate_cap": args.candidate_cap,
        "selected": [
            {
                "silver_job_id": int(row["silver_job_id"]),
                "company_name": row.get("company_name"),
                "title": row.get("title"),
                "source_name": row.get("source_name"),
                "live_final_url": row.get("live_final_url"),
                "current_readiness": row.get("product_readiness_status"),
                "matched_fact_count": row.get("matched_fact_count"),
                "matched_capability_tags": row.get("matched_capability_tags"),
                "candidate_fact_keys": sorted(
                    {
                        str(item.get("fact_key"))
                        for item in (row.get("candidate_fact_matches") or [])
                        if isinstance(item, Mapping) and item.get("fact_key")
                    }
                ),
            }
            for row in selected
        ],
        "capability_review_count": len(cap_requests),
        "hard_filter_operator_reviews_created": 0,
        "ranking_review_count": 0,
        "final": None,
        "boundaries": {
            "live_exact_detail_reads": True,
            "provider_or_llm_requests": 0,
            "candidate_fact_mutation": False,
            "capability_fit_requires_approved_fact_and_exact_job_tag_match": True,
            "hard_filter_operator_review_writes": False,
            "deterministic_hard_filter_override": False,
            "ranking_only_after_canonical_hard_filter_passed": True,
            "direct_rank_or_top5_writes": False,
            "application_or_submission_actions": False,
        },
    }

    if not args.apply:
        with capability_review.connect() as conn:
            capability_review.ensure_schema(conn)
            _profile, cap_plan = capability_review.build_plan(
                conn,
                expected_profile_sha256=profile_sha256,
                reviews=cap_requests,
            ) if cap_requests else (capability_review.load_profile(conn), ())
            conn.rollback()
        report["capability_plan"] = [_json_safe(item.__dict__) for item in cap_plan]
        report["note"] = (
            "Apply is required before canonical hard-filter truth can be re-read; "
            "ranking is intentionally not pre-authorized from hypothetical state."
        )
    else:
        if cap_requests:
            with capability_review.connect() as conn:
                capability_review.ensure_schema(conn)
                capability_review.build_plan(
                    conn,
                    expected_profile_sha256=profile_sha256,
                    reviews=cap_requests,
                )
                conn.rollback()
                changed, unchanged = capability_review.apply_reviews(
                    conn,
                    expected_profile_sha256=profile_sha256,
                    reviews=cap_requests,
                    reviewed_by=reviewed_by,
                )
            report["capability_changed"] = changed
            report["capability_unchanged"] = unchanged
        else:
            report["capability_changed"] = 0
            report["capability_unchanged"] = 0

        with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
            hard_filter = _hard_filter_rows(conn, selected_ids)
            conn.rollback()
        report["hard_filter_after_capability"] = [_json_safe(hard_filter[job_id]) for job_id in selected_ids if job_id in hard_filter]
        ranking_ids = [
            job_id
            for job_id in selected_ids
            if job_id in hard_filter
            and str(hard_filter[job_id].get("hard_filter_status") or "") == "passed"
            and str(hard_filter[job_id].get("product_readiness_status") or "") != "rankable"
        ]

        ranking_items: list[ranking_review.RankingPlanItem] = []
        if ranking_ids:
            with ranking_review.connect() as conn:
                ranking_review.ensure_schema(conn)
                _policy, ranking_items = _ranking_items(conn, ranking_ids)
                conn.rollback()
                changed = sum(
                    ranking_review.apply_item(conn, item=item, reviewed_by=reviewed_by)
                    for item in ranking_items
                )
                conn.commit()
            report["ranking_changed"] = changed
        else:
            report["ranking_changed"] = 0
        report["ranking_review_count"] = len(ranking_items)

        with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
            final = _final_status(conn, selected_ids)
            conn.rollback()
        report["final"] = _json_safe(final)
        report["target_met"] = int(final["total_rankable"]) >= args.target_rankable

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=== DEMO-001 RANKABLE REFILL ===")
    print(f"MODE={report['mode']}")
    print(f"SELECTED={len(selected)}")
    for row in report["selected"]:
        print(
            "SELECTED_JOB="
            f"{row['silver_job_id']}|facts={row['matched_fact_count']}|"
            f"{','.join(row['matched_capability_tags'])}|{row['company_name']}|{row['title']}"
        )
    if args.apply:
        print(f"CAPABILITY_CHANGED={report['capability_changed']}")
        for row in report["hard_filter_after_capability"]:
            print(
                "HARD_FILTER="
                f"{row['silver_job_id']}|capability={row['capability_fit_status']}|"
                f"deterministic={row['deterministic_hard_filter_status']}|"
                f"effective={row['hard_filter_status']}|"
                f"employment={row['employment_status']}|languages={row['language_status']}|"
                f"hours={row['weekly_hours_status']}|seniority={row['seniority_status']}"
            )
        print(f"RANKING_CHANGED={report['ranking_changed']}")
        final = report["final"]
        print(f"TOTAL_RANKABLE={final['total_rankable']}")
        print(f"TOP_JOBS={final['top_jobs']}")
        print(f"TARGET_MET={str(report['target_met']).lower()}")
        for row in final["cohort"]:
            print(
                "FINAL_JOB="
                f"{row['silver_job_id']}|{row['product_readiness_status']}|"
                f"hard_filter={row['hard_filter_status']}|score={row['overall_quality_score']}|"
                f"{row['company_name']}|{row['title']}"
            )
    else:
        print(f"CAPABILITY_PLAN={len(report.get('capability_plan') or [])}")
        print("HARD_FILTER_OPERATOR_REVIEWS=0")
        print("RANKING_PREAUTHORIZED=0")
    print("PROVIDER_REQUESTS=0")
    print("HARD_FILTER_OPERATOR_REVIEW_WRITES=0")
    print(f"artifact={args.output.resolve()}")
    print("DEMO_001_RANKABLE_REFILL=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
