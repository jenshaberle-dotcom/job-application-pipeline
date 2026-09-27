"""Read-only comparison flight for the job-first Employer Discovery Census.

Control sources (BA + StepStone) use their existing registered connectors.
Additional boards are observed only through an explicitly selected external-index
transport. No board page is fetched by the external-index path and no database,
Bronze, Silver, Product, candidate, or connector write is performed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.registry import SourceRole, build_default_connector_registry
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.census_flight_authority import (
    CENSUS_EXTERNAL_INDEX_BACKENDS,
    DEFAULT_CENSUS_EXTERNAL_INDEX_BACKEND,
    resolve_census_flight_authority,
)
from src.search_intelligence.employer_discovery_census import (
    build_employer_discovery_census,
)
from src.search_intelligence.employer_discovery_census_adapter import (
    market_observation_from_raw_record,
)
from src.search_intelligence.external_index_job_sensors import (
    EXTERNAL_INDEX_SOURCES,
    accept_external_index_result,
    build_external_index_queries,
)
from src.search_intelligence.public_web_search import (
    backend_available,
    search_public_web,
)


CONTROL_SOURCES = ("bundesagentur_fuer_arbeit", "stepstone")
DEFAULT_OUTPUT = Path("/tmp/job-first-employer-discovery-census-comparison.json")


def _load_runtime_state(
    *,
    max_terms: int,
    max_locations: int,
) -> tuple[tuple[str, ...], tuple[str, ...], set[str]]:
    """Read current search intent and candidate baseline once under one RO tx."""
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT DISTINCT term.search_term
                    FROM search_terms term
                    JOIN search_profiles profile
                      ON profile.id = term.search_profile_id
                    WHERE term.is_active = TRUE
                      AND profile.is_active = TRUE
                      AND profile.source_name = ANY(%s)
                    ORDER BY term.search_term
                    LIMIT %s
                    """,
                    (list(CONTROL_SOURCES), max_terms),
                )
                terms = tuple(
                    str(row["search_term"]).strip()
                    for row in cur.fetchall()
                    if str(row.get("search_term") or "").strip()
                )

                cur.execute(
                    """
                    SELECT DISTINCT profile.search_location
                    FROM search_profiles profile
                    WHERE profile.is_active = TRUE
                      AND profile.source_name = ANY(%s)
                      AND NULLIF(btrim(profile.search_location), '') IS NOT NULL
                    ORDER BY profile.search_location
                    LIMIT %s
                    """,
                    (list(CONTROL_SOURCES), max_locations),
                )
                locations = tuple(
                    str(row["search_location"]).strip()
                    for row in cur.fetchall()
                    if str(row.get("search_location") or "").strip()
                )

                cur.execute(
                    """
                    SELECT DISTINCT company_key
                    FROM employer_origin_source_candidates
                    WHERE company_key IS NOT NULL
                    ORDER BY company_key
                    """
                )
                known = {
                    normalize_company_key(str(row["company_key"]))
                    for row in cur.fetchall()
                    if row.get("company_key")
                }
        conn.rollback()
    return terms, locations, {key for key in known if key}


def _run_control_sources(
    *,
    search_terms: tuple[str, ...],
    location: str,
    radius_km: int,
    page_size: int,
    observed_at_utc: str,
) -> tuple[list[Any], dict[str, dict[str, Any]]]:
    registry = build_default_connector_registry()
    observations: list[Any] = []
    telemetry: dict[str, dict[str, Any]] = {}

    for source_name in CONTROL_SOURCES:
        if registry.role_for(source_name) != SourceRole.SENSOR:
            raise RuntimeError(f"{source_name} is not registered as a sensor")
        connector = registry.create(source_name)
        profile = SearchProfile(
            id=0,
            profile_name="job_first_census_comparison",
            source_name=source_name,
            search_location=location,
            search_radius_km=radius_km,
            offer_type=1,
            page_size=page_size,
        )
        source_obs = []
        errors: list[str] = []
        fetch_invocations = 0
        for term in search_terms:
            try:
                fetch_invocations += 1
                records, _ = connector.fetch_jobs(profile, SearchTerm(term))
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                continue
            source_obs.extend(
                market_observation_from_raw_record(
                    record,
                    observed_at_utc=observed_at_utc,
                )
                for record in records
            )

        observations.extend(source_obs)
        telemetry[source_name] = {
            "mode": "registered_connector",
            "fetch_invocations": fetch_invocations,
            "observations": len(source_obs),
            "errors": errors,
            "network_request_count_exact": None,
            "network_request_count_note": (
                "connector fetch invocation count is exact; internal pagination "
                "may issue additional bounded HTTP requests"
            ),
        }

    return observations, telemetry


def _run_external_index_sources(
    *,
    provider: str,
    provider_available: bool,
    external_requests_authorized: bool,
    search_terms: tuple[str, ...],
    locations: tuple[str, ...],
    max_results: int,
    timeout_seconds: float,
    observed_at_utc: str,
) -> tuple[list[Any], dict[str, dict[str, Any]]]:
    observations: list[Any] = []
    telemetry: dict[str, dict[str, Any]] = {}

    for source in EXTERNAL_INDEX_SOURCES:
        plans = build_external_index_queries(
            source=source,
            search_terms=search_terms,
            location_signals=locations,
            max_terms=len(search_terms),
            max_locations=len(locations),
        )
        accepted = []
        result_shape_rejected = 0
        provider_request_count = 0
        transport_status_counts: dict[str, int] = defaultdict(int)

        if external_requests_authorized and provider_available:
            for plan in plans:
                response = search_public_web(
                    provider=provider,
                    query=plan.query,
                    max_results=max_results,
                    timeout_seconds=timeout_seconds,
                )
                provider_request_count += response.request_count
                transport_status_counts[response.status] += 1
                for row in response.results:
                    observation = accept_external_index_result(
                        source=source,
                        provider=row.provider,
                        url=row.url,
                        title=row.title,
                        snippet=row.snippet,
                        observed_at_utc=observed_at_utc,
                    )
                    if observation is None:
                        result_shape_rejected += 1
                        continue
                    accepted.append(observation)

        observations.extend(accepted)
        telemetry[source] = {
            "mode": "external_index_only",
            "query_count": len(plans),
            "provider_request_count": provider_request_count,
            "accepted_observations": len(accepted),
            "rejected_provider_results": result_shape_rejected,
            "transport_status_counts": dict(sorted(transport_status_counts.items())),
            "direct_board_requests": 0,
        }

    return observations, telemetry


def _incremental_metrics(report: dict[str, Any]) -> dict[str, Any]:
    control = set(CONTROL_SOURCES)
    external = set(EXTERNAL_INDEX_SOURCES)
    rows = report.get("employers") or []

    pairwise: dict[str, int] = defaultdict(int)
    incremental_by_source = {source: 0 for source in EXTERNAL_INDEX_SOURCES}
    overlap_with_control = {source: 0 for source in EXTERNAL_INDEX_SOURCES}
    incremental_company_keys: set[str] = set()

    for row in rows:
        sources = set(row.get("evidence_sources") or [])
        source_list = sorted(sources)
        for i, left in enumerate(source_list):
            for right in source_list[i + 1 :]:
                pairwise[f"{left}|{right}"] += 1

        has_control = bool(sources & control)
        is_novel = row.get("origin_status") == "novel"
        external_sources = sources & external
        for source in sorted(external_sources):
            if has_control:
                overlap_with_control[source] += 1
            elif is_novel:
                incremental_by_source[source] += 1

        if is_novel and external_sources and not has_control:
            company_key = str(row.get("company_key") or "").strip()
            if company_key:
                incremental_company_keys.add(company_key)

    return {
        "control_sources": list(CONTROL_SOURCES),
        "external_index_sources": list(EXTERNAL_INDEX_SOURCES),
        "pairwise_qualifying_employer_overlap": dict(sorted(pairwise.items())),
        "external_source_overlap_with_ba_or_stepstone": overlap_with_control,
        "novel_incremental_employers_vs_ba_stepstone_and_candidate_baseline": (
            incremental_by_source
        ),
        "primary_incremental_novel_employer_count": len(incremental_company_keys),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    authority = resolve_census_flight_authority(
        provider=args.provider,
        allow_paid_external_provider=args.allow_paid_external_provider,
    )
    provider_available = (
        args.provider == "none" or backend_available(args.provider)
    )

    terms, locations, known_company_keys = _load_runtime_state(
        max_terms=args.max_terms,
        max_locations=args.max_locations,
    )
    if not terms:
        raise RuntimeError("No active Census search terms were found.")
    if not locations:
        locations = ("Hannover",)

    observed_at = datetime.now(UTC).isoformat()
    controls, control_telemetry = _run_control_sources(
        search_terms=terms,
        location=locations[0],
        radius_km=args.radius_km,
        page_size=args.page_size,
        observed_at_utc=observed_at,
    )
    indexed, index_telemetry = _run_external_index_sources(
        provider=args.provider,
        provider_available=provider_available,
        external_requests_authorized=authority.external_requests_authorized,
        search_terms=terms,
        locations=locations,
        max_results=args.max_results,
        timeout_seconds=args.timeout_seconds,
        observed_at_utc=observed_at,
    )

    census = build_employer_discovery_census(
        [*controls, *indexed],
        known_company_keys=known_company_keys,
    )
    census["comparison"] = {
        "authority": {
            "provider": authority.provider,
            "status": authority.status,
            "external_requests_authorized": authority.external_requests_authorized,
            "paid_external_tool": authority.paid_external_tool,
            "reason": authority.reason,
            "provider_available": provider_available,
        },
        "intent": {
            "search_terms": list(terms),
            "location_signals": list(locations),
            "radius_km": args.radius_km,
            "page_size": args.page_size,
            "max_results": args.max_results,
        },
        "baseline_candidate_count": len(known_company_keys),
        "control_telemetry": control_telemetry,
        "external_index_telemetry": index_telemetry,
        "metrics": _incremental_metrics(census),
        "writes": {
            "database": 0,
            "bronze": 0,
            "silver": 0,
            "product": 0,
            "candidate": 0,
            "connector": 0,
        },
        "direct_board_requests": 0,
    }
    return census


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=CENSUS_EXTERNAL_INDEX_BACKENDS,
        default=DEFAULT_CENSUS_EXTERNAL_INDEX_BACKEND,
    )
    parser.add_argument(
        "--allow-paid-external-provider",
        action="store_true",
        help="Required together with a paid provider before any provider request.",
    )
    parser.add_argument("--max-terms", type=int, default=2)
    parser.add_argument("--max-locations", type=int, default=1)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--radius-km", type=int, default=50)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.max_terms <= 4:
        raise SystemExit("--max-terms must be between 1 and 4")
    if not 1 <= args.max_locations <= 2:
        raise SystemExit("--max-locations must be between 1 and 2")
    if not 1 <= args.max_results <= 10:
        raise SystemExit("--max-results must be between 1 and 10")
    if not 1 <= args.page_size <= 25:
        raise SystemExit("--page-size must be between 1 and 25")
    if args.provider != "none" and not args.allow_paid_external_provider:
        raise SystemExit(
            "External provider selected without --allow-paid-external-provider"
        )

    report = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    comparison = report["comparison"]
    metrics = comparison["metrics"]
    print("====================================================")
    print("JOB-FIRST EMPLOYER DISCOVERY CENSUS COMPARISON")
    print("====================================================")
    print(f"PROVIDER={comparison['authority']['provider']}")
    print(f"AUTHORITY_STATUS={comparison['authority']['status']}")
    print(
        "EXTERNAL_REQUESTS_AUTHORIZED="
        f"{comparison['authority']['external_requests_authorized']}"
    )
    print(f"PROVIDER_AVAILABLE={comparison['authority']['provider_available']}")
    print(f"BASELINE_CANDIDATES={comparison['baseline_candidate_count']}")
    print(f"OBSERVED_JOBS={report['observed_job_count']}")
    print(f"QUALIFYING_JOBS={report['qualifying_job_count']}")
    print(f"EMPLOYERS={report['employer_count']}")
    print(f"NOVEL_EMPLOYERS={report['novel_employer_count']}")
    print(
        "INCREMENTAL_NOVEL_EMPLOYERS="
        f"{metrics['primary_incremental_novel_employer_count']}"
    )
    print("DIRECT_BOARD_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("BRONZE_WRITES=0")
    print("SILVER_WRITES=0")
    print("PRODUCT_WRITES=0")
    print("CANDIDATE_CREATION=0")
    print("CONNECTOR_ACTIVATION=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
