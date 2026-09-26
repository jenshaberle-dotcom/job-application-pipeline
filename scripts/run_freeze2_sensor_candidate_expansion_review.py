"""Build the Freeze-II S0.6 candidate-expansion review from a sensor artifact.

The input is the bounded LinkedIn/Indeed sensor JSON. This step performs no
external provider request and no database mutation. It attributes only explicit
company signals, groups them by conservative company key, compares them with the
current Employer-Origin candidate population and delegates the actual decision
logic to the existing candidate_expansion review module.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.candidate_expansion import (
    KnownCandidate,
    MarketCompanyObservation,
    build_candidate_expansion_review,
)
from src.search_intelligence.conservative_market_sensors import (
    extract_observed_company_signal,
)


SCHEMA = "job_application_pipeline.freeze2_sensor_candidate_expansion_review.v1"


def _query_intent(sensor_payload: Mapping[str, Any]) -> dict[str, tuple[str, str | None]]:
    result: dict[str, tuple[str, str | None]] = {}
    for item in sensor_payload.get("queries") or []:
        if not isinstance(item, Mapping):
            continue
        query = str(item.get("query") or "")
        if not query:
            continue
        result[query] = (
            str(item.get("search_term") or ""),
            str(item.get("location_signal")) if item.get("location_signal") is not None else None,
        )
    return result


def _load_known_candidates() -> list[KnownCandidate]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT id, company_key, company_name, status, source_family_candidate
                    FROM employer_origin_source_candidates
                    ORDER BY id
                    """
                )
                rows = cur.fetchall()
        conn.rollback()
    return [
        KnownCandidate(
            candidate_id=int(row["id"]),
            company_key=str(row["company_key"] or ""),
            company_name=str(row["company_name"] or ""),
            status=str(row["status"] or ""),
            source_family_candidate=(
                str(row["source_family_candidate"])
                if row["source_family_candidate"] is not None
                else None
            ),
        )
        for row in rows
    ]


def _build_company_observations(
    report: Mapping[str, Any],
) -> tuple[list[MarketCompanyObservation], dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    unattributed = 0
    attributed = 0
    rule_counts: Counter[str] = Counter()
    sensor_counts: Counter[str] = Counter()

    sensors = report.get("sensors") or {}
    if not isinstance(sensors, Mapping):
        sensors = {}

    for sensor, sensor_payload_obj in sensors.items():
        if not isinstance(sensor_payload_obj, Mapping):
            continue
        sensor_payload = sensor_payload_obj
        intent = _query_intent(sensor_payload)
        for observation_obj in sensor_payload.get("observations") or []:
            if not isinstance(observation_obj, Mapping):
                continue
            observation = observation_obj
            company = str(observation.get("observed_company_signal") or "").strip()
            rule = str(observation.get("company_signal_rule") or "").strip() or None
            if not company:
                company, rule = extract_observed_company_signal(
                    sensor=str(sensor),
                    title=observation.get("title_signal"),
                    snippet=observation.get("snippet_signal"),
                )
            if not company:
                unattributed += 1
                continue

            company_key = normalize_company_key(company)
            if not company_key:
                unattributed += 1
                continue

            attributed += 1
            sensor_counts[str(sensor)] += 1
            if rule:
                rule_counts[rule] += 1

            query = str(observation.get("query") or "")
            search_term = str(observation.get("search_term") or "")
            location_signal = (
                str(observation.get("location_signal"))
                if observation.get("location_signal") is not None
                else None
            )
            if not search_term and query in intent:
                search_term, inferred_location = intent[query]
                if location_signal is None:
                    location_signal = inferred_location

            state = groups.setdefault(
                company_key,
                {
                    "company_names": Counter(),
                    "sensors": set(),
                    "search_terms": set(),
                    "locations": set(),
                    "titles": set(),
                    "latest_observed_at": None,
                    "count": 0,
                    "rules": Counter(),
                },
            )
            state["company_names"][company] += 1
            state["sensors"].add(str(sensor))
            if search_term:
                state["search_terms"].add(search_term)
            if location_signal:
                state["locations"].add(location_signal)
            title = str(observation.get("title_signal") or "").strip()
            if title:
                state["titles"].add(title)
            observed_at = str(observation.get("observed_at_utc") or "").strip() or None
            if observed_at and (
                state["latest_observed_at"] is None
                or observed_at > state["latest_observed_at"]
            ):
                state["latest_observed_at"] = observed_at
            state["count"] += 1
            if rule:
                state["rules"][rule] += 1

    observations: list[MarketCompanyObservation] = []
    grouped_evidence: list[dict[str, Any]] = []
    for company_key, state in sorted(groups.items()):
        company_name = sorted(
            state["company_names"].items(),
            key=lambda item: (-item[1], -len(item[0]), item[0].casefold()),
        )[0][0]
        source_name = "+".join(sorted(state["sensors"]))
        observations.append(
            MarketCompanyObservation(
                company_key=company_key,
                company_name=company_name,
                source_name=source_name,
                observation_count=int(state["count"]),
                latest_observed_at=state["latest_observed_at"],
                search_terms=tuple(sorted(state["search_terms"])),
                sample_titles=tuple(sorted(state["titles"])),
            )
        )
        grouped_evidence.append(
            {
                "company_key": company_key,
                "company_name": company_name,
                "source_name": source_name,
                "observation_count": int(state["count"]),
                "search_terms": sorted(state["search_terms"]),
                "location_signals": sorted(state["locations"]),
                "sample_titles": sorted(state["titles"]),
                "company_signal_rules": dict(sorted(state["rules"].items())),
                "latest_observed_at": state["latest_observed_at"],
            }
        )

    metadata = {
        "total_sensor_observation_count": attributed + unattributed,
        "attributed_observation_count": attributed,
        "unattributed_observation_count": unattributed,
        "attributed_company_count": len(observations),
        "attributed_sensor_counts": dict(sorted(sensor_counts.items())),
        "company_signal_rule_counts": dict(sorted(rule_counts.items())),
        "grouped_company_evidence": grouped_evidence,
    }
    return observations, metadata


def build_report(sensor_report: Mapping[str, Any]) -> dict[str, Any]:
    observations, metadata = _build_company_observations(sensor_report)
    known_candidates = _load_known_candidates()
    review = build_candidate_expansion_review(
        observations,
        known_candidates,
        source_name="freeze2_linkedin_indeed",
        min_create_observations=2,
        min_review_observations=1,
    )

    return {
        "schema": SCHEMA,
        "sensor_report_schema": sensor_report.get("schema"),
        "sensor_provider": sensor_report.get("provider"),
        "baseline_candidate_count": len(known_candidates),
        "summary": {
            **metadata,
            "review_company_count": review.company_count,
            "review_create_recommended_count": review.create_recommended_count,
            "review_manual_review_count": review.manual_review_count,
            "review_already_known_count": review.already_known_count,
            "review_insufficient_evidence_count": review.insufficient_evidence_count,
            "review_suppressed_count": review.suppressed_count,
        },
        "review": asdict(review),
        "boundary": {
            "external_provider_requests": 0,
            "database_writes": 0,
            "candidate_creation": 0,
            "connector_registration": 0,
            "source_activation": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "product_authority": 0,
            "aggregator_url_as_origin_authority": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sensor-report", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/freeze2-sensor-candidate-expansion-review.json"),
    )
    args = parser.parse_args()

    sensor_report = json.loads(args.sensor_report.read_text(encoding="utf-8"))
    report = build_report(sensor_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("============================================")
    print("FREEZE-II S0.6 SENSOR CANDIDATE EXPANSION REVIEW")
    print("============================================")
    print(f"BASELINE_CANDIDATES={report['baseline_candidate_count']}")
    print(f"SENSOR_OBSERVATIONS={summary['total_sensor_observation_count']}")
    print(f"ATTRIBUTED_OBSERVATIONS={summary['attributed_observation_count']}")
    print(f"UNATTRIBUTED_OBSERVATIONS={summary['unattributed_observation_count']}")
    print(f"ATTRIBUTED_COMPANIES={summary['attributed_company_count']}")
    print(f"CREATE_RECOMMENDED={summary['review_create_recommended_count']}")
    print(f"MANUAL_REVIEW={summary['review_manual_review_count']}")
    print(f"ALREADY_KNOWN={summary['review_already_known_count']}")
    print(f"INSUFFICIENT={summary['review_insufficient_evidence_count']}")
    print(f"SUPPRESSED={summary['review_suppressed_count']}")
    print("PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("CANDIDATE_CREATION=0")
    print("SOURCE_ACTIVATION=0")
    print(f"artifact={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
