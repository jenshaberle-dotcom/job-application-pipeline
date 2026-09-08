"""Read-only full connector delivery audit for JAP.

Enumerates connector implementations, registry entries, concrete DB profiles/targets,
and employer-origin candidates. Every active concrete profile is then probed through
its real connector without persisting Bronze/Silver/Gold state. The result correlates
live connector output with recent ingestion, observation, Silver and Control-Center
state so a zero-result path can be localized.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.registry import build_default_connector_registry
from src.ingestion.aggregator_discovery_filter import (
    filter_known_employer_origin_candidates,
    normalize_exclusion_keys,
)
from src.ingestion.post_fetch_filter import (
    apply_keyword_filter,
    apply_multi_term_keyword_filter,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("/tmp/jap-full-connector-delivery-audit.json")
LOCAL_SIGNALS = (
    "hannover", "hanover", "remote", "homeoffice", "hybrid",
    "deutschland", "germany", "bundesweit",
)


def relation_exists(conn: psycopg.Connection[Any], name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{name}",))
        row = cur.fetchone()
    return bool(row and row[0])


def columns(conn: psycopg.Connection[Any], name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (name,),
        )
        return {str(row[0]) for row in cur.fetchall()}


def fetch_all(
    conn: psycopg.Connection[Any], query: str, params: Sequence[Any] = ()
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def require_read_only(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("SHOW default_transaction_read_only")
        value = str(cur.fetchone()[0]).lower()
    if value != "on":
        raise RuntimeError(
            "AUDIT_REFUSED: default_transaction_read_only must be on, got " + value
        )


def connector_implementations() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path in sorted((ROOT / "src" / "connectors").glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [
                base.id if isinstance(base, ast.Name) else base.attr
                for base in node.bases
                if isinstance(base, (ast.Name, ast.Attribute))
            ]
            if "JobSourceConnector" in bases:
                result.append(
                    {
                        "module": f"src.connectors.{path.stem}",
                        "class_name": node.name,
                        "path": str(path.relative_to(ROOT)),
                    }
                )
    return result


def registry_snapshot() -> dict[str, Any]:
    registry = build_default_connector_registry()
    return {
        "exact": [
            {
                "source_name": key,
                "role": registry.exact_roles.get(key).value
                if registry.exact_roles.get(key) else None,
                "factory": getattr(factory, "__name__", repr(factory)),
            }
            for key, factory in sorted(registry.exact_factories.items())
        ],
        "families": [
            {
                "source_family": key,
                "role": registry.family_roles.get(key).value
                if registry.family_roles.get(key) else None,
                "factory": getattr(factory, "__name__", repr(factory)),
            }
            for key, factory in sorted(registry.family_factories.items())
        ],
    }


def db_snapshot() -> dict[str, Any]:
    with psycopg.connect(**get_database_config()) as conn:
        require_read_only(conn)
        profile_cols = columns(conn, "search_profiles")
        recurring = (
            "recurring_ingestion_enabled"
            if "recurring_ingestion_enabled" in profile_cols
            else "FALSE AS recurring_ingestion_enabled"
        )
        profiles = fetch_all(
            conn,
            f"""
            SELECT id, profile_name, source_name, search_location,
                   search_radius_km, offer_type, page_size, is_active, {recurring}
            FROM search_profiles
            ORDER BY source_name, profile_name, id
            """,
        )
        terms = fetch_all(
            conn,
            """
            SELECT id, search_profile_id, search_term, is_active
            FROM search_terms
            ORDER BY search_profile_id, is_active DESC, search_term, id
            """,
        ) if relation_exists(conn, "search_terms") else []

        run_cols = columns(conn, "ingestion_runs")
        connector_count = (
            "connector_record_count" if "connector_record_count" in run_cols
            else "NULL::integer AS connector_record_count"
        )
        post_count = (
            "post_filter_count" if "post_filter_count" in run_cols
            else "NULL::integer AS post_filter_count"
        )
        error_type = (
            "error_type" if "error_type" in run_cols
            else "NULL::text AS error_type"
        )
        error_stage = (
            "error_stage" if "error_stage" in run_cols
            else "NULL::text AS error_stage"
        )
        latest_runs = fetch_all(
            conn,
            f"""
            SELECT DISTINCT ON (search_profile_id)
                   id, search_profile_id, source_name, status, started_at,
                   finished_at, total_loaded, inserted_count, duplicate_count,
                   {connector_count}, {post_count}, {error_type}, {error_stage},
                   error_message
            FROM ingestion_runs
            WHERE search_profile_id IS NOT NULL
            ORDER BY search_profile_id, started_at DESC, id DESC
            """,
        )
        latest_source_runs = fetch_all(
            conn,
            f"""
            SELECT DISTINCT ON (source_name)
                   source_name, status, started_at, finished_at, total_loaded,
                   inserted_count, duplicate_count, {connector_count}, {post_count},
                   error_message
            FROM ingestion_runs
            ORDER BY source_name, started_at DESC, id DESC
            """,
        )

        bronze = fetch_all(
            conn,
            """
            SELECT source_name, COUNT(*) AS bronze_total,
                   COUNT(*) FILTER (WHERE fetched_at >= NOW()-INTERVAL '7 days') AS bronze_7d,
                   MAX(fetched_at) AS latest_bronze_at
            FROM raw_jobs GROUP BY source_name ORDER BY source_name
            """,
        ) if relation_exists(conn, "raw_jobs") else []
        observations = fetch_all(
            conn,
            """
            SELECT source_name, COUNT(*) AS observation_total,
                   COUNT(*) FILTER (WHERE observed_at >= NOW()-INTERVAL '24 hours') AS observations_24h,
                   COUNT(*) FILTER (WHERE observed_at >= NOW()-INTERVAL '7 days') AS observations_7d,
                   MAX(observed_at) AS latest_observed_at
            FROM job_observations GROUP BY source_name ORDER BY source_name
            """,
        ) if relation_exists(conn, "job_observations") else []
        silver = fetch_all(
            conn,
            """
            SELECT source_name, COUNT(*) AS silver_total,
                   COUNT(*) FILTER (WHERE normalized_at >= NOW()-INTERVAL '7 days') AS silver_7d,
                   COUNT(*) FILTER (WHERE lower(coalesce(city,'')) IN ('hannover','hanover')) AS silver_hannover,
                   MAX(normalized_at) AS latest_silver_at
            FROM silver_jobs GROUP BY source_name ORDER BY source_name
            """,
        ) if relation_exists(conn, "silver_jobs") else []

        gold: list[dict[str, Any]] = []
        if relation_exists(conn, "gold_product_v1_job_readiness") and relation_exists(conn, "silver_jobs"):
            ready_cols = columns(conn, "gold_product_v1_job_readiness")
            active_expr = (
                "COUNT(*) FILTER (WHERE r.activity_status='active')"
                if "activity_status" in ready_cols else "0::bigint"
            )
            rankable_expr = (
                "COUNT(*) FILTER (WHERE r.product_readiness_status='rankable')"
                if "product_readiness_status" in ready_cols else "0::bigint"
            )
            gold = fetch_all(
                conn,
                f"""
                SELECT s.source_name, COUNT(*) AS cc_total,
                       {active_expr} AS cc_active,
                       {rankable_expr} AS cc_rankable
                FROM gold_product_v1_job_readiness r
                JOIN silver_jobs s ON s.id=r.silver_job_id
                GROUP BY s.source_name ORDER BY s.source_name
                """,
            )

        candidates: list[dict[str, Any]] = []
        if relation_exists(conn, "employer_origin_source_candidates"):
            lifecycle_join = ""
            module_col = "NULL::text AS connector_module_path"
            if relation_exists(conn, "gold_candidate_lifecycle_status"):
                lifecycle_join = (
                    "LEFT JOIN gold_candidate_lifecycle_status l "
                    "ON l.candidate_id=c.id"
                )
                if "connector_module_path" in columns(conn, "gold_candidate_lifecycle_status"):
                    module_col = "l.connector_module_path"
            candidates = fetch_all(
                conn,
                f"""
                SELECT c.id AS candidate_id, c.company_key, c.company_name,
                       c.source_name_candidate, c.source_family_candidate,
                       c.status AS candidate_status, c.updated_at, {module_col}
                FROM employer_origin_source_candidates c
                {lifecycle_join}
                ORDER BY c.updated_at DESC, c.id DESC
                """,
            )

        suppression: list[str] = []
        if relation_exists(conn, "employer_origin_source_candidates"):
            for row in fetch_all(
                conn,
                """
                SELECT company_key, company_name, source_family_candidate
                FROM employer_origin_source_candidates
                WHERE status IN ('active_controlled','deprecated','disabled',
                                 'abort_documented','not_actionable')
                """,
            ):
                suppression.extend(
                    str(value) for value in row.values()
                    if value is not None and str(value).strip()
                )

    return {
        "profiles": profiles,
        "terms": terms,
        "latest_runs": latest_runs,
        "latest_source_runs": latest_source_runs,
        "bronze": bronze,
        "observations": observations,
        "silver": silver,
        "gold": gold,
        "candidates": candidates,
        "stepstone_suppression": suppression,
    }


def group(rows: Sequence[Mapping[str, Any]], key: str) -> dict[Any, list[dict[str, Any]]]:
    result: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row.get(key), []).append(dict(row))
    return result


def map_rows(rows: Sequence[Mapping[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    return {row.get(key): dict(row) for row in rows if row.get(key) is not None}


def record_key(record: RawJobRecord) -> tuple[str, str]:
    return record.source_name, str(record.external_job_id or record.source_url)


def unique(records: Sequence[RawJobRecord]) -> list[RawJobRecord]:
    seen: set[tuple[str, str]] = set()
    result: list[RawJobRecord] = []
    for record in records:
        key = record_key(record)
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


def nested(raw: Mapping[str, Any], *path: str) -> Any:
    value: Any = raw
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def first_text(raw: Mapping[str, Any], paths: Sequence[tuple[str, ...]]) -> str:
    for path in paths:
        value = nested(raw, *path)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def summarize_record(record: RawJobRecord) -> dict[str, Any]:
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    title = first_text(raw, (("result_card", "title"), ("job", "titel"), ("job", "title")))
    company = first_text(raw, (("result_card", "company_name"), ("job", "arbeitgeber"), ("job", "company_name"), ("job", "company")))
    locations: list[str] = []
    for path in (("result_card", "location"), ("job", "location"), ("job", "ort"), ("job", "city")):
        value = nested(raw, *path)
        if value is not None and str(value).strip() and str(value).strip() not in locations:
            locations.append(str(value).strip())
    structured = nested(raw, "job", "locations")
    if isinstance(structured, list):
        for item in structured:
            if isinstance(item, Mapping):
                text = ", ".join(
                    str(item.get(key) or "").strip()
                    for key in ("city", "country_code")
                    if str(item.get(key) or "").strip()
                )
                if text and text not in locations:
                    locations.append(text)
    location = " | ".join(locations)
    normalized = location.casefold()
    return {
        "external_job_id": record.external_job_id,
        "title": title,
        "company_name": company,
        "location": location,
        "local_signals": [term for term in LOCAL_SIGNALS if term in normalized],
        "source_url": record.source_url,
    }


def profile_object(row: Mapping[str, Any]) -> SearchProfile:
    return SearchProfile(
        id=int(row["id"]),
        profile_name=str(row["profile_name"]),
        source_name=str(row["source_name"]),
        search_location=str(row["search_location"]) if row.get("search_location") is not None else None,
        search_radius_km=int(row["search_radius_km"]) if row.get("search_radius_km") is not None else None,
        offer_type=int(row["offer_type"]) if row.get("offer_type") is not None else None,
        page_size=int(row.get("page_size") or 0),
    )


def connector_metadata(connector: Any) -> dict[str, Any]:
    capabilities = asdict(connector.capabilities)
    max_detail_pages = getattr(connector, "max_detail_pages", None)
    listing_url = getattr(connector, "listing_url", None)
    target = getattr(connector, "target", None)
    if listing_url is None and target is not None:
        listing_url = getattr(target, "listing_url", None)
    cap = int(max_detail_pages) if isinstance(max_detail_pages, int) else None
    return {
        "capabilities": capabilities,
        "max_detail_pages": cap,
        "listing_url": str(listing_url) if listing_url else None,
        "full_fetch_declared_but_detail_capped": bool(
            capabilities.get("supports_full_fetch") is True and cap is not None
        ),
    }


def probe_profile(
    row: Mapping[str, Any], term_rows: Sequence[Mapping[str, Any]], suppression_keys: set[str]
) -> dict[str, Any]:
    profile = profile_object(row)
    active_terms = [
        SearchTerm(id=int(item["id"]), search_term=str(item["search_term"]))
        for item in term_rows if item.get("is_active") is True
    ]
    result: dict[str, Any] = {
        "profile_id": profile.id,
        "profile_name": profile.profile_name,
        "source_name": profile.source_name,
        "search_location": profile.search_location,
        "search_radius_km": profile.search_radius_km,
        "page_size": profile.page_size,
        "active": bool(row.get("is_active")),
        "recurring_ingestion_enabled": bool(row.get("recurring_ingestion_enabled")),
        "active_terms": [term.search_term for term in active_terms],
    }
    if not result["active"]:
        return {**result, "probe_status": "skipped", "skip_reason": "profile_inactive"}
    if not active_terms:
        return {**result, "probe_status": "skipped", "skip_reason": "no_active_terms"}

    registry = build_default_connector_registry()
    try:
        connector = registry.create(profile.source_name)
        result["source_role"] = registry.role_for(profile.source_name).value
        result.update(connector_metadata(connector))
    except Exception as exc:  # noqa: BLE001
        return {**result, "probe_status": "error", "failure_stage": "registry", "error": f"{type(exc).__name__}: {exc}"}

    try:
        fetched_all: list[RawJobRecord] = []
        post_all: list[RawJobRecord] = []
        deliverable_all: list[RawJobRecord] = []
        term_runs: list[dict[str, Any]] = []
        caps = connector.capabilities
        if caps.supports_full_fetch and not caps.supports_keyword:
            records, final_url = connector.fetch_jobs(profile, SearchTerm(search_term="*", id=None))
            fetched = list(records)
            post = apply_multi_term_keyword_filter(fetched, active_terms)
            deliverable = list(post)
            if profile.page_size > 0:
                deliverable = deliverable[: profile.page_size]
            fetched_all.extend(fetched)
            post_all.extend(post)
            deliverable_all.extend(deliverable)
            term_runs.append({
                "mode": "full_fetch_then_local_multi_term",
                "requested_term": "*",
                "connector_records": len(fetched),
                "post_keyword_records": len(post),
                "deliverable_records": len(deliverable),
                "final_url": final_url,
            })
        else:
            for term in active_terms:
                records, final_url = connector.fetch_jobs(profile, term)
                fetched = list(records)
                post = list(fetched)
                if not caps.supports_keyword:
                    post = apply_keyword_filter(post, term.search_term)
                deliverable = list(post)
                suppressed = 0
                if profile.source_name == "stepstone":
                    filtered = filter_known_employer_origin_candidates(deliverable, suppression_keys)
                    suppressed = len(filtered.suppressed_records)
                    deliverable = filtered.kept_records
                fetched_all.extend(fetched)
                post_all.extend(post)
                deliverable_all.extend(deliverable)
                term_runs.append({
                    "mode": "per_term",
                    "requested_term": term.search_term,
                    "connector_records": len(fetched),
                    "post_keyword_records": len(post),
                    "suppressed_records": suppressed,
                    "deliverable_records": len(deliverable),
                    "final_url": final_url,
                })

        fetched_unique = unique(fetched_all)
        post_unique = unique(post_all)
        deliverable_unique = unique(deliverable_all)
        samples = [summarize_record(record) for record in deliverable_unique[:8]]
        return {
            **result,
            "probe_status": "success",
            "connector_record_count_sum": sum(int(item["connector_records"]) for item in term_runs),
            "connector_record_count_unique": len(fetched_unique),
            "post_keyword_count_unique": len(post_unique),
            "deliverable_count_unique": len(deliverable_unique),
            "sample_jobs": samples,
            "term_runs": term_runs,
        }
    except Exception as exc:  # noqa: BLE001
        return {**result, "probe_status": "error", "failure_stage": "connector_fetch", "error": f"{type(exc).__name__}: {exc}"}


def diagnose(profile: Mapping[str, Any], latest: Mapping[str, Any] | None, state: Mapping[str, Any]) -> list[str]:
    if not profile.get("active"):
        return ["PROFILE_INACTIVE"]
    if not profile.get("active_terms"):
        return ["NO_ACTIVE_SEARCH_TERMS"]
    if profile.get("probe_status") == "error":
        return [f"LIVE_{str(profile.get('failure_stage') or 'unknown').upper()}_ERROR"]
    if profile.get("probe_status") != "success":
        return ["LIVE_PROBE_NOT_EXECUTED"]

    findings: list[str] = []
    connector_count = int(profile.get("connector_record_count_unique") or 0)
    post_count = int(profile.get("post_keyword_count_unique") or 0)
    deliverable = int(profile.get("deliverable_count_unique") or 0)
    capped = bool(profile.get("full_fetch_declared_but_detail_capped"))
    if connector_count == 0:
        findings.append("ZERO_FROM_BOUNDED_CONNECTOR_INCONCLUSIVE" if capped else "CONNECTOR_RETURNED_ZERO_LIVE")
    elif post_count == 0:
        findings.append("SOURCE_HAS_JOBS_BUT_ACTIVE_TERMS_FILTER_ALL")
    elif deliverable == 0:
        findings.append("POST_FETCH_POLICY_FILTERS_ALL")
    else:
        findings.append("LIVE_CONNECTOR_HAS_DELIVERABLE_JOBS")
    if capped:
        findings.append("FULL_FETCH_CONTRACT_MISMATCH_DETAIL_CAP")
    if not profile.get("recurring_ingestion_enabled"):
        findings.append("RECURRING_INGESTION_DISABLED")
    if latest is None:
        findings.append("NO_INGESTION_RUN_HISTORY")
    else:
        if latest.get("status") != "success":
            findings.append("LATEST_INGESTION_RUN_FAILED")
        if int(latest.get("connector_record_count") or 0) > 0 and int(latest.get("post_filter_count") or 0) == 0:
            findings.append("PRODUCTION_POST_FILTER_DROPPED_ALL")
    if deliverable > 0 and int(state.get("observations_7d") or 0) == 0:
        findings.append("LIVE_JOBS_NOT_REACHING_RECENT_BRONZE_OBSERVATIONS")
    if int(state.get("observations_7d") or 0) > 0 and int(state.get("silver_7d") or 0) == 0:
        findings.append("RECENT_BRONZE_OBSERVATIONS_NOT_REACHING_SILVER")
    if int(state.get("silver_total") or 0) > 0 and int(state.get("cc_active") or 0) == 0:
        findings.append("SILVER_EXISTS_BUT_NO_ACTIVE_CC_JOB")
    return findings


def build_report() -> dict[str, Any]:
    db = db_snapshot()
    registry = build_default_connector_registry()
    registry_view = registry_snapshot()
    implementations = connector_implementations()
    terms_by_profile = group(db["terms"], "search_profile_id")
    latest_by_profile = map_rows(db["latest_runs"], "search_profile_id")

    state: dict[str, dict[str, Any]] = {}
    for section in ("latest_source_runs", "bronze", "observations", "silver", "gold"):
        for row in db[section]:
            state.setdefault(str(row["source_name"]), {}).update(row)

    suppression_keys = normalize_exclusion_keys(db["stepstone_suppression"])
    profiles: list[dict[str, Any]] = []
    for row in db["profiles"]:
        audit = probe_profile(row, terms_by_profile.get(row["id"], []), suppression_keys)
        latest = latest_by_profile.get(row["id"])
        source_state = state.get(str(row["source_name"]), {})
        audit["latest_ingestion_run"] = latest
        audit["source_db_state"] = source_state
        audit["diagnosis"] = diagnose(audit, latest, source_state)
        profiles.append(audit)

    profile_sources = group(db["profiles"], "source_name")
    candidate_sources = group(db["candidates"], "source_name_candidate")
    concrete = {str(row["source_name"]) for row in db["profiles"]}
    concrete.update(str(row["source_name"]) for row in registry_view["exact"])
    concrete.update(
        str(row["source_name_candidate"])
        for row in db["candidates"] if row.get("source_name_candidate")
    )

    sources: list[dict[str, Any]] = []
    for source_name in sorted(concrete):
        try:
            connector = registry.create(source_name)
            meta = connector_metadata(connector)
            resolvable = True
            role = registry.role_for(source_name).value
            cls = type(connector).__name__
            module = type(connector).__module__
            error = None
        except Exception as exc:  # noqa: BLE001
            meta = {}
            resolvable = False
            role = None
            cls = None
            module = None
            error = f"{type(exc).__name__}: {exc}"
        bound_profiles = profile_sources.get(source_name, [])
        sources.append({
            "source_name": source_name,
            "source_family": source_name.split(":", 1)[0],
            "registry_resolvable": resolvable,
            "source_role": role,
            "connector_class": cls,
            "connector_module": module,
            **meta,
            "registration_error": error,
            "profile_count": len(bound_profiles),
            "active_profile_count": sum(bool(row.get("is_active")) for row in bound_profiles),
            "recurring_profile_count": sum(bool(row.get("is_active")) and bool(row.get("recurring_ingestion_enabled")) for row in bound_profiles),
            "candidate_count": len(candidate_sources.get(source_name, [])),
            "db_state": state.get(source_name, {}),
        })

    active = [row for row in profiles if row.get("active")]
    success = [row for row in active if row.get("probe_status") == "success"]
    with_jobs = [row for row in success if int(row.get("connector_record_count_unique") or 0) > 0]
    deliverable = [row for row in success if int(row.get("deliverable_count_unique") or 0) > 0]
    return {
        "schema": "job_application_pipeline.full_connector_delivery_audit.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "safety": {
            "database_read_only": True,
            "database_writes": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "gold_writes": 0,
            "source_activation": False,
            "provider_or_llm_calls": 0,
            "network_surface": "existing connector fetch_jobs only",
        },
        "summary": {
            "connector_implementation_classes": len(implementations),
            "registry_exact_entries": len(registry_view["exact"]),
            "registry_family_entries": len(registry_view["families"]),
            "concrete_source_names": len(sources),
            "db_profiles_total": len(profiles),
            "db_profiles_active": len(active),
            "db_profiles_active_recurring": sum(bool(row.get("recurring_ingestion_enabled")) for row in active),
            "live_profiles_success": len(success),
            "live_profiles_error": sum(row.get("probe_status") == "error" for row in active),
            "live_profiles_with_connector_jobs": len(with_jobs),
            "live_profiles_with_deliverable_jobs": len(deliverable),
            "live_deliverable_but_recurring_disabled": sum(not row.get("recurring_ingestion_enabled") for row in deliverable),
            "full_fetch_contract_mismatches": sum(bool(row.get("full_fetch_declared_but_detail_capped")) for row in success),
        },
        "registry": registry_view,
        "implementation_classes": implementations,
        "sources": sources,
        "profiles": profiles,
        "employer_origin_candidates": db["candidates"],
    }


def print_summary(report: Mapping[str, Any]) -> None:
    print("============================================================")
    print("JAP FULL CONNECTOR DELIVERY AUDIT")
    print("============================================================")
    for key, value in report["summary"].items():
        print(f"{key.upper()}={value}")
    print("SOURCE | ROLE | profiles active/recurring | latest | obs7d | silver7d | cc-active")
    for source in report["sources"]:
        state = source.get("db_state") or {}
        print(
            f"{source['source_name']} | {source.get('source_role') or '-'} | "
            f"{source['profile_count']} {source['active_profile_count']}/{source['recurring_profile_count']} | "
            f"{state.get('status', '-')} | {state.get('observations_7d', 0)} | "
            f"{state.get('silver_7d', 0)} | {state.get('cc_active', 0)}"
        )
    print("PROFILE | SOURCE | recurring | connector/post/deliverable | diagnosis")
    for profile in report["profiles"]:
        if not profile.get("active"):
            continue
        print(
            f"{profile['profile_name']} | {profile['source_name']} | "
            f"{profile['recurring_ingestion_enabled']} | "
            f"{profile.get('connector_record_count_unique', '-')}/"
            f"{profile.get('post_keyword_count_unique', '-')}/"
            f"{profile.get('deliverable_count_unique', '-')} | "
            f"{','.join(profile.get('diagnosis') or [])}"
        )
        if profile.get("error"):
            print(f"PROFILE_ERROR={profile['profile_name']}|{profile['error']}")
    print("DATABASE_WRITES=0")
    print("AUDIT=COMPLETE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print_summary(report)
    print(f"artifact={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
