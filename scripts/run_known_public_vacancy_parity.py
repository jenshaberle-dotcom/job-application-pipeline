#!/usr/bin/env python3
"""Read-only stage probe for one known public vacancy across normal product paths."""
from __future__ import annotations

import argparse
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.bundesagentur import BundesagenturConnector

BA_SOURCE = "bundesagentur_fuer_arbeit"
STAGES = (
    "ba_live",
    "ba_raw",
    "ba_silver",
    "ba_gold",
    "gold_canonical",
    "origin_candidate",
    "origin_active",
    "origin_raw",
    "origin_silver",
    "origin_gold",
)


def normalize(value: object) -> str:
    text = str(value or "").casefold()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def text_matches(expected: str, actual: object) -> bool:
    needle = normalize(expected)
    haystack = normalize(actual)
    return bool(needle and needle in haystack)


def _raw_title(raw_data: dict[str, Any]) -> object:
    job = raw_data.get("job") if isinstance(raw_data.get("job"), dict) else {}
    card = (
        raw_data.get("result_card")
        if isinstance(raw_data.get("result_card"), dict)
        else {}
    )
    return job.get("titel") or job.get("title") or card.get("title")


def _raw_company(raw_data: dict[str, Any]) -> object:
    job = raw_data.get("job") if isinstance(raw_data.get("job"), dict) else {}
    card = (
        raw_data.get("result_card")
        if isinstance(raw_data.get("result_card"), dict)
        else {}
    )
    return (
        job.get("arbeitgeber")
        or job.get("company_name")
        or job.get("company")
        or card.get("company_name")
    )


def _raw_matches(
    rows: list[dict[str, Any]],
    *,
    expected_company: str,
    expected_title: str,
    require_company: bool,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        raw_data = row.get("raw_data")
        if not isinstance(raw_data, dict):
            continue
        if not text_matches(expected_title, _raw_title(raw_data)):
            continue
        if require_company and not text_matches(expected_company, _raw_company(raw_data)):
            continue
        result.append(row)
    return result


def _flat_matches(
    rows: list[dict[str, Any]],
    *,
    expected_company: str,
    expected_title: str,
    require_company: bool,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if not text_matches(expected_title, row.get("title")):
            continue
        if require_company and not text_matches(expected_company, row.get("company_name")):
            continue
        result.append(row)
    return result


def _relation_exists(cur: Any, relation: str) -> bool:
    cur.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS relation_exists",
        (f"public.{relation}",),
    )
    row = cur.fetchone()
    return bool(row and row["relation_exists"])


def load_database_state(
    *,
    company_key: str,
    expected_company: str,
    expected_title: str,
    ba_profile_name: str,
    ba_external_job_id: str | None = None,
) -> tuple[dict[str, Any], SearchProfile]:
    origin_source = f"generic_origin:{company_key}"
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, profile_name, source_name, search_location,
                       search_radius_km, offer_type, page_size
                FROM search_profiles
                WHERE profile_name = %s
                  AND source_name = %s
                  AND is_active = TRUE
                """,
                (ba_profile_name, BA_SOURCE),
            )
            profile_row = cur.fetchone()
            if profile_row is None:
                raise RuntimeError("configured BA market-sensor profile is not active")

            cur.execute(
                """
                SELECT id, company_key, company_name, candidate_url, status, risk_level
                FROM employer_origin_source_candidates
                WHERE company_key = %s
                ORDER BY updated_at DESC NULLS LAST, id DESC
                """,
                (company_key,),
            )
            candidates = [dict(row) for row in cur.fetchall()]

            active: list[dict[str, Any]] = []
            if _relation_exists(cur, "generic_employer_origin_active_sources"):
                cur.execute(
                    """
                    SELECT candidate_id, company_key, source_name, origin_url, proof_state
                    FROM generic_employer_origin_active_sources
                    WHERE company_key = %s
                    """,
                    (company_key,),
                )
                active = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, source_name, source_url, external_job_id, raw_data
                FROM raw_jobs
                WHERE source_name IN (%s, %s)
                ORDER BY id DESC
                LIMIT 2000
                """,
                (BA_SOURCE, origin_source),
            )
            raw_rows = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, source_name, source_url, external_job_id, title, company_name
                FROM silver_jobs
                WHERE source_name IN (%s, %s)
                ORDER BY id DESC
                LIMIT 2000
                """,
                (BA_SOURCE, origin_source),
            )
            silver_rows = [dict(row) for row in cur.fetchall()]

            gold_rows: list[dict[str, Any]] = []
            if _relation_exists(cur, "gold_product_v1_job_readiness"):
                cur.execute(
                    """
                    SELECT silver_job_id, source_name, source_url, title, company_name,
                           product_readiness_status
                    FROM gold_product_v1_job_readiness
                    WHERE company_name ILIKE %s
                    ORDER BY silver_job_id DESC
                    LIMIT 2000
                    """,
                    (f"%{expected_company}%",),
                )
                gold_rows = [dict(row) for row in cur.fetchall()]

        conn.rollback()

    ba_raw_rows = [row for row in raw_rows if row["source_name"] == BA_SOURCE]
    if ba_external_job_id:
        ba_raw_rows = [
            row
            for row in ba_raw_rows
            if str(row.get("external_job_id") or "") == ba_external_job_id
        ]
    ba_raw = _raw_matches(
        ba_raw_rows,
        expected_company=expected_company,
        expected_title=expected_title,
        require_company=True,
    )
    origin_raw = _raw_matches(
        [row for row in raw_rows if row["source_name"] == origin_source],
        expected_company=expected_company,
        expected_title=expected_title,
        require_company=False,
    )
    ba_silver_rows = [
        row for row in silver_rows if row["source_name"] == BA_SOURCE
    ]
    if ba_external_job_id:
        ba_silver_rows = [
            row
            for row in ba_silver_rows
            if str(row.get("external_job_id") or "") == ba_external_job_id
        ]
    ba_silver = _flat_matches(
        ba_silver_rows,
        expected_company=expected_company,
        expected_title=expected_title,
        require_company=True,
    )
    origin_silver = _flat_matches(
        [row for row in silver_rows if row["source_name"] == origin_source],
        expected_company=expected_company,
        expected_title=expected_title,
        require_company=False,
    )
    ba_gold = _flat_matches(
        [row for row in gold_rows if row["source_name"] == BA_SOURCE],
        expected_company=expected_company,
        expected_title=expected_title,
        require_company=True,
    )
    origin_gold = _flat_matches(
        [row for row in gold_rows if row["source_name"] == origin_source],
        expected_company=expected_company,
        expected_title=expected_title,
        require_company=False,
    )
    gold_canonical = _flat_matches(
        gold_rows,
        expected_company=expected_company,
        expected_title=expected_title,
        require_company=True,
    )

    profile = SearchProfile(
        id=int(profile_row["id"]),
        profile_name=str(profile_row["profile_name"]),
        source_name=str(profile_row["source_name"]),
        search_location=(
            str(profile_row["search_location"])
            if profile_row["search_location"] is not None
            else None
        ),
        search_radius_km=(
            int(profile_row["search_radius_km"])
            if profile_row["search_radius_km"] is not None
            else None
        ),
        offer_type=(
            int(profile_row["offer_type"])
            if profile_row["offer_type"] is not None
            else None
        ),
        page_size=int(profile_row["page_size"]),
    )

    return {
        "origin_candidate": candidates,
        "origin_active": active,
        "ba_raw": ba_raw,
        "origin_raw": origin_raw,
        "ba_silver": ba_silver,
        "origin_silver": origin_silver,
        "ba_gold": ba_gold,
        "gold_canonical": gold_canonical,
        "origin_gold": origin_gold,
    }, profile


def ba_matches(
    records: list[Any],
    *,
    expected_company: str,
    expected_title: str,
) -> list[Any]:
    result = []
    for record in records:
        job = record.raw_data.get("job")
        if not isinstance(job, dict):
            continue
        if not text_matches(expected_title, job.get("titel")):
            continue
        if not text_matches(expected_company, job.get("arbeitgeber")):
            continue
        result.append(record)
    return result


def _print_stage(name: str, rows: list[Any]) -> None:
    print(f"PIPELINE_STAGE={name}|present={str(bool(rows)).lower()}|count={len(rows)}")
    if rows:
        first = rows[0]
        if isinstance(first, dict):
            print(
                f"PIPELINE_STAGE_FIRST={name}|"
                f"id={first.get('id') or first.get('silver_job_id') or first.get('candidate_id') or '-'}|"
                f"source={first.get('source_name') or '-'}|"
                f"title={first.get('title') or '-'}|"
                f"url={first.get('source_url') or first.get('candidate_url') or first.get('origin_url') or '-'}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--expected-company", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--ba-profile-name", required=True)
    parser.add_argument("--ba-search-term", required=True)
    parser.add_argument("--ba-external-job-id")
    parser.add_argument("--live-ba", action="store_true")
    parser.add_argument("--require-stage", action="append", choices=STAGES, default=[])
    args = parser.parse_args()

    state, ba_profile = load_database_state(
        company_key=args.company_key,
        expected_company=args.expected_company,
        expected_title=args.expected_title,
        ba_profile_name=args.ba_profile_name,
        ba_external_job_id=args.ba_external_job_id,
    )

    live_matches: list[Any] = []
    request_url = None
    if args.live_ba:
        records, request_url = BundesagenturConnector().fetch_jobs(
            ba_profile,
            SearchTerm(args.ba_search_term),
        )
        live_matches = ba_matches(
            records,
            expected_company=args.expected_company,
            expected_title=args.expected_title,
        )

    stages: dict[str, list[Any]] = {
        "ba_live": live_matches,
        **state,
    }
    for name in STAGES:
        _print_stage(name, stages.get(name, []))

    if args.ba_external_job_id:
        print(f"BA_EXPECTED_EXTERNAL_JOB_ID={args.ba_external_job_id}")
    if request_url:
        print(f"BA_LIVE_REQUEST={request_url}")
    print("DATABASE_WRITES=0")

    missing = [name for name in args.require_stage if not stages.get(name)]
    if missing:
        print("PIPELINE_PROBE=BLOCKED")
        print("PIPELINE_PROBE_MISSING=" + ",".join(missing))
        return 3

    print("PIPELINE_PROBE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
