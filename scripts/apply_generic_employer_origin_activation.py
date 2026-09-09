from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config import get_database_config

SENSOR_SOURCE_NAMES = ("bundesagentur_fuer_arbeit", "stepstone")
GENERIC_SOURCE_PREFIX = "generic_origin:"
PROFILE_PREFIX = "generic_origin__"
NEUTRAL_TRIGGER_TERM = "jobs"
ACTIVE_SOURCE_RELATION = "generic_employer_origin_active_sources"
GENERIC_AUTHORITY = "generic_evidence_driven_layer_model"


def _load_product(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    authority = payload.get("authority") or {}
    if authority.get("sole_connector_truth") != GENERIC_AUTHORITY:
        raise ValueError("activation input is not the canonical generic layer product")
    if authority.get("source_validity_gate") != "proof=PASS":
        raise ValueError("activation input does not use proof=PASS as source validity gate")
    return payload


def _proof_layer(item: dict[str, Any]) -> dict[str, Any] | None:
    layers = item.get("layers") or []
    return next(
        (
            layer
            for layer in layers
            if isinstance(layer, dict) and layer.get("layer") == "proof"
        ),
        None,
    )


def _proof_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        proof = _proof_layer(item)
        if proof and proof.get("state") == "pass":
            rows.append(item)
    return rows


def _relation_exists(conn: psycopg.Connection[Any], relation_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{relation_name}",))
        row = cur.fetchone()
    return bool(row and row[0])


def _validate_db_candidates(conn: psycopg.Connection[Any], rows: list[dict[str, Any]]) -> None:
    expected = {int(row["candidate_id"]): str(row["company_key"]) for row in rows}
    if not expected:
        raise ValueError("generic product contains zero proof-passed candidates")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, company_key, candidate_url
            FROM employer_origin_source_candidates
            WHERE id = ANY(%s)
            """,
            (list(expected),),
        )
        actual = {int(row["id"]): row for row in cur.fetchall()}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        raise ValueError(f"proof cohort candidate IDs missing in DB: {missing}")
    for candidate_id, company_key in expected.items():
        row = actual[candidate_id]
        if str(row["company_key"]) != company_key:
            raise ValueError(
                f"candidate identity mismatch for {candidate_id}: {row['company_key']} != {company_key}"
            )
        if not str(row.get("candidate_url") or "").strip():
            raise ValueError(f"proof-passed candidate {company_key} has no persisted origin URL")


def _legacy_active_profile_count(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)
            FROM search_profiles
            WHERE is_active = TRUE
              AND source_name <> ALL(%s)
              AND source_name NOT LIKE %s
            """,
            (list(SENSOR_SOURCE_NAMES), f"{GENERIC_SOURCE_PREFIX}%"),
        )
        return int(cur.fetchone()[0])


def _current_generic_profile_count(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)
            FROM search_profiles
            WHERE is_active = TRUE
              AND source_name LIKE %s
            """,
            (f"{GENERIC_SOURCE_PREFIX}%",),
        )
        return int(cur.fetchone()[0])


def _current_projection_count(conn: psycopg.Connection[Any]) -> int | None:
    if not _relation_exists(conn, ACTIVE_SOURCE_RELATION):
        return None
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {ACTIVE_SOURCE_RELATION}")
        return int(cur.fetchone()[0])


def _sync_active_source_projection(
    cur: psycopg.Cursor[Any],
    rows: list[dict[str, Any]],
) -> None:
    proof_ids = [int(row["candidate_id"]) for row in rows]
    cur.execute(
        f"DELETE FROM {ACTIVE_SOURCE_RELATION} WHERE NOT (candidate_id = ANY(%s))",
        (proof_ids,),
    )
    for row in rows:
        candidate_id = int(row["candidate_id"])
        company_key = str(row["company_key"])
        source_name = f"{GENERIC_SOURCE_PREFIX}{company_key}"
        proof = _proof_layer(row)
        if proof is None or proof.get("state") != "pass":
            raise ValueError(f"missing proof=PASS evidence for {company_key}")
        cur.execute(
            f"""
            INSERT INTO {ACTIVE_SOURCE_RELATION} (
                candidate_id,
                company_key,
                source_name,
                authority,
                proof_state,
                proof_evidence
            )
            VALUES (%s, %s, %s, %s, 'pass', %s)
            ON CONFLICT (candidate_id)
            DO UPDATE SET
                company_key = EXCLUDED.company_key,
                source_name = EXCLUDED.source_name,
                authority = EXCLUDED.authority,
                proof_state = EXCLUDED.proof_state,
                proof_evidence = EXCLUDED.proof_evidence,
                updated_at = NOW()
            """,
            (
                candidate_id,
                company_key,
                source_name,
                GENERIC_AUTHORITY,
                Jsonb(proof),
            ),
        )


def apply_activation(
    conn: psycopg.Connection[Any],
    rows: list[dict[str, Any]],
) -> None:
    proof_ids = [int(row["candidate_id"]) for row in rows]
    if not _relation_exists(conn, ACTIVE_SOURCE_RELATION):
        raise RuntimeError(
            "generic active-source projection is missing; apply migration 107 first"
        )

    with conn.cursor() as cur:
        # The table is a materialized projection of the current generic proof cohort,
        # not an independent approval mechanism.
        _sync_active_source_projection(cur, rows)

        # Market sensors stay active; all legacy Employer-Origin execution profiles retire.
        cur.execute(
            """
            UPDATE search_profiles
            SET is_active = FALSE,
                recurring_ingestion_enabled = FALSE
            WHERE source_name <> ALL(%s)
              AND source_name NOT LIKE %s
            """,
            (list(SENSOR_SOURCE_NAMES), f"{GENERIC_SOURCE_PREFIX}%"),
        )

        # A candidate that previously carried controlled-active state from a legacy
        # admission path is no longer active unless the current generic proof passed.
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET status = 'candidate',
                updated_at = NOW()
            WHERE status = 'active_controlled'
              AND NOT (id = ANY(%s))
            """,
            (proof_ids,),
        )

        for row in rows:
            candidate_id = int(row["candidate_id"])
            company_key = str(row["company_key"])
            source_name = f"{GENERIC_SOURCE_PREFIX}{company_key}"
            profile_name = f"{PROFILE_PREFIX}{company_key}"

            cur.execute(
                """
                UPDATE employer_origin_source_candidates
                SET status = 'active_controlled',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (candidate_id,),
            )

            cur.execute(
                """
                INSERT INTO search_profiles (
                    profile_name,
                    source_name,
                    search_term,
                    search_location,
                    search_radius_km,
                    offer_type,
                    page_size,
                    is_active,
                    recurring_ingestion_enabled
                )
                VALUES (%s, %s, NULL, 'Hannover', 50, 1, 1, TRUE, TRUE)
                ON CONFLICT (profile_name)
                DO UPDATE SET
                    source_name = EXCLUDED.source_name,
                    search_term = NULL,
                    search_location = EXCLUDED.search_location,
                    search_radius_km = EXCLUDED.search_radius_km,
                    offer_type = EXCLUDED.offer_type,
                    page_size = EXCLUDED.page_size,
                    is_active = TRUE,
                    recurring_ingestion_enabled = TRUE
                """,
                (profile_name, source_name),
            )

            cur.execute(
                "SELECT id FROM search_profiles WHERE profile_name = %s",
                (profile_name,),
            )
            profile_id = int(cur.fetchone()[0])
            cur.execute(
                "UPDATE search_terms SET is_active = FALSE WHERE search_profile_id = %s",
                (profile_id,),
            )
            cur.execute(
                """
                INSERT INTO search_terms (search_profile_id, search_term, is_active)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (search_profile_id, search_term)
                DO UPDATE SET is_active = TRUE
                """,
                (profile_id, NEUTRAL_TRIGGER_TERM),
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply generic Employer-Origin proof PASS as the sole source activation truth."
    )
    parser.add_argument("--proof-json", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    payload = _load_product(args.proof_json)
    rows = _proof_rows(payload)

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        _validate_db_candidates(conn, rows)
        legacy_before = _legacy_active_profile_count(conn)
        generic_before = _current_generic_profile_count(conn)
        projection_before = _current_projection_count(conn)

        print(f"PROOF_PASS_SOURCES={len(rows)}")
        print(f"LEGACY_ACTIVE_EMPLOYER_PROFILES_BEFORE={legacy_before}")
        print(f"GENERIC_ACTIVE_PROFILES_BEFORE={generic_before}")
        print(
            "GENERIC_ACTIVE_SOURCE_PROJECTION_BEFORE="
            + ("MISSING" if projection_before is None else str(projection_before))
        )
        for row in rows:
            print(
                "ACTIVATION_SOURCE="
                f"generic_origin:{row['company_key']}|candidate_id={row['candidate_id']}"
            )

        if not args.apply:
            conn.rollback()
            print("GENERIC_ORIGIN_ACTIVATION=PLAN_ONLY")
            print("DATABASE_WRITES=0")
            return 0

        apply_activation(conn, rows)
        conn.commit()

        legacy_after = _legacy_active_profile_count(conn)
        generic_after = _current_generic_profile_count(conn)
        projection_after = _current_projection_count(conn)
        if legacy_after != 0:
            raise RuntimeError(f"legacy Employer-Origin profiles remain active: {legacy_after}")
        if generic_after != len(rows):
            raise RuntimeError(
                f"generic active profile count mismatch: {generic_after} != {len(rows)}"
            )
        if projection_after != len(rows):
            raise RuntimeError(
                "generic active-source projection count mismatch: "
                f"{projection_after} != {len(rows)}"
            )

        print(f"LEGACY_ACTIVE_EMPLOYER_PROFILES_AFTER={legacy_after}")
        print(f"GENERIC_ACTIVE_PROFILES_AFTER={generic_after}")
        print(f"GENERIC_ACTIVE_SOURCE_PROJECTION_AFTER={projection_after}")
        print("GENERIC_ORIGIN_ACTIVATION=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
