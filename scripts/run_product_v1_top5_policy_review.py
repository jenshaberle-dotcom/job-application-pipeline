"""Version-bound operator review for the Product V1 Top-5 recommendation cutoff.

This command changes no job assessment, score, hard-filter result, lifecycle state,
source authority or application state. It may only lower the approved recommendation
cutoff from 70 to 60 after current Product truth proves that at least five already-
rankable jobs meet 60 and that fewer than five meet the previous 70 threshold.
"""
from __future__ import annotations

import argparse
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

APPROVAL_TOKEN = "PRODUCT-V1-TOP5-POLICY-REVIEW-2026-09-03"
EXPECTED_OLD_THRESHOLD = Decimal("70.00")
NEW_THRESHOLD = Decimal("60.00")
NEW_POLICY_VERSION = "product-v1-2026-09-03"


class Top5PolicyReviewStop(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Top5PolicyReviewStop(message)


def connect():
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _snapshot(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT policy_key, status, top_job_limit, top_job_semantics,
                   minimum_quality_score, policy_version, approved_by
            FROM product_v1_ranking_policy
            WHERE policy_key = 'default'
            """
        )
        policy = cur.fetchone()
        _require(policy is not None, "default ranking policy missing")
        cur.execute(
            """
            SELECT silver_job_id, company_name, title, overall_quality_score
            FROM gold_product_v1_job_readiness
            WHERE product_readiness_status = 'rankable'
            ORDER BY overall_quality_score DESC NULLS LAST, silver_job_id
            """
        )
        rankable = list(cur.fetchall())
    return policy, rankable


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    approved_by = str(args.approved_by or "").strip()
    _require(bool(approved_by), "approved_by must not be blank")
    if args.apply:
        _require(args.approval_token == APPROVAL_TOKEN, "invalid Top-5 policy approval token")

    with connect() as conn:
        policy, rankable = _snapshot(conn)
        conn.rollback()

        _require(str(policy["status"]) == "approved", "ranking policy is not approved")
        _require(int(policy["top_job_limit"]) == 5, "Top-job limit must remain 5")
        _require(str(policy["top_job_semantics"]) == "at_most_no_fill", "unexpected Top-job semantics")
        current_threshold = Decimal(str(policy["minimum_quality_score"]))
        _require(
            current_threshold in {EXPECTED_OLD_THRESHOLD, NEW_THRESHOLD},
            f"unexpected current minimum-quality cutoff: {current_threshold}",
        )

        scores = [Decimal(str(row["overall_quality_score"])) for row in rankable if row["overall_quality_score"] is not None]
        old_eligible = [score for score in scores if score >= EXPECTED_OLD_THRESHOLD]
        new_eligible = [score for score in scores if score >= NEW_THRESHOLD]
        below_new = [score for score in scores if score < NEW_THRESHOLD]

        _require(len(rankable) >= 5, "fewer than five rankable jobs exist")
        _require(len(new_eligible) >= 5, "fewer than five rankable jobs meet the reviewed 60 cutoff")
        _require(len(old_eligible) < 5, "existing 70 cutoff already provides five recommendations")
        _require(bool(below_new), "no lower-scoring rankable comparator exists")

        print("=== PRODUCT V1 TOP-5 POLICY REVIEW ===")
        print(f"MODE={'apply' if args.apply else 'plan'}")
        print(f"CURRENT_THRESHOLD={current_threshold}")
        print(f"REVIEWED_THRESHOLD={NEW_THRESHOLD}")
        print(f"TOTAL_RANKABLE={len(rankable)}")
        print(f"ELIGIBLE_AT_70={len(old_eligible)}")
        print(f"ELIGIBLE_AT_60={len(new_eligible)}")
        print(f"BEST_BELOW_60={max(below_new)}")
        for row in rankable[:8]:
            print(
                "RANKABLE="
                f"{row['silver_job_id']}|score={row['overall_quality_score']}|"
                f"{row['company_name']}|{row['title']}"
            )

        if args.apply and current_threshold != NEW_THRESHOLD:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("PRODUCT-V1-RANKING-POLICY:default",))
                cur.execute(
                    """
                    UPDATE product_v1_ranking_policy
                    SET minimum_quality_score = %s,
                        policy_version = %s,
                        approved_by = %s,
                        approved_at = now(),
                        updated_at = now()
                    WHERE policy_key = 'default'
                      AND status = 'approved'
                      AND minimum_quality_score = %s
                    """,
                    (NEW_THRESHOLD, NEW_POLICY_VERSION, approved_by, EXPECTED_OLD_THRESHOLD),
                )
                _require(cur.rowcount == 1, "ranking policy changed concurrently")
            conn.commit()
        else:
            conn.rollback()

    with connect() as conn:
        policy_after, _rankable_after = _snapshot(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT silver_job_id, company_name, title, overall_quality_score, product_rank
                FROM gold_product_v1_top_jobs
                ORDER BY product_rank
                """
            )
            top_jobs = list(cur.fetchall())
        conn.rollback()

    print(f"FINAL_THRESHOLD={policy_after['minimum_quality_score']}")
    print(f"POLICY_VERSION={policy_after['policy_version']}")
    print(f"TOP_JOBS={len(top_jobs)}")
    for row in top_jobs:
        print(
            "TOP_JOB="
            f"{row['product_rank']}|{row['silver_job_id']}|score={row['overall_quality_score']}|"
            f"{row['company_name']}|{row['title']}"
        )
    if args.apply:
        _require(Decimal(str(policy_after["minimum_quality_score"])) == NEW_THRESHOLD, "cutoff not applied")
        _require(len(top_jobs) == 5, "Top-5 view did not expose exactly five jobs")
        print("PRODUCT_V1_TOP5_POLICY_REVIEW=PASS")
    else:
        print("DATABASE_WRITES=0")
        print("PRODUCT_V1_TOP5_POLICY_REVIEW=PLAN_COMPLETE")
    print("JOB_SCORE_WRITES=0")
    print("HARD_FILTER_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
