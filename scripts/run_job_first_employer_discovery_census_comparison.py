"""Read-only comparison flight for the job-first Employer Discovery Census.

Control sources (BA + StepStone) use their existing registered connectors.
Additional boards are observed only through an explicitly selected external-index
transport. No board page is fetched by the external-index path. The flight is
read-only by default; an explicit write gate may persist minimized sensor evidence
to the existing market_evidence boundary. Bronze, Silver, Product, candidate and
connector writes remain forbidden.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.bundesagentur import BundesagenturConnector
from src.connectors.stepstone import StepStoneConnector
from src.ingestion.repository import JobIngestionRepository
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.census_flight_authority import (
    CENSUS_EXTERNAL_INDEX_BACKENDS,
    DEFAULT_CENSUS_EXTERNAL_INDEX_BACKEND,
    resolve_census_flight_authority,
)
from src.search_intelligence.employer_discovery_census import (
    build_employer_discovery_census,
    qualify_observation,
)
from src.search_intelligence.employer_discovery_census_adapter import (
    market_observation_from_raw_record,
)
from src.search_intelligence.external_index_job_sensors import (
    EXTERNAL_INDEX_SOURCES,
    accept_external_index_result,
    build_external_index_queries,
)
from src.search_intelligence.market_sensor_evidence_contract import (
    build_market_sensor_evidence_payload,
)
from src.search_intelligence.market_sensor_coverage import (
    MarketSensorProfile,
    supports_local_target,
    supports_remote_nationwide_target,
)
from src.search_intelligence.market_source_access import source_access_qualification
from src.search_intelligence.public_web_search import (
    backend_available,
    search_public_web,
)


CONTROL_SOURCES = ("bundesagentur_fuer_arbeit", "stepstone")
CENSUS_EXTERNAL_PROFILE_NAME = "job_first_employer_discovery_census"
DEFAULT_OUTPUT = Path("/tmp/job-first-employer-discovery-census-comparison.json")


@dataclass(frozen=True)
class RuntimeProfileIntent:
    profile: SearchProfile
    search_terms: tuple[str, ...]


def _profile_intents_from_rows(rows: list[dict[str, Any]]) -> tuple[RuntimeProfileIntent, ...]:
    grouped: dict[tuple[object, ...], set[str]] = {}
    profile_values: dict[tuple[object, ...], SearchProfile] = {}

    for row in rows:
        term = str(row.get("search_term") or "").strip()
        if not term:
            continue
        key = (
            int(row["id"]),
            str(row["profile_name"]),
            str(row["source_name"]),
            row.get("search_location"),
            row.get("search_radius_km"),
            row.get("offer_type"),
            int(row["page_size"]),
        )
        profile_values[key] = SearchProfile(
            id=int(row["id"]),
            profile_name=str(row["profile_name"]),
            source_name=str(row["source_name"]),
            search_location=(
                str(row["search_location"]).strip()
                if row.get("search_location") is not None
                and str(row["search_location"]).strip()
                else None
            ),
            search_radius_km=(
                int(row["search_radius_km"])
                if row.get("search_radius_km") is not None
                else None
            ),
            offer_type=(
                int(row["offer_type"])
                if row.get("offer_type") is not None
                else None
            ),
            page_size=int(row["page_size"]),
        )
        grouped.setdefault(key, set()).add(term)

    return tuple(
        RuntimeProfileIntent(
            profile=profile_values[key],
            search_terms=tuple(sorted(grouped[key], key=str.casefold)),
        )
        for key in sorted(
            grouped,
            key=lambda item: (str(item[2]).casefold(), str(item[1]).casefold(), int(item[0])),
        )
    )


def _external_location_signals(
    profile_intents: tuple[RuntimeProfileIntent, ...],
) -> tuple[str, ...]:
    """Project source-specific profiles into canonical Census market intents."""
    profiles = tuple(
        MarketSensorProfile(
            profile_key=intent.profile.profile_name,
            source_name=intent.profile.source_name,
            search_location=intent.profile.search_location,
            search_radius_km=intent.profile.search_radius_km,
            search_terms=intent.search_terms,
            is_active=True,
        )
        for intent in profile_intents
    )
    signals: list[str] = []
    if any(supports_local_target(profile) for profile in profiles):
        signals.append("Hannover")
    if any(supports_remote_nationwide_target(profile) for profile in profiles):
        signals.append("Deutschland remote")
    return tuple(signals)


def _load_runtime_state(
) -> tuple[tuple[RuntimeProfileIntent, ...], tuple[str, ...], tuple[str, ...], set[str]]:
    """Read the complete active control raster and candidate baseline once."""
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT
                        profile.id,
                        profile.profile_name,
                        profile.source_name,
                        profile.search_location,
                        profile.search_radius_km,
                        profile.offer_type,
                        profile.page_size,
                        COALESCE(term.search_term, profile.search_term) AS search_term
                    FROM search_profiles profile
                    LEFT JOIN search_terms term
                      ON term.search_profile_id = profile.id
                     AND term.is_active = TRUE
                    WHERE profile.is_active = TRUE
                      AND profile.source_name = ANY(%s)
                      AND NULLIF(
                            btrim(COALESCE(term.search_term, profile.search_term, '')),
                            ''
                          ) IS NOT NULL
                    ORDER BY
                        profile.source_name,
                        profile.profile_name,
                        search_term
                    """,
                    (list(CONTROL_SOURCES),),
                )
                intents = _profile_intents_from_rows(list(cur.fetchall()))

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

    search_terms = tuple(
        sorted(
            {
                term
                for intent in intents
                for term in intent.search_terms
            },
            key=str.casefold,
        )
    )
    locations = tuple(
        sorted(
            {
                intent.profile.search_location
                for intent in intents
                if intent.profile.search_location
            },
            key=str.casefold,
        )
    )
    return intents, search_terms, locations, {key for key in known if key}


def _run_control_sources(
    *,
    profile_intents: tuple[RuntimeProfileIntent, ...],
    observed_at_utc: str,
) -> tuple[list[Any], dict[str, dict[str, Any]]]:
    connector_factories = {
        "bundesagentur_fuer_arbeit": BundesagenturConnector,
        "stepstone": StepStoneConnector,
    }
    observations: list[Any] = []
    telemetry: dict[str, dict[str, Any]] = {}

    intents_by_source: dict[str, list[RuntimeProfileIntent]] = defaultdict(list)
    for intent in profile_intents:
        intents_by_source[intent.profile.source_name].append(intent)

    for source_name in CONTROL_SOURCES:
        if not source_access_qualification(source_name).automation_authorized:
            raise RuntimeError(f"{source_name} is not authorized for direct sensor access")
        connector = connector_factories[source_name]()
        source_obs = []
        errors: list[str] = []
        fetch_invocations = 0
        profile_telemetry: list[dict[str, Any]] = []

        for intent in intents_by_source.get(source_name, []):
            profile_fetches = 0
            profile_observations_before = len(source_obs)
            for term in intent.search_terms:
                try:
                    fetch_invocations += 1
                    profile_fetches += 1
                    records, _ = connector.fetch_jobs(
                        intent.profile,
                        SearchTerm(term),
                    )
                except Exception as exc:
                    errors.append(
                        f"{intent.profile.profile_name}|{term}|"
                        f"{type(exc).__name__}: {exc}"
                    )
                    continue
                source_obs.extend(
                    market_observation_from_raw_record(
                        record,
                        observed_at_utc=observed_at_utc,
                    )
                    for record in records
                )

            profile_telemetry.append(
                {
                    "profile_name": intent.profile.profile_name,
                    "location": intent.profile.search_location,
                    "radius_km": intent.profile.search_radius_km,
                    "offer_type": intent.profile.offer_type,
                    "page_size": intent.profile.page_size,
                    "search_term_count": len(intent.search_terms),
                    "fetch_invocations": profile_fetches,
                    "observations": len(source_obs) - profile_observations_before,
                }
            )

        observations.extend(source_obs)
        telemetry[source_name] = {
            "mode": "registered_connector",
            "profile_count": len(intents_by_source.get(source_name, [])),
            "profiles": profile_telemetry,
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
    max_external_requests: int,
    timeout_seconds: float,
    observed_at_utc: str,
) -> tuple[list[Any], dict[str, dict[str, Any]]]:
    observations: list[Any] = []
    telemetry: dict[str, dict[str, Any]] = {}
    plans_by_source = {
        source: build_external_index_queries(
            source=source,
            search_terms=search_terms,
            location_signals=locations,
            max_terms=len(search_terms),
            max_locations=len(locations),
        )
        for source in EXTERNAL_INDEX_SOURCES
    }
    planned_request_count = sum(len(plans) for plans in plans_by_source.values())

    if (
        external_requests_authorized
        and provider_available
        and planned_request_count > max_external_requests
    ):
        raise RuntimeError(
            "Full external-index raster requires "
            f"{planned_request_count} provider requests, exceeding explicit "
            f"flight budget {max_external_requests}; refusing to truncate search intent."
        )

    for source in EXTERNAL_INDEX_SOURCES:
        plans = plans_by_source[source]
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
                        search_term=plan.search_term,
                        location_signal=plan.location_signal,
                    )
                    if observation is None:
                        result_shape_rejected += 1
                        continue
                    accepted.append(observation)

        observations.extend(accepted)
        telemetry[source] = {
            "mode": "external_index_only",
            "query_count": len(plans),
            "full_raster_preserved": True,
            "provider_request_budget": max_external_requests,
            "provider_request_count": provider_request_count,
            "accepted_observations": len(accepted),
            "rejected_provider_results": result_shape_rejected,
            "transport_status_counts": dict(sorted(transport_status_counts.items())),
            "direct_board_requests": 0,
        }

    return observations, telemetry


def _persist_external_market_evidence(
    observations: list[Any],
    *,
    repository: JobIngestionRepository | None = None,
) -> dict[str, int]:
    """Persist qualified external-index observations through the sensor boundary."""

    repo = repository or JobIngestionRepository()
    qualified_count = 0
    written_count = 0

    for observation in observations:
        if qualify_observation(observation) is None:
            continue
        company_name = " ".join(str(observation.company_name or "").split()).strip()
        if not company_name:
            continue
        qualified_count += 1
        payload = build_market_sensor_evidence_payload(
            source_name=observation.source,
            company_name=company_name,
            display_title=observation.title,
            search_profile_name=CENSUS_EXTERNAL_PROFILE_NAME,
            search_term=observation.search_term,
            ingestion_run_id=None,
        )
        evidence_id = repo.save_market_evidence(**payload)
        if evidence_id is not None:
            written_count += 1

    return {
        "qualified_observation_count": qualified_count,
        "market_evidence_write_count": written_count,
    }


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

    profile_intents, terms, control_locations, known_company_keys = _load_runtime_state()
    if not terms:
        raise RuntimeError("No active Census search terms were found.")
    external_locations = _external_location_signals(profile_intents)
    if not external_locations:
        raise RuntimeError("No canonical Census market-location intent was found.")

    observed_at = datetime.now(UTC).isoformat()
    controls, control_telemetry = _run_control_sources(
        profile_intents=profile_intents,
        observed_at_utc=observed_at,
    )
    indexed, index_telemetry = _run_external_index_sources(
        provider=args.provider,
        provider_available=provider_available,
        external_requests_authorized=authority.external_requests_authorized,
        search_terms=terms,
        locations=external_locations,
        max_results=args.max_results,
        max_external_requests=args.max_external_requests,
        timeout_seconds=args.timeout_seconds,
        observed_at_utc=observed_at,
    )

    census = build_employer_discovery_census(
        [*controls, *indexed],
        known_company_keys=known_company_keys,
    )

    write_requested = bool(getattr(args, "write_market_evidence", False))
    if write_requested and not authority.external_requests_authorized:
        raise RuntimeError(
            "market_evidence persistence requires an authorized external-index flight"
        )
    persistence = {
        "qualified_observation_count": 0,
        "market_evidence_write_count": 0,
    }
    if write_requested:
        persistence = _persist_external_market_evidence(indexed)
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
            "location_signals": list(external_locations),
            "control_location_signals": list(control_locations),
            "external_location_signals": list(external_locations),
            "control_profile_count": len(profile_intents),
            "max_results": args.max_results,
            "max_external_requests": args.max_external_requests,
        },
        "baseline_candidate_count": len(known_company_keys),
        "control_telemetry": control_telemetry,
        "external_index_telemetry": index_telemetry,
        "metrics": _incremental_metrics(census),
        "writes": {
            "database": persistence["market_evidence_write_count"],
            "market_evidence": persistence["market_evidence_write_count"],
            "qualified_external_observations": persistence[
                "qualified_observation_count"
            ],
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
    parser.add_argument(
        "--write-market-evidence",
        action="store_true",
        help=(
            "Persist qualified external-index observations through the canonical "
            "market_evidence sensor boundary. Does not create jobs or candidates."
        ),
    )
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument(
        "--max-external-requests",
        type=int,
        default=50,
        help=(
            "Cost guard for paid external-index flights. The full active search "
            "raster is never truncated; the flight fails before provider calls "
            "when this budget is too small."
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.max_results <= 10:
        raise SystemExit("--max-results must be between 1 and 10")
    if args.max_external_requests < 1:
        raise SystemExit("--max-external-requests must be >= 1")
    if args.provider != "none" and not args.allow_paid_external_provider:
        raise SystemExit(
            "External provider selected without --allow-paid-external-provider"
        )
    if args.write_market_evidence and args.provider == "none":
        raise SystemExit(
            "--write-market-evidence requires an external provider flight"
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
    print(f"CONTROL_PROFILES={comparison['intent']['control_profile_count']}")
    print(f"SEARCH_TERMS={len(comparison['intent']['search_terms'])}")
    print(f"LOCATION_SIGNALS={len(comparison['intent']['location_signals'])}")
    print(f"OBSERVED_JOBS={report['observed_job_count']}")
    print(f"QUALIFYING_JOBS={report['qualifying_job_count']}")
    print(f"EMPLOYERS={report['employer_count']}")
    print(f"NOVEL_EMPLOYERS={report['novel_employer_count']}")
    print(
        "INCREMENTAL_NOVEL_EMPLOYERS="
        f"{metrics['primary_incremental_novel_employer_count']}"
    )
    print("DIRECT_BOARD_REQUESTS=0")
    print(f"DATABASE_WRITES={comparison['writes']['database']}")
    print(
        "MARKET_EVIDENCE_WRITES="
        f"{comparison['writes']['market_evidence']}"
    )
    print("BRONZE_WRITES=0")
    print("SILVER_WRITES=0")
    print("PRODUCT_WRITES=0")
    print("CANDIDATE_CREATION=0")
    print("CONNECTOR_ACTIVATION=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
