"""Collect DB-backed observation seed pool with source-type boundaries."""

from __future__ import annotations

import argparse
import json
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.origin_seed_pool import (
    SEED_POOL_BOUNDARY,
    ObservationSeed,
    classify_seed_row,
    deduplicate_seeds,
    generate_company_url_candidates,
    observation_role_counts,
    seed_type_counts,
)


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _table_columns(conn: psycopg.Connection[Any], table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        return {str(row["column_name"]) for row in cur.fetchall()}


def _table_exists(conn: psycopg.Connection[Any], table_name: str) -> bool:
    return bool(_table_columns(conn, table_name))


def _fetch_rows(conn: psycopg.Connection[Any], query: str, params: tuple[object, ...] = ()) -> list[Mapping[str, object]]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        return list(cur.fetchall())


def collect_seed_rows(conn: psycopg.Connection[Any], *, limit_per_source: int) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []

    if _table_exists(conn, "employer_origin_source_candidates"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT
                    'employer_origin_source_candidates' AS seed_source_table,
                    company_key,
                    company_name,
                    source_name_candidate AS source_name,
                    source_family_candidate,
                    candidate_url AS seed_url,
                    status
                FROM employer_origin_source_candidates
                ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    if _table_exists(conn, "employer_origin_job_detail_evidence"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT
                    'employer_origin_job_detail_evidence' AS seed_source_table,
                    company_key,
                    company_key AS company_name,
                    company_key AS source_family_candidate,
                    COALESCE(final_url, source_url) AS seed_url,
                    relevance_decision AS status
                FROM employer_origin_job_detail_evidence
                WHERE COALESCE(final_url, source_url) IS NOT NULL
                ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    if _table_exists(conn, "candidate_expansion_review_items"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT
                    'candidate_expansion_review_items' AS seed_source_table,
                    company_key,
                    company_name,
                    source_name,
                    NULL::text AS seed_url,
                    distinct_search_term_count
                FROM candidate_expansion_review_items
                ORDER BY distinct_search_term_count DESC NULLS LAST, company_name
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    if _table_exists(conn, "candidate_promotion_review_items"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT
                    'candidate_promotion_review_items' AS seed_source_table,
                    company_key,
                    company_name,
                    source_name,
                    source_family_candidate,
                    candidate_url AS seed_url,
                    source_decision AS status
                FROM candidate_promotion_review_items
                ORDER BY created_candidate_id DESC NULLS LAST, company_name
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    if _table_exists(conn, "aggregator_novelty_items"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT
                    'aggregator_novelty_items' AS seed_source_table,
                    company_key,
                    company_name,
                    source_name,
                    evidence_url AS seed_url,
                    search_term
                FROM aggregator_novelty_items
                ORDER BY company_name
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    if _table_exists(conn, "market_evidence"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT
                    'market_evidence' AS seed_source_table,
                    normalized_company_key AS company_key,
                    company_name,
                    source_name,
                    evidence_url AS seed_url,
                    search_term
                FROM market_evidence
                ORDER BY source_seen_at DESC NULLS LAST, company_name
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    if _table_exists(conn, "raw_jobs"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT DISTINCT
                    'raw_jobs' AS seed_source_table,
                    NULL::text AS company_key,
                    NULL::text AS company_name,
                    source_name,
                    source_url AS seed_url
                FROM raw_jobs
                WHERE source_url IS NOT NULL
                  AND btrim(source_url) <> ''
                ORDER BY source_name, source_url
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    if _table_exists(conn, "silver_jobs") and "company_name" in _table_columns(conn, "silver_jobs"):
        rows.extend(
            _fetch_rows(
                conn,
                """
                SELECT
                    'silver_jobs' AS seed_source_table,
                    normalized_company_name AS company_key,
                    company_name,
                    source_name,
                    source_url AS seed_url,
                    COUNT(*) AS silver_job_count
                FROM silver_jobs
                WHERE company_name IS NOT NULL
                  AND btrim(company_name) <> ''
                GROUP BY normalized_company_name, company_name, source_name, source_url
                ORDER BY COUNT(*) DESC, company_name
                LIMIT %s
                """,
                (limit_per_source,),
            )
        )

    return rows


def collect_seeds(conn: psycopg.Connection[Any], *, limit_per_source: int) -> list[ObservationSeed]:
    return deduplicate_seeds(classify_seed_row(row) for row in collect_seed_rows(conn, limit_per_source=limit_per_source))


def load_promoted_url_patterns(conn: psycopg.Connection[Any]) -> tuple[str, ...]:
    if not _table_exists(conn, "origin_pattern_promotion_decisions"):
        return ()
    columns = _table_columns(conn, "origin_pattern_promotion_decisions")
    category_filter = ""
    if "usage_scope" in columns:
        category_filter = "AND usage_scope IN ('detail_url_discovery', 'listing_url_discovery')"
    rows = _fetch_rows(
        conn,
        f"""
        SELECT DISTINCT pattern_value
        FROM origin_pattern_promotion_decisions
        WHERE promotion_status = 'promoted'
          AND usable_by_url_finder = true
          {category_filter}
        ORDER BY pattern_value
        """,
    )
    return tuple(str(row["pattern_value"]) for row in rows if row["pattern_value"])


def persist_seed_snapshot(conn: psycopg.Connection[Any], *, seeds: Iterable[ObservationSeed], run_label: str, created_by: str) -> int:
    count = 0
    with conn.cursor() as cur:
        for seed in seeds:
            cur.execute(
                """
                INSERT INTO origin_observation_seed_pool_snapshots (
                    run_label,
                    seed_key,
                    seed_type,
                    seed_source_table,
                    observation_role,
                    company_key,
                    company_name,
                    source_name,
                    source_family,
                    seed_url,
                    url_allowed_for_observation,
                    priority_score,
                    prior_reason,
                    evidence,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    run_label,
                    seed.seed_key,
                    seed.seed_type,
                    seed.seed_source_table,
                    seed.observation_role,
                    seed.company_key,
                    seed.company_name,
                    seed.source_name,
                    seed.source_family,
                    seed.seed_url,
                    seed.url_allowed_for_observation,
                    seed.priority_score,
                    seed.prior_reason,
                    json.dumps(seed.evidence or {}, sort_keys=True),
                    created_by,
                ),
            )
            count += 1
    conn.commit()
    return count


def print_seed_summary(seeds: list[ObservationSeed]) -> None:
    print(f"seed_count: {len(seeds)}")
    print(f"seed_type_counts: {json.dumps(seed_type_counts(seeds), sort_keys=True)}")
    print(f"observation_role_counts: {json.dumps(observation_role_counts(seeds), sort_keys=True)}")
    allowed = sum(1 for seed in seeds if seed.url_allowed_for_observation)
    print(f"url_allowed_for_observation_count: {allowed}")
    for seed in seeds[:25]:
        print(
            "seed: "
            f"type={seed.seed_type} | role={seed.observation_role} | priority={seed.priority_score} | "
            f"company={seed.company_name or seed.company_key or '-'} | url={seed.seed_url or '-'} | "
            f"source={seed.seed_source_table} | reason={seed.prior_reason}"
        )


def run(args: argparse.Namespace) -> int:
    with connect() as conn:
        seeds = collect_seeds(conn, limit_per_source=args.limit_per_source)
        print_seed_summary(seeds)
        promoted_patterns = load_promoted_url_patterns(conn)
        company_seeds = [seed for seed in seeds if seed.seed_type == "company_name_only_seed"]
        for seed in company_seeds[: args.company_url_preview_limit]:
            candidates = generate_company_url_candidates(seed.company_key or "", seed.company_name, promoted_path_patterns=promoted_patterns)
            print(
                "url_discovery_preview: "
                f"company={seed.company_name or seed.company_key} | candidate_count={len(candidates)} | "
                f"sample={list(candidates[:4])}"
            )
        if not args.dry_run:
            count = persist_seed_snapshot(conn, seeds=seeds, run_label=args.run_label, created_by=args.reviewed_by)
            print(f"persisted_seed_count: {count}")
        else:
            print("dry_run: True")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect DB-backed observation seeds with source-type boundaries.")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--run-label", default="a2e_seed_pool")
    parser.add_argument("--limit-per-source", type=int, default=100)
    parser.add_argument("--company-url-preview-limit", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
