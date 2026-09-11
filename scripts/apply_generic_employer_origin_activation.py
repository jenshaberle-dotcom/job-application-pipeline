from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.config import get_database_config

SENSOR_SOURCE_NAMES = ("bundesagentur_fuer_arbeit", "stepstone")
GENERIC_SOURCE_PREFIX = "generic_origin:"
PROFILE_PREFIX = "generic_origin__"
NEUTRAL_TRIGGER_TERM = "*"
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


def _layer(item: dict[str, Any], layer_name: str) -> dict[str, Any] | None:
    layers = item.get("layers") or []
    return next(
        (
            layer
            for layer in layers
            if isinstance(layer, dict) and layer.get("layer") == layer_name
        ),
        None,
    )


def _proof_layer(item: dict[str, Any]) -> dict[str, Any] | None:
    return _layer(item, "proof")


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
        cur.execute(
            "SELECT to_regclass(%s) IS NOT NULL AS relation_exists",
            (f"public.{relation_name}",),
        )
        row = cur.fetchone()
    return bool(row and row["relation_exists"])


def _url_shape(value: str) -> dict[str, object]:
    parsed = urlparse(value)
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


def _shape_to_https_url(shape: object) -> str | None:
    if not isinstance(shape, dict):
        return None
    scheme = str(shape.get("scheme") or "").casefold()
    host = str(shape.get("host") or "").casefold().strip(".")
    path = str(shape.get("path") or "/")
    query_keys = shape.get("query_keys") or []
    if scheme != "https" or not host or query_keys:
        return None
    if not path.startswith("/"):
        path = "/" + path
    return f"https://{host}{path}"


def _proof_origin_shape(row: dict[str, Any]) -> object:
    origin = _layer(row, "origin")
    if origin is None or origin.get("state") != "pass":
        raise ValueError(f"missing origin=PASS evidence for {row.get('company_key')}")
    evidence = origin.get("evidence") or {}
    if not isinstance(evidence, dict):
        raise ValueError(f"invalid origin evidence for {row.get('company_key')}")
    source = str(evidence.get("source") or "")
    if source == "persisted_candidate_url":
        return evidence.get("candidate_url")
    if source == "provider_free_origin_discovery":
        return evidence.get("selected_url")
    raise ValueError(
        f"unsupported proof origin source for {row.get('company_key')}: {source or 'unknown'}"
    )


def _resolve_projection_origins(
    conn: psycopg.Connection[Any],
    rows: list[dict[str, Any]],
) -> dict[int, str]:
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

    origins: dict[int, str] = {}
    proof_by_id = {int(row["candidate_id"]): row for row in rows}
    for candidate_id, company_key in expected.items():
        db_row = actual[candidate_id]
        if str(db_row["company_key"]) != company_key:
            raise ValueError(
                f"candidate identity mismatch for {candidate_id}: {db_row['company_key']} != {company_key}"
            )

        proof_shape = _proof_origin_shape(proof_by_id[candidate_id])
        persisted = str(db_row.get("candidate_url") or "").strip()
        if persisted:
            parsed = urlparse(persisted)
            if parsed.scheme.casefold() != "https" or not parsed.hostname:
                raise ValueError(f"proof-passed candidate {company_key} has invalid persisted origin URL")
            if isinstance(proof_shape, dict) and _url_shape(persisted) != proof_shape:
                raise ValueError(
                    f"persisted origin no longer matches fresh proof for {company_key}"
                )
            origins[candidate_id] = persisted
            continue

        discovered = _shape_to_https_url(proof_shape)
        if discovered is None:
            raise ValueError(
                "fresh proof discovered an origin that cannot be exactly materialized "
                f"without persisted query values for {company_key}"
            )
        origins[candidate_id] = discovered

    return origins


def _legacy_active_profile_count(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) AS count
            FROM search_profiles
            WHERE is_active = TRUE
              AND source_name <> ALL(%s)
              AND source_name NOT LIKE %s
            """,
            (list(SENSOR_SOURCE_NAMES), f"{GENERIC_SOURCE_PREFIX}%"),
        )
        row = cur.fetchone()
    return int(row["count"])


def _current_generic_profile_count(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) AS count
            FROM search_profiles
            WHERE is_active = TRUE
              AND source_name LIKE %s
            """,
            (f"{GENERIC_SOURCE_PREFIX}%",),
        )
        row = cur.fetchone()
    return int(row["count"])


def _current_projection_count(conn: psycopg.Connection[Any]) -> int | None:
    if not _relation_exists(conn, ACTIVE_SOURCE_RELATION):
        return None
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS count FROM {ACTIVE_SOURCE_RELATION}")
        row = cur.fetchone()
    return int(row["count"])


def _sync_active_source_projection(
    cur: psycopg.Cursor[Any],
    rows: list[dict[str, Any]],
    origin_urls: dict[int, str],
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
                origin_url,
                authority,
                proof_state,
                proof_evidence
            )
            VALUES (%s, %s, %s, %s, %s, 'pass', %s)
            ON CONFLICT (candidate_id)
            DO UPDATE SET
                company_key = EXCLUDED.company_key,
                source_name = EXCLUDED.source_name,
                origin_url = EXCLUDED.origin_url,
                authority = EXCLUDED.authority,
                proof_state = EXCLUDED.proof_state,
                proof_evidence = EXCLUDED.proof_evidence,
                updated_at = NOW()
            """,
            (
                candidate_id,
                company_key,
                source_name,
                origin_urls[candidate_id],
                GENERIC_AUTHORITY,
                Jsonb(proof),
            ),
        )


def apply_activation(
    conn: psycopg.Connection[Any],
    rows: list[dict[str, Any]],
    origin_urls: dict[int, str],
) -> None:
    proof_ids = [int(row["candidate_id"]) for row in rows]
    if not _relation_exists(conn, ACTIVE_SOURCE_RELATION):
        raise RuntimeError(
            "generic active-source projection is missing; apply migration 107 first"
        )

    with conn.cursor() as cur:
        # The table is a materialized projection of the current generic proof cohort,
        # not an independent approval mechanism.
        _sync_active_source_projection(cur, rows, origin_urls)

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

        # The generic execution surface is also a complete materialized projection.
        # Retire every prior generic profile before re-enabling exactly one canonical
        # profile per current proof-PASS source below. This removes stale aliases and
        # duplicate active profiles without changing proof authority.
        cur.execute(
            """
            UPDATE search_profiles
            SET is_active = FALSE,
                recurring_ingestion_enabled = FALSE
            WHERE source_name LIKE %s
            """,
            (f"{GENERIC_SOURCE_PREFIX}%",),
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
            profile_row = cur.fetchone()
            profile_id = int(profile_row["id"])
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
        origin_urls = _resolve_projection_origins(conn, rows)
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
            candidate_id = int(row["candidate_id"])
            print(
                "ACTIVATION_SOURCE="
                f"generic_origin:{row['company_key']}|candidate_id={candidate_id}|"
                f"origin_url={origin_urls[candidate_id]}"
            )

        if not args.apply:
            conn.rollback()
            print("GENERIC_ORIGIN_ACTIVATION=PLAN_ONLY")
            print("DATABASE_WRITES=0")
            return 0

        apply_activation(conn, rows, origin_urls)
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
