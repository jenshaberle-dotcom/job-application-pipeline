from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.strategy_recommendation import StrategyRecommendationInput, build_strategy_recommendations


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


def load_recommendation_inputs(conn: psycopg.Connection[Any]) -> list[StrategyRecommendationInput]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            with latest_confidence as (
                select distinct on (suggested_term, coalesce(source_family_candidate, ''))
                    suggested_term,
                    source_family_candidate,
                    confidence_score,
                    confidence_level,
                    sample_size,
                    success_count,
                    failure_count,
                    noise_count,
                    created_at
                from search_term_confidence_snapshots
                order by suggested_term, coalesce(source_family_candidate, ''), created_at desc
            ), latest_risk as (
                select distinct on (company_key)
                    candidate_id,
                    company_key,
                    risk_level,
                    sighting_count,
                    created_at
                from false_negative_risk_snapshots
                order by company_key, created_at desc
            )
            select
                lr.candidate_id,
                coalesce(lr.company_key, lc.source_family_candidate, lc.suggested_term) as company_key,
                c.source_name_candidate,
                coalesce(c.source_family_candidate, lc.source_family_candidate) as source_family_candidate,
                lc.suggested_term,
                lc.confidence_score,
                lc.confidence_level,
                lc.sample_size,
                lc.success_count,
                lc.failure_count,
                lc.noise_count,
                lr.risk_level as false_negative_risk_level,
                coalesce(lr.sighting_count, 0) as false_negative_sighting_count
            from latest_confidence lc
            left join employer_origin_source_candidates c
                on c.source_family_candidate = lc.source_family_candidate
                or c.company_key = lc.source_family_candidate
            left join latest_risk lr
                on lr.company_key = c.company_key
                or lr.company_key = lc.source_family_candidate
            order by lc.created_at desc
            """
        )
        rows = cur.fetchall()
    return [
        StrategyRecommendationInput(
            candidate_id=row['candidate_id'],
            company_key=str(row['company_key']),
            source_name_candidate=row['source_name_candidate'],
            source_family_candidate=row['source_family_candidate'],
            suggested_term=str(row['suggested_term']),
            confidence_score=Decimal(str(row['confidence_score'])),
            confidence_level=str(row['confidence_level']),
            sample_size=int(row['sample_size'] or 0),
            success_count=int(row['success_count'] or 0),
            failure_count=int(row['failure_count'] or 0),
            noise_count=int(row['noise_count'] or 0),
            false_negative_risk_level=row['false_negative_risk_level'],
            false_negative_sighting_count=int(row['false_negative_sighting_count'] or 0),
        )
        for row in rows
    ]


def write_recommendations(conn: psycopg.Connection[Any], *, reviewed_by: str) -> int:
    recommendations = build_strategy_recommendations(load_recommendation_inputs(conn))
    count = 0
    with conn.cursor() as cur:
        for item in recommendations:
            cur.execute(
                """
                insert into search_strategy_recommendations (
                    candidate_id,
                    company_key,
                    source_name_candidate,
                    source_family_candidate,
                    suggested_term,
                    recommendation_type,
                    recommendation_status,
                    autonomy_level,
                    confidence_score,
                    confidence_level,
                    sample_size,
                    success_count,
                    failure_count,
                    noise_count,
                    false_negative_risk_level,
                    false_negative_sighting_count,
                    guardrail_decision,
                    guardrail_summary,
                    reason,
                    reviewed_by,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, now())
                on conflict (company_key, source_family_candidate, suggested_term, recommendation_type)
                do update set
                    candidate_id = excluded.candidate_id,
                    source_name_candidate = excluded.source_name_candidate,
                    recommendation_status = excluded.recommendation_status,
                    autonomy_level = excluded.autonomy_level,
                    confidence_score = excluded.confidence_score,
                    confidence_level = excluded.confidence_level,
                    sample_size = excluded.sample_size,
                    success_count = excluded.success_count,
                    failure_count = excluded.failure_count,
                    noise_count = excluded.noise_count,
                    false_negative_risk_level = excluded.false_negative_risk_level,
                    false_negative_sighting_count = excluded.false_negative_sighting_count,
                    guardrail_decision = excluded.guardrail_decision,
                    guardrail_summary = excluded.guardrail_summary,
                    reason = excluded.reason,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    item.candidate_id,
                    item.company_key,
                    item.source_name_candidate,
                    item.source_family_candidate,
                    item.suggested_term,
                    item.recommendation_type,
                    item.recommendation_status,
                    item.autonomy_level,
                    item.confidence_score,
                    item.confidence_level,
                    item.sample_size,
                    item.success_count,
                    item.failure_count,
                    item.noise_count,
                    item.false_negative_risk_level,
                    item.false_negative_sighting_count,
                    item.guardrail_decision,
                    json.dumps(item.guardrail_summary, ensure_ascii=False),
                    item.reason,
                    reviewed_by,
                ),
            )
            count += 1
    return count


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        recommendations = build_strategy_recommendations(load_recommendation_inputs(conn))
        print('Search Strategy Recommendation Preview')
        print(f'recommendation_count: {len(recommendations)}')
        for item in recommendations[: args.limit]:
            print('---')
            print(f'company: {item.company_key}')
            print(f'term: {item.suggested_term}')
            print(f'recommendation_type: {item.recommendation_type}')
            print(f'status: {item.recommendation_status}')
            print(f'autonomy_level: {item.autonomy_level}')
            print(f'guardrail_decision: {item.guardrail_decision}')
            print(f'confidence_score: {item.confidence_score}')
            print(f'sample_size: {item.sample_size}')
            print(f'false_negative_risk: {item.false_negative_risk_level or "-"}')
            print(f'reason: {item.reason}')
        if args.write:
            count = write_recommendations(conn, reviewed_by=args.reviewed_by)
            conn.commit()
            print('---')
            print('write_mode: true')
            print(f'search_strategy_recommendation_upsert_count: {count}')
        else:
            print('---')
            print('write_mode: false')
            print('NEXT: rerun with --write after reviewing recommendations.')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Generate guardrailed search-strategy recommendations from validated search-intelligence evidence.')
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--reviewed-by', default='agent')
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == '__main__':
    main()
