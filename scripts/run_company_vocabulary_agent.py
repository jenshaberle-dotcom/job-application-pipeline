
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.search_intelligence.company_vocabulary import (
    CompanyVocabularyObservation,
    MarketEvidenceVocabularyInput,
    build_company_vocabulary_observations,
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


def load_market_evidence(conn: psycopg.Connection[Any], *, limit: int) -> list[MarketEvidenceVocabularyInput]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select
                normalized_company_key as company_key,
                company_name,
                title,
                source_name,
                observed_at::text as observed_at
            from market_evidence
            where title is not null
              and length(trim(title)) > 0
            order by observed_at desc
            limit %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    return [
        MarketEvidenceVocabularyInput(
            company_key=str(row["company_key"]),
            company_name=row["company_name"],
            title=str(row["title"]),
            source_name=str(row["source_name"]),
            observed_at=row["observed_at"],
        )
        for row in rows
    ]


def write_observations(
    conn: psycopg.Connection[Any],
    *,
    observations: list[CompanyVocabularyObservation],
    reviewed_by: str,
) -> int:
    count = 0
    with conn.cursor() as cur:
        for item in observations:
            cur.execute(
                """
                insert into company_vocabulary_observations (
                    company_key,
                    company_name,
                    observed_term,
                    source_name,
                    evidence_type,
                    observation_count,
                    first_seen_at,
                    last_seen_at,
                    evidence,
                    reviewed_by,
                    updated_at
                ) values (%s, %s, %s, %s, %s, %s, coalesce(%s::timestamptz, now()), coalesce(%s::timestamptz, now()), %s::jsonb, %s, now())
                on conflict (company_key, observed_term, source_name, evidence_type)
                do update set
                    company_name = excluded.company_name,
                    observation_count = excluded.observation_count,
                    first_seen_at = least(company_vocabulary_observations.first_seen_at, excluded.first_seen_at),
                    last_seen_at = greatest(company_vocabulary_observations.last_seen_at, excluded.last_seen_at),
                    evidence = excluded.evidence,
                    reviewed_by = excluded.reviewed_by,
                    updated_at = now()
                """,
                (
                    item.company_key,
                    item.company_name,
                    item.observed_term,
                    item.source_name,
                    item.evidence_type,
                    item.observation_count,
                    item.first_seen_at,
                    item.last_seen_at,
                    json.dumps(asdict(item), ensure_ascii=False),
                    reviewed_by,
                ),
            )
            count += 1
    conn.commit()
    return count


def render_preview(observations: list[CompanyVocabularyObservation], *, write_mode: bool) -> str:
    lines = ["Company Vocabulary Preview"]
    by_company: dict[str, list[CompanyVocabularyObservation]] = {}
    for item in observations:
        by_company.setdefault(item.company_key, []).append(item)

    lines.append(f"company_count: {len(by_company)}")
    lines.append(f"vocabulary_observation_count: {len(observations)}")
    lines.append("---")
    for company_key, items in list(by_company.items())[:10]:
        company_name = next((item.company_name for item in items if item.company_name), company_key)
        top_terms = ", ".join(
            f"{item.observed_term} ({item.observation_count})" for item in sorted(items, key=lambda x: (-x.observation_count, x.observed_term))[:8]
        )
        lines.append(f"company: {company_name} [{company_key}]")
        lines.append(f"terms: {top_terms or '-'}")
        lines.append("---")
    lines.append(f"write_mode: {str(write_mode).lower()}")
    if not write_mode:
        lines.append("NEXT: rerun with --write after reviewing observed company vocabulary.")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.dsn()) as conn:
        rows = load_market_evidence(conn, limit=args.limit)
        observations = build_company_vocabulary_observations(rows)
        print(render_preview(observations, write_mode=args.write))
        if args.write:
            count = write_observations(conn, observations=observations, reviewed_by=args.reviewed_by)
            print(f"company_vocabulary_observation_upsert_count: {count}")
            print("boundary: no search-profile mutation, no source activation, no Bronze write, no scheduler change")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build company vocabulary observations from existing market evidence.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum market evidence rows to inspect.")
    parser.add_argument("--write", action="store_true", help="Persist observed company vocabulary.")
    parser.add_argument("--reviewed-by", default="agent", help="Reviewer/agent label for persisted observations.")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
