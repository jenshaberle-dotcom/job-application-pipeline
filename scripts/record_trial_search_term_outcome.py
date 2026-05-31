from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row


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


def find_trial_id(conn: psycopg.Connection[Any], *, company_key: str, suggested_term: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select id
            from search_strategy_trial_terms
            where company_key = %s
              and suggested_term = %s
              and trial_status = 'active'
            order by updated_at desc
            limit 1
            """,
            (company_key, suggested_term),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"No active trial term found for company_key={company_key!r}, term={suggested_term!r}")
    return int(row["id"])


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        trial_id = args.trial_id or find_trial_id(
            conn,
            company_key=args.company_key,
            suggested_term=args.suggested_term,
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into search_strategy_trial_outcomes (
                    trial_term_id,
                    outcome_status,
                    result_count,
                    relevant_count,
                    noise_count,
                    recorded_by,
                    notes,
                    evidence
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning id
                """,
                (
                    trial_id,
                    args.outcome_status,
                    args.result_count,
                    args.relevant_count,
                    args.noise_count,
                    args.recorded_by,
                    args.notes,
                    json.dumps(
                        {
                            "boundary": {
                                "trial_observation_only": True,
                                "permanent_search_profile_mutation": False,
                                "source_activation": False,
                                "bronze_write": False,
                            }
                        }
                    ),
                ),
            )
            outcome_id = cur.fetchone()[0]
        conn.commit()

    print("trial_outcome_written: true")
    print(f"trial_outcome_id: {outcome_id}")
    print("boundary: trial observation only, no permanent search-profile mutation, no source activation, no Bronze write")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record the observed outcome of a controlled trial search term.")
    parser.add_argument("--trial-id", type=int)
    parser.add_argument("--company-key", default="")
    parser.add_argument("--suggested-term", default="")
    parser.add_argument(
        "--outcome-status",
        required=True,
        choices=["pending", "no_result", "found_relevant", "found_noise", "rollback_recommended", "promotion_candidate"],
    )
    parser.add_argument("--result-count", type=int, default=0)
    parser.add_argument("--relevant-count", type=int, default=0)
    parser.add_argument("--noise-count", type=int, default=0)
    parser.add_argument("--recorded-by", default="agent")
    parser.add_argument("--notes")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.trial_id is None and (not args.company_key or not args.suggested_term):
        raise SystemExit("Provide --trial-id or both --company-key and --suggested-term.")
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
