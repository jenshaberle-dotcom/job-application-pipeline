"""Run the F4A-R2 read-only requirement plan against operator-visible current truth.

F4A-R2 exists to repair the evidence shown in the Control Center. Therefore its
cohort must be the same normal review scope the operator actually sees, not the
larger lifecycle-current storage projection. The Control Center already applies
bounded presentation-only geography filtering and exact Origin identity dedup to
that scope; neither operation grants ranking or application authority.

This diagnostic deliberately does *not* treat source activation/admission as a
second gate for reading public job-side requirement evidence. A row first has to
be in canonical Product truth and then survive the exact same presentation
projection used for normal operator review. The diagnostic still fetches only the
exact persisted HTTPS detail URL, rejects cross-origin redirects, never reads
Candidate Facts, never writes the database, and grants no ranking, Top-5,
capability-fit or application authority.

The core Product payload is loaded with source-connector overview disabled. That
keeps this evidence diagnostic independent of optional connector implementation
dependencies; the Sources panel is irrelevant to review-scope selection.

For source migrations, the diagnostic reports exact title+company matches already
present in Silver under another source projection and the DB-backed state of the
corresponding canonical ``generic_origin:<company>`` source. These are evidence
only: no vacancy identity, URL, lifecycle state, source activation, or Product
authority is mutated.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import psycopg

from scripts import product_v1_control_center_base as control_center_base
from scripts import run_f4a_r2_current_requirement_plan as plan
from scripts.product_v1_job_presentation_runtime import (
    enrich_product_payload_for_operator,
)


CURRENT_PRODUCT_AUTHORITY = "operator_review_scope_current_origin"
_CANONICAL_LOAD_CURRENT_ROWS = plan._load_current_rows


def _review_scope_ids(payload: Mapping[str, object]) -> set[int]:
    result: set[int] = set()
    rows = payload.get("job_readiness")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = row.get("silver_job_id")
        try:
            silver_job_id = int(value) if value is not None else 0
        except (TypeError, ValueError):
            continue
        if silver_job_id > 0:
            result.add(silver_job_id)
    return result


def _operator_review_payload() -> dict[str, object]:
    """Load normal review truth without constructing the connector registry."""

    core = control_center_base.load_product_v1_payload(
        include_source_connector_overview=False
    )
    return enrich_product_payload_for_operator(core)


def _operator_review_rows(conn: psycopg.Connection[Any]) -> list[dict[str, object]]:
    """Return assessment rows for exactly the normal Control Center review scope."""

    review_ids = _review_scope_ids(_operator_review_payload())
    if not review_ids:
        return []
    return [
        row
        for row in _CANONICAL_LOAD_CURRENT_ROWS(conn)
        if int(row.get("current_silver_job_id") or 0) in review_ids
    ]


def _current_product_sources(conn: psycopg.Connection[Any]) -> dict[str, str]:
    """Return sources represented by the operator-visible current review scope."""

    rows = _operator_review_rows(conn)
    return {
        source_name: CURRENT_PRODUCT_AUTHORITY
        for row in rows
        if (source_name := str(row.get("source_name") or "").strip())
    }


def _print_exact_relocation_candidates(conn: psycopg.Connection[Any]) -> None:
    """Report exact cross-source title+company matches without creating identity."""

    rows = _operator_review_rows(conn)
    legacy = [
        row
        for row in rows
        if not str(row.get("source_name") or "").startswith("generic_origin:")
    ]
    if not legacy:
        print("F4A_R2_EXACT_RELOCATION_CANDIDATES=0")
        return

    candidate_count = 0
    with conn.cursor() as cur:
        for row in legacy:
            title = str(row.get("title") or "").strip()
            company = str(row.get("company_name") or "").strip()
            if not title or not company:
                continue
            cur.execute(
                """
                SELECT
                    silver.id AS silver_job_id,
                    silver.source_name,
                    silver.source_url,
                    silver.title,
                    silver.company_name,
                    lifecycle.lifecycle_status,
                    identity.is_representative,
                    identity.canonical_vacancy_key
                FROM silver_jobs silver
                LEFT JOIN gold_job_lifecycle_health lifecycle
                  ON lifecycle.silver_job_id = silver.id
                LEFT JOIN gold_vacancy_identity identity
                  ON identity.silver_job_id = silver.id
                WHERE silver.id <> %s
                  AND lower(btrim(silver.title)) = lower(btrim(%s))
                  AND lower(btrim(coalesce(silver.company_name, '')))
                      = lower(btrim(%s))
                  AND silver.source_name LIKE 'generic_origin:%%'
                ORDER BY
                    CASE lifecycle.lifecycle_status
                        WHEN 'active_confirmed' THEN 0
                        WHEN 'unverifiable' THEN 1
                        WHEN 'stale_needs_refresh' THEN 2
                        WHEN 'inactive_confirmed' THEN 3
                        ELSE 4
                    END,
                    silver.id DESC
                """,
                (
                    int(row.get("current_silver_job_id") or 0),
                    title,
                    company,
                ),
            )
            for candidate in cur.fetchall():
                candidate_count += 1
                print(
                    "F4A_R2_EXACT_RELOCATION_CANDIDATE="
                    + json.dumps(
                        {
                            "from_silver_job_id": int(
                                row.get("current_silver_job_id") or 0
                            ),
                            "from_source_name": row.get("source_name"),
                            "from_source_url": row.get("source_url"),
                            "candidate": dict(candidate),
                        },
                        default=str,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
    print(f"F4A_R2_EXACT_RELOCATION_CANDIDATES={candidate_count}")


def _print_generic_source_state(conn: psycopg.Connection[Any]) -> None:
    """Expose whether canonical generic FI admission has ever reached ingestion."""

    source_name = "generic_origin:finanz_informatik"
    state: dict[str, object] = {"source_name": source_name}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT to_regclass('public.generic_employer_origin_active_sources') AS relation
            """
        )
        relation = cur.fetchone()
        active_relation = relation is not None and relation["relation"] is not None
        state["active_source_table_present"] = active_relation
        if active_relation:
            cur.execute(
                """
                SELECT company_key, origin_url, proof_state, authority, activated_at, updated_at
                FROM generic_employer_origin_active_sources
                WHERE source_name = %s
                """,
                (source_name,),
            )
            active = cur.fetchone()
            state["active_source"] = dict(active) if active is not None else None

        cur.execute(
            """
            SELECT id, profile_name, is_active, search_location, search_radius_km
            FROM search_profiles
            WHERE source_name = %s
            ORDER BY id
            """,
            (source_name,),
        )
        state["profiles"] = [dict(row) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT id, search_profile_id, status, started_at, finished_at,
                   total_loaded, inserted_count, duplicate_count, error_message
            FROM ingestion_runs
            WHERE source_name = %s
            ORDER BY started_at DESC, id DESC
            LIMIT 5
            """,
            (source_name,),
        )
        state["recent_ingestion_runs"] = [dict(row) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT count(*)::integer AS raw_count
            FROM raw_jobs
            WHERE source_name = %s
            """,
            (source_name,),
        )
        state["raw_count"] = int(cur.fetchone()["raw_count"])

        cur.execute(
            """
            SELECT count(*)::integer AS silver_count
            FROM silver_jobs
            WHERE source_name = %s
            """,
            (source_name,),
        )
        state["silver_count"] = int(cur.fetchone()["silver_count"])

    print(
        "F4A_R2_GENERIC_FI_STATE="
        + json.dumps(state, default=str, ensure_ascii=False, sort_keys=True)
    )


def main() -> int:
    with psycopg.connect(**plan.get_database_config(), row_factory=plan.dict_row) as conn:
        _print_generic_source_state(conn)
        _print_exact_relocation_candidates(conn)
        conn.rollback()
    plan._load_current_rows = _operator_review_rows
    plan._load_authorized_sources = _current_product_sources
    return plan.main()


if __name__ == "__main__":
    raise SystemExit(main())
