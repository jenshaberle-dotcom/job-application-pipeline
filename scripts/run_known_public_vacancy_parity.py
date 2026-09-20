#!/usr/bin/env python3
"""Read-only acceptance for one known public vacancy across normal source paths.

The check proves that an already-activated generic Employer-Origin source has
persisted the target vacancy into Silver and that the configured Bundesagentur
sensor can independently observe the same public vacancy with its normal
connector/profile contract. It never writes to the database.
"""
from __future__ import annotations

import argparse
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.bundesagentur import BundesagenturConnector


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
    return bool(needle and (needle in haystack or haystack in needle))


def load_acceptance_state(
    *,
    company_key: str,
    expected_title: str,
    ba_profile_name: str,
    ba_search_term: str,
) -> tuple[dict[str, Any], SearchProfile]:
    source_name = f"generic_origin:{company_key}"
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT candidate_id, company_key, source_name, origin_url, proof_state
                FROM generic_employer_origin_active_sources
                WHERE company_key = %s
                """,
                (company_key,),
            )
            active = cur.fetchone()
            if active is None:
                raise RuntimeError("required generic Employer-Origin source is not active")

            cur.execute(
                """
                SELECT id, profile_name, source_name, search_location,
                       search_radius_km, offer_type, page_size
                FROM search_profiles
                WHERE profile_name = %s
                  AND source_name = 'bundesagentur_fuer_arbeit'
                  AND is_active = TRUE
                """,
                (ba_profile_name,),
            )
            profile_row = cur.fetchone()
            if profile_row is None:
                raise RuntimeError("configured BA market-sensor profile is not active")

            cur.execute(
                """
                SELECT 1
                FROM search_terms
                WHERE search_profile_id = %s
                  AND search_term = %s
                  AND is_active = TRUE
                """,
                (int(profile_row["id"]), ba_search_term),
            )
            if cur.fetchone() is None:
                raise RuntimeError("required BA market-sensor search term is not active")

            cur.execute(
                """
                SELECT id, title, company_name, source_url
                FROM silver_jobs
                WHERE source_name = %s
                ORDER BY id DESC
                """,
                (source_name,),
            )
            silver = [
                dict(row)
                for row in cur.fetchall()
                if text_matches(expected_title, row["title"])
            ]

        conn.rollback()

    state = {
        "active_source": dict(active),
        "silver_matches": silver,
    }
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
    return state, profile


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--expected-company", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--ba-profile-name", required=True)
    parser.add_argument("--ba-search-term", required=True)
    args = parser.parse_args()

    state, ba_profile = load_acceptance_state(
        company_key=args.company_key,
        expected_title=args.expected_title,
        ba_profile_name=args.ba_profile_name,
        ba_search_term=args.ba_search_term,
    )
    if not state["silver_matches"]:
        raise SystemExit("MARKET_PARITY_ORIGIN_SILVER_TARGET_MISSING")

    records, request_url = BundesagenturConnector().fetch_jobs(
        ba_profile,
        SearchTerm(args.ba_search_term),
    )
    matches = ba_matches(
        records,
        expected_company=args.expected_company,
        expected_title=args.expected_title,
    )
    if not matches:
        raise SystemExit("MARKET_PARITY_BA_TARGET_MISSING")

    active = state["active_source"]
    first_silver = state["silver_matches"][0]
    first_ba = matches[0].raw_data["job"]
    print("MARKET_PARITY_ACCEPTANCE=PASS")
    print(f"ACTIVE_SOURCE={active['source_name']}|proof={active['proof_state']}")
    print(f"ACTIVE_ORIGIN={active['origin_url']}")
    print(
        "ORIGIN_SILVER_TARGET="
        f"{first_silver['id']}|{first_silver['title']}|{first_silver['source_url']}"
    )
    print(
        "BA_SENSOR_TARGET="
        f"{first_ba.get('arbeitgeber')}|{first_ba.get('titel')}|"
        f"{matches[0].source_url}"
    )
    print(f"BA_REQUEST={request_url}")
    print("DATABASE_WRITES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
