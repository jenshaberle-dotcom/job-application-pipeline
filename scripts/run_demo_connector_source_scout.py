"""Bounded live source scout for the Product V1 demo.

The scout executes only existing code-backed employer-origin connectors and already-
known ATS targets and reports what they expose *now*. It does not write Bronze,
Silver, Gold, activate a source, call an LLM/provider, or create ranking authority.

Profile proximity deliberately reuses Product V1's existing role-title classifier.
The scout is only source-selection evidence for the demo; authoritative ranking still
belongs to Product V1 after normal ingestion and assessment.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Callable, Mapping, Sequence

from src.connectors.accompio import AccompioConnector
from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.computacenter import ComputacenterConnector
from src.connectors.enercity import EnercityConnector
from src.connectors.finanz_informatik import FinanzInformatikConnector
from src.connectors.hdi import HdiConnector
from src.connectors.personio import PersonioConnector
from src.connectors.successfactors import SuccessFactorsConnector
from src.search_intelligence.product_v1_contenders import classify_role_title, normalize_text


DEFAULT_OUTPUT = Path("/tmp/demo_connector_source_scout.json")
PROFILE_NAME = "demo_product_v1_hannover"
SEARCH_TERM = "machine learning data platform reliability engineer"
LOCATION_SIGNALS = (
    "hannover",
    "hanover",
    "remote",
    "hybrid",
    "homeoffice",
    "deutschland",
    "germany",
    "bundesweit",
)


@dataclass(frozen=True)
class ConnectorSpec:
    source_name: str
    factory: Callable[[], JobSourceConnector]
    provenance: str = "code_backed_employer_origin"


def _personio(target_key: str) -> Callable[[], JobSourceConnector]:
    return lambda: PersonioConnector(target_key=target_key)


CONNECTOR_SPECS: tuple[ConnectorSpec, ...] = (
    # Current explicit employer-origin connector registry.
    ConnectorSpec("hdi:hannover", HdiConnector),
    ConnectorSpec("enercity:discovery", EnercityConnector),
    ConnectorSpec("finanz_informatik:hannover", FinanzInformatikConnector),
    ConnectorSpec("computacenter:discovery", ComputacenterConnector),
    ConnectorSpec("accompio:discovery", AccompioConnector),
    # Existing reviewed/previously active ATS source targets from repository truth.
    ConnectorSpec(
        "successfactors:eon_germany",
        lambda: SuccessFactorsConnector(target_key="eon_germany"),
        provenance="existing_controlled_ats_target",
    ),
    ConnectorSpec(
        "personio:eraneos",
        _personio("eraneos"),
        provenance="existing_source_target",
    ),
    ConnectorSpec(
        "personio:1komma5grad",
        _personio("1komma5grad"),
        provenance="existing_source_target",
    ),
    ConnectorSpec(
        "personio:schluetersche-mediengruppe",
        _personio("schluetersche-mediengruppe"),
        provenance="existing_source_target",
    ),
    ConnectorSpec(
        "personio:it-p",
        _personio("it-p"),
        provenance="existing_source_target",
    ),
    ConnectorSpec(
        "personio:otl-akademie",
        _personio("otl-akademie"),
        provenance="existing_source_target",
    ),
)


def _first_text(raw: Mapping[str, object], *paths: tuple[str, str]) -> str:
    for parent_key, child_key in paths:
        parent = raw.get(parent_key)
        if not isinstance(parent, Mapping):
            continue
        value = parent.get(child_key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _structured_locations(raw: Mapping[str, object]) -> list[str]:
    job = raw.get("job")
    if not isinstance(job, Mapping):
        return []
    locations = job.get("locations")
    if not isinstance(locations, list):
        return []
    result: list[str] = []
    for location in locations:
        if not isinstance(location, Mapping):
            continue
        city = str(location.get("city") or "").strip()
        country = str(location.get("country_code") or "").strip()
        text = ", ".join(part for part in (city, country) if part)
        if text and text not in result:
            result.append(text)
    return result


def _location_signals(value: str) -> list[str]:
    normalized = normalize_text(value)
    return [signal for signal in LOCATION_SIGNALS if normalize_text(signal) in normalized]


def record_to_observation(record: RawJobRecord) -> dict[str, object]:
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    title = _first_text(raw, ("job", "title"), ("result_card", "title"))
    company = _first_text(raw, ("job", "company_name"), ("result_card", "company_name"))
    raw_location = _first_text(raw, ("job", "location"), ("result_card", "location"))
    structured_locations = _structured_locations(raw)
    location = " | ".join(part for part in (raw_location, *structured_locations) if part)
    role = classify_role_title(title)
    location_signals = _location_signals(location)

    return {
        "source_name": record.source_name,
        "external_job_id": record.external_job_id,
        "source_url": record.source_url,
        "title": title,
        "company_name": company,
        "location": location,
        "role_profile_match": role is not None,
        "role_tier": role.tier if role else None,
        "role_family": role.family if role else None,
        "role_signals": list(role.signals) if role else [],
        "location_signal_match": bool(location_signals),
        "location_signals": location_signals,
    }


def _profile_for(source_name: str) -> SearchProfile:
    return SearchProfile(
        id=0,
        profile_name=PROFILE_NAME,
        source_name=source_name,
        search_location="Hannover",
        search_radius_km=50,
        offer_type=1,
        page_size=25,
    )


def _search_term() -> SearchTerm:
    return SearchTerm(search_term=SEARCH_TERM, id=None)


def run_connector(spec: ConnectorSpec) -> dict[str, object]:
    started = datetime.now(UTC)
    try:
        connector = spec.factory()
        records, final_url = connector.fetch_jobs(
            _profile_for(spec.source_name),
            _search_term(),
        )
        observations = [record_to_observation(record) for record in records]
        profile_matches = [row for row in observations if row["role_profile_match"] is True]
        profile_location_matches = [
            row
            for row in profile_matches
            if row["location_signal_match"] is True
        ]
        status = "success"
        error = None
    except Exception as exc:  # noqa: BLE001 - source health must be reported per connector
        observations = []
        profile_matches = []
        profile_location_matches = []
        final_url = None
        status = "error"
        error = f"{type(exc).__name__}: {exc}"

    finished = datetime.now(UTC)
    return {
        "source_name": spec.source_name,
        "provenance": spec.provenance,
        "status": status,
        "error": error,
        "final_url": final_url,
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "observed_job_count": len(observations),
        "profile_match_count": len(profile_matches),
        "profile_and_location_signal_count": len(profile_location_matches),
        "jobs": observations,
    }


def build_report(specs: Sequence[ConnectorSpec] = CONNECTOR_SPECS) -> dict[str, object]:
    sources = [run_connector(spec) for spec in specs]
    profile_matches = [
        row
        for source in sources
        for row in source["jobs"]
        if isinstance(row, Mapping) and row.get("role_profile_match") is True
    ]
    strong_demo_candidates = [
        row
        for row in profile_matches
        if row.get("location_signal_match") is True
    ]
    healthy_sources = [source for source in sources if source["status"] == "success"]
    sources_with_profile_matches = [
        source
        for source in sources
        if int(source["profile_match_count"]) > 0
    ]

    return {
        "schema": "job_application_pipeline.demo_connector_source_scout.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "purpose": "source_selection_evidence_only_not_product_ranking",
        "profile": {
            "target": "Machine Learning Engineer with strong Data Engineering and Reliability focus",
            "location": "Hannover / remote Germany",
            "role_classifier": "src.search_intelligence.product_v1_contenders.classify_role_title",
        },
        "summary": {
            "connector_count": len(sources),
            "healthy_connector_count": len(healthy_sources),
            "observed_job_count": sum(int(source["observed_job_count"]) for source in sources),
            "profile_match_count": len(profile_matches),
            "profile_and_location_signal_count": len(strong_demo_candidates),
            "sources_with_profile_matches": len(sources_with_profile_matches),
        },
        "sources": sources,
        "profile_matches": profile_matches,
        "profile_and_location_signal_matches": strong_demo_candidates,
        "boundaries": {
            "existing_connectors_or_targets_only": True,
            "network_gets": True,
            "database_reads": False,
            "database_writes": False,
            "bronze_writes": False,
            "silver_writes": False,
            "gold_or_ranking_writes": False,
            "source_activation": False,
            "provider_or_llm_requests": 0,
            "application_writes": 0,
            "submission_actions": 0,
            "demo_ranking_created": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    summary = report["summary"]
    print("============================================")
    print("DEMO CONNECTOR SOURCE SCOUT")
    print("============================================")
    print(f"CONNECTORS={summary['connector_count']}")
    print(f"HEALTHY_CONNECTORS={summary['healthy_connector_count']}")
    print(f"OBSERVED_JOBS={summary['observed_job_count']}")
    print(f"PROFILE_MATCHES={summary['profile_match_count']}")
    print(f"PROFILE_LOCATION_MATCHES={summary['profile_and_location_signal_count']}")
    print(f"SOURCES_WITH_PROFILE_MATCHES={summary['sources_with_profile_matches']}")
    for source in report["sources"]:
        print(
            "SOURCE="
            f"{source['source_name']}|{source['status']}|"
            f"jobs={source['observed_job_count']}|"
            f"profile={source['profile_match_count']}|"
            f"profile_location={source['profile_and_location_signal_count']}"
        )
        if source["error"]:
            print(f"SOURCE_ERROR={source['source_name']}|{source['error']}")
    for row in report["profile_and_location_signal_matches"]:
        print(
            "DEMO_CANDIDATE="
            f"{row['source_name']}|{row['role_tier']}|{row['company_name']}|"
            f"{row['title']}|{row['location']}|{row['source_url']}"
        )
    print("DATABASE_WRITES=0")
    print("PRODUCT_RANKING_WRITES=0")
    print(f"artifact={args.output.resolve()}")
    print("DEMO_CONNECTOR_SOURCE_SCOUT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
