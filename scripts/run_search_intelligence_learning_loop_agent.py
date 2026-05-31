from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.search_term_validation import SearchTermValidationRun, build_confidence


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


def load_validation_runs(conn: psycopg.Connection[Any]) -> list[SearchTermValidationRun]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                suggestion_id,
                candidate_id,
                company_key,
                source_name_candidate,
                source_family_candidate,
                suggested_term,
                validation_scope,
                outcome,
                result_count,
                relevant_count,
                noise_count,
                evidence_url,
                notes,
                validated_by
            from search_term_validation_runs
            order by created_at desc
            """
        )
        rows = cur.fetchall()
    return [
        SearchTermValidationRun(
            suggestion_id=row['suggestion_id'],
            candidate_id=int(row['candidate_id']),
            company_key=str(row['company_key']),
            source_name_candidate=row['source_name_candidate'],
            source_family_candidate=row['source_family_candidate'],
            suggested_term=str(row['suggested_term']),
            validation_scope=str(row['validation_scope']),
            outcome=str(row['outcome']),
            result_count=int(row['result_count'] or 0),
            relevant_count=int(row['relevant_count'] or 0),
            noise_count=int(row['noise_count'] or 0),
            evidence_url=row['evidence_url'],
            notes=row['notes'],
            validated_by=str(row['validated_by']),
        )
        for row in rows
    ]


def write_confidence_snapshots(conn: psycopg.Connection[Any], *, reviewed_by: str) -> int:
    confidences = build_confidence(load_validation_runs(conn))
    count = 0
    with conn.cursor() as cur:
        for item in confidences:
            cur.execute(
                """
                insert into search_term_confidence_snapshots (
                    suggested_term,
                    source_family_candidate,
                    validation_scope,
                    sample_size,
                    success_count,
                    failure_count,
                    noise_count,
                    confidence_score,
                    confidence_level,
                    evidence,
                    reviewed_by
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    item.suggested_term,
                    item.source_family_candidate,
                    item.validation_scope,
                    item.sample_size,
                    item.success_count,
                    item.failure_count,
                    item.noise_count,
                    item.confidence_score,
                    item.confidence_level,
                    json.dumps(asdict(item), default=str, ensure_ascii=False),
                    reviewed_by,
                ),
            )
            count += 1
    return count


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        validations = load_validation_runs(conn)
        confidences = build_confidence(validations)
        print('Search Intelligence Learning Loop Preview')
        print(f'validation_run_count: {len(validations)}')
        print(f'confidence_item_count: {len(confidences)}')
        for item in confidences[: args.limit]:
            print('---')
            print(f'term: {item.suggested_term}')
            print(f'source_family: {item.source_family_candidate or "-"}')
            print(f'confidence_score: {item.confidence_score}')
            print(f'confidence_level: {item.confidence_level}')
            print(f'sample_size: {item.sample_size}')
            print(f'success_count: {item.success_count}')
            print(f'failure_count: {item.failure_count}')
            print(f'noise_count: {item.noise_count}')
        if args.write_snapshot:
            count = write_confidence_snapshots(conn, reviewed_by=args.reviewed_by)
            conn.commit()
            print('---')
            print('snapshot_written: true')
            print(f'search_term_confidence_snapshot_count: {count}')
        else:
            print('---')
            print('snapshot_written: false')
            print('NEXT: rerun with --write-snapshot after reviewing the preview.')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Build confidence snapshots from reviewed search-term validation outcomes.')
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--write-snapshot', action='store_true')
    parser.add_argument('--reviewed-by', default='agent')
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == '__main__':
    main()
