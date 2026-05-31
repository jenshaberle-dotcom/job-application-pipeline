"""Record a manual market-evidence sighting.

Use this for evidence such as a LinkedIn alert that proves a company has a relevant
role while employer-origin discovery remains unresolved. This writes market evidence
only; it does not create jobs, activate sources or change schedulers.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg

from src.normalization.company_keys import normalize_company_key


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


def record_market_evidence(conn: psycopg.Connection[Any], args: argparse.Namespace) -> int | None:
    normalized = normalize_company_key(args.company_name)
    evidence = {
        "recorded_by": args.recorded_by,
        "input_mode": "manual_market_evidence",
        "boundary": {
            "job_ingestion": False,
            "bronze_write": False,
            "source_activation": False,
            "scheduler_change": False,
        },
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into market_evidence (
                evidence_source,
                evidence_kind,
                source_name,
                normalized_company_key,
                company_name,
                title,
                evidence_url,
                search_profile_name,
                search_term,
                source_seen_at,
                evidence
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s::jsonb)
            on conflict do nothing
            returning id
            """,
            (
                args.evidence_source,
                "manual_aggregator_sighting",
                args.source_name,
                normalized,
                args.company_name,
                args.title,
                args.evidence_url,
                args.search_profile_name,
                args.search_term,
                args.seen_at,
                json.dumps(evidence, ensure_ascii=False),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return None if row is None else int(row[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record manual market evidence without ingesting a job.")
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-name", default="linkedin")
    parser.add_argument("--evidence-source", default="manual")
    parser.add_argument("--evidence-url")
    parser.add_argument("--search-profile-name")
    parser.add_argument("--search-term")
    parser.add_argument("--seen-at")
    parser.add_argument("--recorded-by", default="jens")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        evidence_id = record_market_evidence(conn, args)
    if evidence_id is None:
        print("market_evidence_written: false")
        print("reason: duplicate observation already exists")
    else:
        print("market_evidence_written: true")
        print(f"market_evidence_id: {evidence_id}")
        print("boundary: no Bronze write, no source activation, no scheduler change")


if __name__ == "__main__":
    main()
