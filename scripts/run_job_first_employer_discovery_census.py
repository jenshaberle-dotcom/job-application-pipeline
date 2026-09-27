"""Bounded read-only job-first Employer Discovery Census flight."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.registry import SourceRole, build_default_connector_registry
from src.search_intelligence.employer_discovery_census import (
    build_employer_discovery_census,
)
from src.search_intelligence.employer_discovery_census_adapter import (
    market_observation_from_raw_record,
)


DEFAULT_OUTPUT = Path(".runtime/census/employer_discovery_census.json")
DEFAULT_SOURCES = ("bundesagentur_fuer_arbeit", "stepstone")


def run_census_flight(
    *,
    search_terms: list[str],
    location: str,
    radius_km: int,
    page_size: int,
    known_company_keys: set[str] | None = None,
) -> dict[str, object]:
    """Run bounded registered sensors and return evidence only."""
    registry = build_default_connector_registry()
    observations = []
    source_errors: dict[str, str] = {}

    for source_name in DEFAULT_SOURCES:
        if registry.role_for(source_name) != SourceRole.SENSOR:
            raise RuntimeError(f"{source_name} is not registered as a sensor")
        connector = registry.create(source_name)
        profile = SearchProfile(
            id=0,
            profile_name="job_first_employer_discovery_census",
            source_name=source_name,
            search_location=location,
            search_radius_km=radius_km,
            offer_type=1,
            page_size=page_size,
        )
        for term in search_terms:
            try:
                records, _ = connector.fetch_jobs(profile, SearchTerm(term))
            except Exception as exc:  # evidence flight records source failure; it never retries
                source_errors[source_name] = f"{type(exc).__name__}: {exc}"
                break
            observations.extend(
                market_observation_from_raw_record(record) for record in records
            )

    report = build_employer_discovery_census(
        observations,
        known_company_keys=known_company_keys or set(),
    )
    report["flight"] = {
        "mode": "read_only_evidence",
        "sources_attempted": list(DEFAULT_SOURCES),
        "source_errors": source_errors,
        "search_terms": search_terms,
        "location": location,
        "radius_km": radius_km,
        "page_size_per_term": page_size,
        "writes": {
            "database": 0,
            "bronze": 0,
            "silver": 0,
            "product": 0,
            "candidate": 0,
            "connector": 0,
        },
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--term", action="append", dest="terms", required=True)
    parser.add_argument("--location", default="Hannover")
    parser.add_argument("--radius-km", type=int, default=50)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.radius_km < 0 or not 1 <= args.page_size <= 25:
        raise SystemExit("radius-km must be >= 0 and page-size must be 1..25")
    report = run_census_flight(
        search_terms=args.terms,
        location=args.location,
        radius_km=args.radius_km,
        page_size=args.page_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
