from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.trial_application import (
    TRIAL_APPROVAL_TOKEN,
    StrategyRecommendationForTrial,
    build_trial_application_plans,
)


class DatabaseConfig:
    @classmethod
    def dsn(cls) -> str:
        return (
            f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
            f"port={os.environ.get('POSTGRES_PORT', '5432')} "
            f"dbname={os.environ['POSTGRES_DB']} "
            f"user={os.environ['POSTGRES_USER']} "
            f"password={os.environ['POSTGRES_PASSWORD']}"
        )


def load_trial_recommendations(conn: psycopg.Connection[Any], *, limit: int) -> list[StrategyRecommendationForTrial]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                id,
                candidate_id,
                company_key,
                source_name_candidate,
                source_family_candidate,
                suggested_term,
                recommendation_type,
                recommendation_status,
                autonomy_level,
                guardrail_decision,
                confidence_score,
                sample_size,
                false_negative_risk_level,
                guardrail_summary,
                reason
            from search_strategy_recommendations
            where recommendation_type = 'ADD_TRIAL_TERM'
              and recommendation_status in ('pending_review', 'auto_eligible')
            order by
                case recommendation_status
                    when 'auto_eligible' then 1
                    else 2
                end,
                confidence_score desc,
                sample_size desc,
                updated_at desc
            limit %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    return [
        StrategyRecommendationForTrial(
            recommendation_id=int(row["id"]),
            candidate_id=row["candidate_id"],
            company_key=str(row["company_key"]),
            source_name_candidate=row["source_name_candidate"],
            source_family_candidate=row["source_family_candidate"],
            suggested_term=str(row["suggested_term"]),
            recommendation_type=str(row["recommendation_type"]),
            recommendation_status=str(row["recommendation_status"]),
            autonomy_level=str(row["autonomy_level"]),
            guardrail_decision=str(row["guardrail_decision"]),
            confidence_score=Decimal(str(row["confidence_score"])),
            sample_size=int(row["sample_size"] or 0),
            false_negative_risk_level=row["false_negative_risk_level"],
            guardrail_summary=dict(row["guardrail_summary"] or {}),
            reason=str(row["reason"]),
        )
        for row in rows
    ]


def write_trial_terms(
    conn: psycopg.Connection[Any],
    *,
    approval_token: str | None,
    allow_auto_eligible: bool,
    applied_by: str,
    limit: int,
) -> int:
    plans = build_trial_application_plans(
        load_trial_recommendations(conn, limit=limit),
        approval_token=approval_token,
        allow_auto_eligible=allow_auto_eligible,
    )
    count = 0
    with conn.cursor() as cur:
        for item in plans:
            if not item.apply_allowed:
                continue

            cur.execute(
                """
                insert into search_strategy_trial_terms (
                    recommendation_id,
                    candidate_id,
                    company_key,
                    source_name_candidate,
                    source_family_candidate,
                    suggested_term,
                    trial_status,
                    trial_scope,
                    autonomy_level,
                    guardrail_decision,
                    trial_expires_at,
                    max_result_volume,
                    max_noise_rate,
                    applied_by,
                    evidence,
                    updated_at
                )
                values (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s::jsonb, now()
                )
                on conflict (company_key, COALESCE(source_family_candidate, ''), suggested_term)
                where trial_status = 'active'
                do update set
                    recommendation_id = excluded.recommendation_id,
                    candidate_id = excluded.candidate_id,
                    source_name_candidate = excluded.source_name_candidate,
                    autonomy_level = excluded.autonomy_level,
                    guardrail_decision = excluded.guardrail_decision,
                    trial_expires_at = excluded.trial_expires_at,
                    max_result_volume = excluded.max_result_volume,
                    max_noise_rate = excluded.max_noise_rate,
                    applied_by = excluded.applied_by,
                    evidence = excluded.evidence,
                    updated_at = now()
                """,
                (
                    item.recommendation_id,
                    item.candidate_id,
                    item.company_key,
                    item.source_name_candidate,
                    item.source_family_candidate,
                    item.suggested_term,
                    item.trial_status,
                    item.trial_scope,
                    item.autonomy_level,
                    item.guardrail_decision,
                    item.trial_expires_at,
                    item.max_result_volume,
                    item.max_noise_rate,
                    applied_by,
                    json.dumps(
                        {
                            "boundary": {
                                "permanent_search_profile_mutation": False,
                                "source_activation": False,
                                "bronze_write": False,
                                "scheduler_change": False,
                            },
                            "reason": item.reason,
                        }
                    ),
                ),
            )
            count += 1
    conn.commit()
    return count


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        recommendations = load_trial_recommendations(conn, limit=args.limit)
        plans = build_trial_application_plans(
            recommendations,
            approval_token=args.approval_token,
            allow_auto_eligible=args.allow_auto_eligible,
        )

        print("Controlled Trial Search-Term Preview")
        print(f"recommendation_count: {len(recommendations)}")
        print(f"trial_plan_count: {len(plans)}")
        for item in plans:
            print("---")
            print(f"company: {item.company_key}")
            print(f"term: {item.suggested_term}")
            print(f"status: {item.trial_status}")
            print(f"apply_allowed: {item.apply_allowed}")
            print(f"approval_required: {item.approval_required}")
            print(f"guardrail: {item.guardrail_decision}")
            print(f"expires_at: {item.trial_expires_at.isoformat()}")
            print(f"max_result_volume: {item.max_result_volume}")
            print(f"max_noise_rate: {item.max_noise_rate}")
            print(f"reason: {item.reason}")

        if not args.write:
            print("---")
            print("write_mode: false")
            print(f"NEXT: rerun with --write --approval-token {TRIAL_APPROVAL_TOKEN} after reviewing the trial plan, or use --allow-auto-eligible for auto-eligible items.")
            return 0

        count = write_trial_terms(
            conn,
            approval_token=args.approval_token,
            allow_auto_eligible=args.allow_auto_eligible,
            applied_by=args.reviewed_by,
            limit=args.limit,
        )
        print("---")
        print("write_mode: true")
        print(f"trial_term_upsert_count: {count}")
        print("boundary: no permanent search-profile mutation, no source activation, no Bronze write, no scheduler change")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply approved or auto-eligible search-strategy recommendations as bounded trial terms."
    )
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--allow-auto-eligible", action="store_true")
    parser.add_argument("--reviewed-by", default="agent")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
