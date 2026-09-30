from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.market_sensor_catalog import CORE_SENSORS

SCHEMA_VERSION = "jap.current_employer_connector_census.v1"
GENERIC_PREFIX = "generic_origin:"


def _latest_distinct_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, tuple[tuple[str, int], dict[str, Any]]] = {}
    for raw in rows:
        company_key = str(raw.get("company_key") or "").strip()
        if not company_key:
            continue
        row = dict(raw)
        source_name = str(row.get("source_name_candidate") or "").strip().casefold()
        family = source_name.split(":", 1)[0] if source_name else ""
        if family in {value.casefold() for value in CORE_SENSORS}:
            raise ValueError(f"market_sensor_leaked_into_employer_candidate_population:{company_key}")
        key = (
            str(row.get("updated_at") or ""),
            int(row.get("id") or 0),
        )
        previous = latest.get(company_key)
        if previous is None or key >= previous[0]:
            latest[company_key] = (key, row)
    return [item[1] for item in sorted(latest.values(), key=lambda item: item[1]["company_key"])]


def _builder_failure_map(builder_audit: Mapping[str, Any] | None) -> dict[str, str]:
    if not builder_audit:
        return {}
    candidates = builder_audit.get("results")
    if not isinstance(candidates, list):
        candidates = builder_audit.get("candidates")
    if not isinstance(candidates, list):
        candidates = builder_audit.get("assessments")
    if not isinstance(candidates, list):
        return {}
    result: dict[str, str] = {}
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        key = str(raw.get("company_key") or "").strip()
        if not key:
            continue
        ready = bool(raw.get("recipe_ready"))
        failure = str(raw.get("first_failure_layer") or "").strip()
        result[key] = "RECIPE_READY" if ready else (failure or "UNCLASSIFIED_GAP")
    return result


def build_census(
    *,
    candidate_rows: Sequence[Mapping[str, Any]],
    active_source_rows: Sequence[Mapping[str, Any]] = (),
    profile_rows: Sequence[Mapping[str, Any]] = (),
    ingestion_rows: Sequence[Mapping[str, Any]] = (),
    builder_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidates = _latest_distinct_candidates(candidate_rows)
    active_by_key = {
        str(row.get("company_key") or "").strip(): dict(row)
        for row in active_source_rows
        if str(row.get("company_key") or "").strip()
    }
    profiles_by_source = {
        str(row.get("source_name") or "").strip(): dict(row)
        for row in profile_rows
        if str(row.get("source_name") or "").strip()
    }
    runs_by_source = {
        str(row.get("source_name") or "").strip(): dict(row)
        for row in ingestion_rows
        if str(row.get("source_name") or "").strip()
    }
    builder = _builder_failure_map(builder_audit)

    records: list[dict[str, Any]] = []
    counts = {
        "employer_candidate_count": len(candidates),
        "active_recurring_connector_count": 0,
        "connector_materialized_nonrecurring_count": 0,
        "recipe_ready_not_materialized_count": 0,
        "source_resolution_gap_count": 0,
        "capability_gap_count": 0,
        "qualification_gap_count": 0,
        "resolution_required_count": 0,
        "broken_active_connector_count": 0,
    }

    for candidate in candidates:
        company_key = str(candidate["company_key"])
        canonical_source = f"{GENERIC_PREFIX}{company_key}"
        active = active_by_key.get(company_key)
        source_name = str((active or {}).get("source_name") or canonical_source)
        profile = profiles_by_source.get(source_name, {})
        run = runs_by_source.get(source_name, {})
        active_profile_count = int(profile.get("active_profile_count") or 0)
        recurring_profile_count = int(profile.get("recurring_profile_count") or 0)
        proof_pass = str((active or {}).get("proof_state") or "").casefold() == "pass"
        materialized = active is not None and proof_pass
        recurring = materialized and active_profile_count > 0 and recurring_profile_count > 0
        latest_run_status = str(run.get("last_ingestion_status") or "not_run").casefold()
        broken_active = recurring and latest_run_status == "failed"
        builder_state = builder.get(company_key)

        if broken_active:
            disposition = "BROKEN_ACTIVE_CONNECTOR"
            counts["broken_active_connector_count"] += 1
            counts["active_recurring_connector_count"] += 1
        elif recurring:
            disposition = "ACTIVE_RECURRING"
            counts["active_recurring_connector_count"] += 1
        elif materialized:
            disposition = "MATERIALIZED_NONRECURRING"
            counts["connector_materialized_nonrecurring_count"] += 1
        elif builder_state == "RECIPE_READY":
            disposition = "RECIPE_READY_NOT_MATERIALIZED"
            counts["recipe_ready_not_materialized_count"] += 1
        elif builder_state in {"identity", "origin", "origin_reachability", "delegation"}:
            disposition = "SOURCE_RESOLUTION_GAP"
            counts["source_resolution_gap_count"] += 1
        elif builder_state in {"provider", "inventory", "detail", "recipe"}:
            disposition = "CAPABILITY_GAP"
            counts["capability_gap_count"] += 1
        elif builder_state == "proof":
            disposition = "QUALIFICATION_GAP"
            counts["qualification_gap_count"] += 1
        elif builder_state:
            disposition = "BUILDER_GAP_UNCLASSIFIED"
            counts["resolution_required_count"] += 1
        else:
            disposition = "RESOLUTION_REQUIRED"
            counts["resolution_required_count"] += 1

        records.append(
            {
                "candidate_id": int(candidate.get("id") or 0) or None,
                "company_key": company_key,
                "company_name": str(candidate.get("company_name") or "").strip(),
                "candidate_status": str(candidate.get("status") or "unknown"),
                "candidate_url": candidate.get("candidate_url"),
                "canonical_source_name": canonical_source,
                "connector_source_name": source_name if materialized else None,
                "connector_materialized": materialized,
                "active_profile_count": active_profile_count,
                "recurring_profile_count": recurring_profile_count,
                "latest_run_status": latest_run_status,
                "builder_state": builder_state or "NOT_MEASURED",
                "disposition": disposition,
            }
        )

    accounted = sum(
        counts[key]
        for key in (
            "active_recurring_connector_count",
            "connector_materialized_nonrecurring_count",
            "recipe_ready_not_materialized_count",
            "source_resolution_gap_count",
            "capability_gap_count",
            "qualification_gap_count",
            "resolution_required_count",
        )
    )
    if accounted != counts["employer_candidate_count"]:
        raise ValueError(
            f"census_partition_mismatch:{accounted}!={counts['employer_candidate_count']}"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            **counts,
            "market_sensor_count_excluded": len(CORE_SENSORS),
            "market_sensors_excluded": list(CORE_SENSORS),
            "candidate_population_authority": "latest_distinct_employer_origin_source_candidates_by_company_key",
            "connector_identity": "generic_origin:<company_key>",
            "builder_gap_authority": (
                "fresh_supplied_builder_audit"
                if builder_audit is not None
                else "not_measured_no_capability_gap_inference"
            ),
            "builder_audit_schema": (
                str(builder_audit.get("schema") or builder_audit.get("schema_version") or "unknown")
                if builder_audit is not None
                else None
            ),
        },
        "candidates": records,
        "boundaries": {
            "read_only": True,
            "market_sensors_excluded": True,
            "historical_65_candidate_benchmark_not_population_authority": True,
            "source_overview_union_not_candidate_denominator": True,
            "missing_builder_measurement_is_resolution_required_not_capability_gap": True,
            "builder_failure_layer_is_not_automatically_capability_gap": True,
            "capability_gap_layers": ["provider", "inventory", "detail", "recipe"],
            "source_resolution_gap_layers": [
                "identity",
                "origin",
                "origin_reachability",
                "delegation"
            ],
            "qualification_gap_layers": ["proof"],
            "bespoke_connector_per_employer_required": False,
        },
    }


def _relation_exists(cur: Any, relation: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{relation}",))
    row = cur.fetchone()
    return bool(row and row[0] is not None)


def load_live_rows(conn: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, company_key, company_name, status, candidate_url,
                   source_name_candidate, updated_at
            FROM employer_origin_source_candidates
            ORDER BY company_key, updated_at, id
            """
        )
        candidates = list(cur.fetchall())

        active: list[dict[str, Any]] = []
        if _relation_exists(cur, "generic_employer_origin_active_sources"):
            cur.execute(
                """
                SELECT candidate_id, company_key, source_name, origin_url, proof_state,
                       activated_at, updated_at
                FROM generic_employer_origin_active_sources
                ORDER BY company_key
                """
            )
            active = list(cur.fetchall())

        profiles: list[dict[str, Any]] = []
        if _relation_exists(cur, "search_profiles"):
            cur.execute(
                """
                SELECT source_name,
                       count(*) FILTER (WHERE is_active)::integer AS active_profile_count,
                       count(*) FILTER (
                           WHERE is_active AND recurring_ingestion_enabled
                       )::integer AS recurring_profile_count
                FROM search_profiles
                WHERE source_name LIKE 'generic_origin:%'
                GROUP BY source_name
                ORDER BY source_name
                """
            )
            profiles = list(cur.fetchall())

        runs: list[dict[str, Any]] = []
        if _relation_exists(cur, "ingestion_runs"):
            cur.execute(
                """
                SELECT DISTINCT ON (source_name)
                       source_name,
                       status AS last_ingestion_status,
                       started_at,
                       finished_at,
                       error_message
                FROM ingestion_runs
                WHERE source_name LIKE 'generic_origin:%'
                ORDER BY source_name, started_at DESC, id DESC
                """
            )
            runs = list(cur.fetchall())
    return candidates, active, profiles, runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only current Employer-Origin connector fleet census."
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--builder-audit",
        type=Path,
        help="Optional fresh full-population deterministic builder audit JSON.",
    )
    args = parser.parse_args()

    builder_audit = None
    if args.builder_audit is not None:
        builder_audit = json.loads(args.builder_audit.read_text(encoding="utf-8"))

    with psycopg.connect(**get_database_config()) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        candidates, active, profiles, runs = load_live_rows(conn)
        result = build_census(
            candidate_rows=candidates,
            active_source_rows=active,
            profile_rows=profiles,
            ingestion_rows=runs,
            builder_audit=builder_audit,
        )
        conn.rollback()

    rendered = json.dumps(result, indent=2, sort_keys=True, default=str) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
