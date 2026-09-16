"""Historical read-only audit for the superseded DEMO-001 Top-5 cutoff review.

The 2026-09-03 demo path lowered the Product V1 minimum quality threshold from
70 to 60 only to obtain five recommendations. F4B Operator Gate 001 reaffirmed
PD-051=70/100 on 2026-09-16 and PD-050 forbids quota filling. The historical
comparison remains useful provenance, but this command may no longer mutate the
ranking policy.
"""
from __future__ import annotations

import argparse
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

HISTORICAL_THRESHOLD = Decimal("60.00")
AUTHORITATIVE_THRESHOLD = Decimal("70.00")


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
    # Retained only so stale operator commands fail with a precise governance
    # message instead of an argparse error.
    parser.add_argument("--approved-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.apply:
        raise Top5PolicyReviewStop(
            "PD-051_REAFFIRMED_70: DEMO-001 60-cutoff mutation is retired; "
            "Top 5 is at_most_no_fill"
        )

    with connect() as conn:
        policy, rankable = _snapshot(conn)
        conn.rollback()

    _require(str(policy["status"]) == "approved", "ranking policy is not approved")
    _require(int(policy["top_job_limit"]) == 5, "Top-job limit must remain 5")
    _require(
        str(policy["top_job_semantics"]) == "at_most_no_fill",
        "unexpected Top-job semantics",
    )
    current_threshold = Decimal(str(policy["minimum_quality_score"]))
    scores = [
        Decimal(str(row["overall_quality_score"]))
        for row in rankable
        if row["overall_quality_score"] is not None
    ]
    eligible_at_70 = [score for score in scores if score >= AUTHORITATIVE_THRESHOLD]
    eligible_at_60 = [score for score in scores if score >= HISTORICAL_THRESHOLD]

    print("=== PRODUCT V1 HISTORICAL TOP-5 POLICY AUDIT ===")
    print("MODE=read_only")
    print(f"CURRENT_THRESHOLD={current_threshold}")
    print(f"AUTHORITATIVE_PD051_THRESHOLD={AUTHORITATIVE_THRESHOLD}")
    print(f"HISTORICAL_DEMO001_THRESHOLD={HISTORICAL_THRESHOLD}")
    print(f"TOTAL_RANKABLE={len(rankable)}")
    print(f"ELIGIBLE_AT_70={len(eligible_at_70)}")
    print(f"ELIGIBLE_AT_60={len(eligible_at_60)}")
    print("DATABASE_WRITES=0")
    print("PRODUCT_V1_TOP5_POLICY_REVIEW=HISTORICAL_AUDIT_ONLY")
    print("PROVIDER_REQUESTS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
