"""Create one non-recurring generic-origin demo execution profile.

This does not grant recurring ingestion or scheduler authority. The profile is
usable only through an explicit exact-profile ingestion command.
"""
from __future__ import annotations

import argparse

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

APPROVAL_TOKEN = "DEMO-GENERIC-ORIGIN-PROFILE-001"
PROFILE_PREFIX = "demo_generic_origin__"
SEARCH_TERM = "*"


def prepare_profile(conn, company_key: str) -> dict[str, object]:
    key = company_key.strip().casefold()
    if not key:
        raise ValueError("company key is required")
    source_name = f"generic_origin:{key}"
    profile_name = f"{PROFILE_PREFIX}{key}"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, company_name, candidate_url
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (key,),
        )
        candidate = cur.fetchone()
        if candidate is None:
            raise ValueError(f"no Employer-Origin candidate found for {key}")
        candidate_url = str(candidate["candidate_url"] or "").strip()
        if not candidate_url.startswith("https://"):
            raise ValueError(f"{key} has no materialized HTTPS origin URL")

        cur.execute(
            """
            INSERT INTO search_profiles (
                profile_name, source_name, search_term, search_location,
                search_radius_km, offer_type, page_size, is_active,
                recurring_ingestion_enabled
            )
            VALUES (%s, %s, NULL, 'Hannover', 50, 1, 1, TRUE, FALSE)
            ON CONFLICT (profile_name)
            DO UPDATE SET
                source_name = EXCLUDED.source_name,
                search_term = NULL,
                search_location = EXCLUDED.search_location,
                search_radius_km = EXCLUDED.search_radius_km,
                offer_type = EXCLUDED.offer_type,
                page_size = EXCLUDED.page_size,
                is_active = TRUE,
                recurring_ingestion_enabled = FALSE
            RETURNING id, profile_name, source_name, is_active,
                      recurring_ingestion_enabled
            """,
            (profile_name, source_name),
        )
        profile = dict(cur.fetchone())
        cur.execute(
            "UPDATE search_terms SET is_active = FALSE WHERE search_profile_id = %s",
            (profile["id"],),
        )
        cur.execute(
            """
            INSERT INTO search_terms (search_profile_id, search_term, is_active)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (search_profile_id, search_term)
            DO UPDATE SET is_active = TRUE
            """,
            (profile["id"], SEARCH_TERM),
        )

    return {
        **profile,
        "candidate_id": int(candidate["id"]),
        "company_name": str(candidate["company_name"]),
        "candidate_url": candidate_url,
        "bounded_ingestion": f"python -m src.ingest_jobs --profile {profile_name}",
        "source_bounded_silver": (
            f"python -m src.run_silver_jobs --source {source_name} --limit 1"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    args = parser.parse_args()

    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("invalid demo profile approval token")

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        if args.apply:
            result = prepare_profile(conn, args.company_key)
            conn.commit()
        else:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, company_name, candidate_url
                    FROM employer_origin_source_candidates
                    WHERE company_key = %s
                    ORDER BY updated_at DESC NULLS LAST, id DESC
                    LIMIT 1
                    """,
                    (args.company_key.strip().casefold(),),
                )
                candidate = cur.fetchone()
            conn.rollback()
            if candidate is None or not str(candidate["candidate_url"] or "").startswith("https://"):
                raise SystemExit("demo source is not materialized yet")
            result = {
                "company_name": str(candidate["company_name"]),
                "candidate_url": str(candidate["candidate_url"]),
                "profile_name": f"{PROFILE_PREFIX}{args.company_key.strip().casefold()}",
            }

    print(f"DEMO_GENERIC_ORIGIN={args.company_key.strip().casefold()}")
    print(f"PROFILE={result['profile_name']}")
    print(f"ORIGIN={result['candidate_url']}")
    print(f"MODE={'apply' if args.apply else 'plan'}")
    print("RECURRING_INGESTION=false")
    if args.apply:
        print(f"NEXT={result['bounded_ingestion']}")
        print(f"THEN={result['source_bounded_silver']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
