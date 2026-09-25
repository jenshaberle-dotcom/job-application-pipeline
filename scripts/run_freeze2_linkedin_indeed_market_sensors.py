"""Run bounded LinkedIn + Indeed discovery-only market sensors.

Default mode is provider=none and performs zero external requests. A real Tavily
probe requires an explicit --provider tavily and TAVILY_API_KEY. The script reads
current active sensor search intent from PostgreSQL under a read-only transaction
and emits minimal discovery evidence only.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_source_discovery_agent import (
    _is_missing_or_placeholder_secret,
    load_local_env_file,
    tavily_search,
)
from src.config import get_database_config
from src.search_intelligence.conservative_market_sensors import (
    BOUNDARY,
    SENSOR_PLATFORMS,
    accept_provider_result,
    build_sensor_queries,
    deduplicate_observations,
)


DEFAULT_INTENT_SOURCES = ("bundesagentur_fuer_arbeit", "stepstone")


def _load_current_search_intent(
    *,
    max_terms: int,
    max_locations: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
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
                    (list(DEFAULT_INTENT_SOURCES), max_terms),
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
                    (list(DEFAULT_INTENT_SOURCES), max_locations),
                )
                locations = tuple(
                    str(row["search_location"]).strip()
                    for row in cur.fetchall()
                    if str(row.get("search_location") or "").strip()
                )
        conn.rollback()
    return terms, locations


def _status(
    *,
    provider: str,
    provider_available: bool,
    query_count: int,
    observations: int,
) -> str:
    if provider == "none":
        return "plan_only"
    if not provider_available:
        return "provider_unavailable"
    if query_count == 0:
        return "no_search_intent"
    if observations == 0:
        return "zero_yield"
    return "observations"


def run(args: argparse.Namespace) -> dict[str, object]:
    load_local_env_file()
    terms, locations = _load_current_search_intent(
        max_terms=args.max_terms,
        max_locations=args.max_locations,
    )

    requested_sensors = tuple(dict.fromkeys(args.sensor or SENSOR_PLATFORMS))
    provider_available = (
        args.provider == "none"
        or not _is_missing_or_placeholder_secret(os.getenv("TAVILY_API_KEY"))
    )
    observed_at = datetime.now(UTC).isoformat()

    report_sensors: dict[str, object] = {}
    total_requests = 0
    total_observations = 0

    for sensor in requested_sensors:
        queries = build_sensor_queries(
            sensor=sensor,
            search_terms=terms,
            location_signals=locations,
            max_terms=args.max_terms,
            max_locations=args.max_locations,
        )
        accepted = []
        rejected_count = 0
        request_count = 0

        if args.provider == "tavily" and provider_available:
            for plan in queries:
                request_count += 1
                total_requests += 1
                rows = tavily_search(
                    plan.query,
                    max_results=args.max_results,
                    timeout_seconds=args.timeout_seconds,
                    search_depth="basic",
                )
                for row in rows:
                    observation = accept_provider_result(
                        sensor=sensor,
                        provider=row.provider,
                        query=plan.query,
                        url=row.url,
                        title=row.title,
                        snippet=row.snippet,
                        observed_at_utc=observed_at,
                    )
                    if observation is None:
                        rejected_count += 1
                    else:
                        accepted.append(observation)

        unique = deduplicate_observations(accepted)
        total_observations += len(unique)
        report_sensors[sensor] = {
            "status": _status(
                provider=args.provider,
                provider_available=provider_available,
                query_count=len(queries),
                observations=len(unique),
            ),
            "query_count": len(queries),
            "provider_request_count": request_count,
            "accepted_observation_count": len(unique),
            "rejected_provider_result_count": rejected_count,
            "queries": [
                {
                    "search_term": plan.search_term,
                    "location_signal": plan.location_signal,
                    "query": plan.query,
                }
                for plan in queries
            ],
            "observations": [item.as_dict() for item in unique],
        }

    return {
        "schema": "job_application_pipeline.freeze2_market_sensor_probe.v1",
        "mode": "discovery_only",
        "provider": args.provider,
        "provider_available": provider_available,
        "intent": {
            "search_terms": list(terms),
            "location_signals": list(locations),
            "intent_sources": list(DEFAULT_INTENT_SOURCES),
        },
        "sensors": report_sensors,
        "summary": {
            "sensor_count": len(requested_sensors),
            "provider_request_count": total_requests,
            "accepted_observation_count": total_observations,
        },
        "boundary": dict(BOUNDARY),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sensor",
        action="append",
        choices=SENSOR_PLATFORMS,
        help="Sensor to run. Repeatable. Defaults to LinkedIn + Indeed.",
    )
    parser.add_argument("--provider", choices=("none", "tavily"), default="none")
    parser.add_argument("--max-terms", type=int, default=3)
    parser.add_argument("--max-locations", type=int, default=2)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/freeze2-linkedin-indeed-market-sensors.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_terms < 1 or args.max_terms > 10:
        raise SystemExit("--max-terms must be between 1 and 10")
    if args.max_locations < 0 or args.max_locations > 5:
        raise SystemExit("--max-locations must be between 0 and 5")
    if args.max_results < 1 or args.max_results > 10:
        raise SystemExit("--max-results must be between 1 and 10")

    report = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("FREEZE-II LINKEDIN + INDEED MARKET SENSORS")
    print("============================================")
    print(f"PROVIDER={report['provider']}")
    print(f"PROVIDER_AVAILABLE={report['provider_available']}")
    print(
        "INTENT_TERMS="
        + json.dumps(report["intent"]["search_terms"], ensure_ascii=False)
    )
    print(
        "INTENT_LOCATIONS="
        + json.dumps(report["intent"]["location_signals"], ensure_ascii=False)
    )
    for sensor, payload in report["sensors"].items():
        print(
            f"SENSOR={sensor}"
            f"|status={payload['status']}"
            f"|queries={payload['query_count']}"
            f"|requests={payload['provider_request_count']}"
            f"|observations={payload['accepted_observation_count']}"
            f"|rejected={payload['rejected_provider_result_count']}"
        )
    print(
        "TOTAL_PROVIDER_REQUESTS="
        f"{report['summary']['provider_request_count']}"
    )
    print(
        "TOTAL_ACCEPTED_OBSERVATIONS="
        f"{report['summary']['accepted_observation_count']}"
    )
    print("DATABASE_WRITES=0")
    print("BRONZE_WRITES=0")
    print("SILVER_WRITES=0")
    print("PRODUCT_AUTHORITY=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
