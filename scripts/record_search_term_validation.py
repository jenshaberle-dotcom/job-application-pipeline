from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

VALID_OUTCOMES = {
    'pending',
    'tested_no_result',
    'tested_found_noise',
    'tested_found_relevant',
    'accepted',
    'rejected',
}


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


def load_candidate_and_suggestion(conn: psycopg.Connection[Any], company_key: str, suggested_term: str) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                c.id as candidate_id,
                c.company_key,
                c.source_name_candidate,
                c.source_family_candidate,
                s.id as suggestion_id,
                coalesce(s.suggested_term, %s) as suggested_term
            from employer_origin_source_candidates c
            left join search_term_suggestions s
              on s.candidate_id = c.id
             and lower(s.suggested_term) = lower(%s)
            where c.company_key = %s
            order by s.updated_at desc nulls last
            limit 1
            """,
            (suggested_term, suggested_term, company_key),
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit(f"No employer-origin candidate found for company_key={company_key!r}")
    return dict(row)


def record_validation(conn: psycopg.Connection[Any], args: argparse.Namespace) -> int:
    row = load_candidate_and_suggestion(conn, args.company_key, args.suggested_term)
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into search_term_validation_runs (
                suggestion_id,
                candidate_id,
                company_key,
                source_name_candidate,
                source_family_candidate,
                suggested_term,
                outcome,
                result_count,
                relevant_count,
                noise_count,
                evidence_url,
                notes,
                validated_by,
                evidence
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            returning id
            """,
            (
                row.get('suggestion_id'),
                row['candidate_id'],
                row['company_key'],
                row.get('source_name_candidate'),
                row.get('source_family_candidate'),
                row['suggested_term'],
                args.outcome,
                args.result_count,
                args.relevant_count,
                args.noise_count,
                args.evidence_url,
                args.notes,
                args.validated_by,
                json.dumps({'boundary': 'review_state_only_no_profile_mutation'}, ensure_ascii=False),
            ),
        )
        validation_id = cur.fetchone()[0]

        if row.get('suggestion_id') is not None and args.outcome in {'accepted', 'rejected', 'tested_found_relevant', 'tested_no_result', 'tested_found_noise'}:
            status = 'accepted' if args.outcome in {'accepted', 'tested_found_relevant'} else 'rejected' if args.outcome == 'rejected' else 'tested'
            cur.execute(
                """
                update search_term_suggestions
                set status = %s, updated_at = now()
                where id = %s
                """,
                (status, row['suggestion_id']),
            )
    return int(validation_id)


def run(args: argparse.Namespace) -> int:
    if args.outcome not in VALID_OUTCOMES:
        raise SystemExit(f"Invalid outcome {args.outcome!r}; expected one of {sorted(VALID_OUTCOMES)}")
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        validation_id = record_validation(conn, args)
        conn.commit()
    print('search_term_validation_written: true')
    print(f'search_term_validation_id: {validation_id}')
    print('boundary: no search-profile mutation, no source activation, no Bronze write')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Record a reviewed search-term validation outcome.')
    parser.add_argument('--company-key', required=True)
    parser.add_argument('--suggested-term', required=True)
    parser.add_argument('--outcome', required=True, choices=sorted(VALID_OUTCOMES))
    parser.add_argument('--result-count', type=int, default=0)
    parser.add_argument('--relevant-count', type=int, default=0)
    parser.add_argument('--noise-count', type=int, default=0)
    parser.add_argument('--evidence-url')
    parser.add_argument('--notes')
    parser.add_argument('--validated-by', default='agent')
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == '__main__':
    main()
