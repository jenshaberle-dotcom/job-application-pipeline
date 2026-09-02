"""Read-only live scout for Product V1 hard-filter source-evidence readiness.

This extends DEMO-001 source selection without creating Product V1 authority. Existing
code-backed connectors are executed once; their current source-provided vacancy evidence
is evaluated with the already-qualified deterministic Product V1 assessment extractor.
No Bronze/Silver/Gold/database writes, candidate-fit decision, ranking, provider call, or
application action is performed.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Mapping, Sequence

from scripts.run_demo_connector_source_scout import (
    CONNECTOR_SPECS,
    ConnectorSpec,
    _profile_for,
    _search_term,
    record_to_observation,
)
from scripts.run_product_v1_assessment_materialization_resilient import (
    _flatten_source_text,
)
from src.connectors.base import RawJobRecord
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)


DEFAULT_OUTPUT = Path("/tmp/demo_hard_filter_readiness_scout.json")


def _raw_mapping(record: RawJobRecord) -> Mapping[str, object]:
    return record.raw_data if isinstance(record.raw_data, Mapping) else {}


def _vacancy_text(record: RawJobRecord) -> str:
    raw = _raw_mapping(record)
    job = raw.get("job")
    if not isinstance(job, Mapping):
        return ""
    description = " ".join(str(job.get("description") or "").split())
    structured = " ".join(_flatten_source_text(raw.get("source_specific"))).strip()
    if structured:
        if description and description not in structured:
            return f"{description} {structured}".strip()
        return structured
    return description


def _structured_signal(record: RawJobRecord, key: str) -> str:
    raw = _raw_mapping(record)
    job = raw.get("job")
    if not isinstance(job, Mapping):
        return ""
    return " ".join(str(job.get(key) or "").split())


def assessment_readiness(record: RawJobRecord) -> dict[str, object]:
    observation = record_to_observation(record)
    detail_text = _vacancy_text(record)
    if not detail_text:
        return {
            **observation,
            "assessment_evidence_status": "missing_description",
            "assessment_unresolved_fields": [
                "employment_type",
                "required_languages",
                "weekly_hours",
                "work_model",
                "title_seniority",
                "requirements_seniority",
            ],
            "employment_type": "unknown",
            "required_languages": [],
            "weekly_hours_min": None,
            "weekly_hours_max": None,
            "work_model": "unknown",
            "title_seniority": "unknown",
            "requirements_seniority": "unknown",
            "structured_employment_type": _structured_signal(record, "employment_type"),
            "structured_schedule": _structured_signal(record, "schedule"),
            "hard_filter_source_evidence_complete": False,
        }

    try:
        evidence = extract_product_v1_assessment_evidence(
            description=detail_text,
            title=observation["title"],
            source_url=str(record.source_url or ""),
        )
    except ValueError as exc:
        return {
            **observation,
            "assessment_evidence_status": f"invalid:{exc}",
            "assessment_unresolved_fields": [],
            "structured_employment_type": _structured_signal(record, "employment_type"),
            "structured_schedule": _structured_signal(record, "schedule"),
            "hard_filter_source_evidence_complete": False,
        }

    hours_observed = evidence.weekly_hours_min is not None or evidence.weekly_hours_max is not None
    source_complete = (
        evidence.employment_type != "unknown"
        and bool(evidence.required_languages)
        and hours_observed
    )
    return {
        **observation,
        "assessment_evidence_status": "ready",
        "assessment_unresolved_fields": list(evidence.unresolved_fields),
        "employment_type": evidence.employment_type,
        "required_languages": list(evidence.required_languages),
        "weekly_hours_min": evidence.weekly_hours_min,
        "weekly_hours_max": evidence.weekly_hours_max,
        "work_model": evidence.work_model,
        "title_seniority": evidence.title_seniority,
        "requirements_seniority": evidence.requirements_seniority,
        "structured_employment_type": _structured_signal(record, "employment_type"),
        "structured_schedule": _structured_signal(record, "schedule"),
        "hard_filter_source_evidence_complete": source_complete,
    }


def run_connector(spec: ConnectorSpec) -> dict[str, object]:
    started = datetime.now(UTC)
    try:
        connector = spec.factory()
        records, final_url = connector.fetch_jobs(
            _profile_for(spec.source_name),
            _search_term(),
        )
        jobs = [assessment_readiness(record) for record in records]
        status = "success"
        error = None
    except Exception as exc:  # noqa: BLE001 - health evidence must remain per source
        jobs = []
        final_url = None
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
    finished = datetime.now(UTC)

    strong = [
        row
        for row in jobs
        if row.get("role_profile_match") is True
        and row.get("location_signal_match") is True
    ]
    source_ready = [
        row for row in strong if row.get("hard_filter_source_evidence_complete") is True
    ]
    return {
        "source_name": spec.source_name,
        "provenance": spec.provenance,
        "status": status,
        "error": error,
        "final_url": final_url,
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "observed_job_count": len(jobs),
        "profile_location_match_count": len(strong),
        "hard_filter_source_ready_count": len(source_ready),
        "jobs": jobs,
    }


def build_report(specs: Sequence[ConnectorSpec] = CONNECTOR_SPECS) -> dict[str, object]:
    sources = [run_connector(spec) for spec in specs]
    strong = [
        row
        for source in sources
        for row in source["jobs"]
        if isinstance(row, Mapping)
        and row.get("role_profile_match") is True
        and row.get("location_signal_match") is True
    ]
    source_ready = [
        row for row in strong if row.get("hard_filter_source_evidence_complete") is True
    ]
    healthy = [source for source in sources if source["status"] == "success"]
    return {
        "schema": "job_application_pipeline.demo_hard_filter_readiness_scout.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "purpose": "source_evidence_selection_only_not_product_authority",
        "summary": {
            "connector_count": len(sources),
            "healthy_connector_count": len(healthy),
            "observed_job_count": sum(int(source["observed_job_count"]) for source in sources),
            "profile_location_match_count": len(strong),
            "hard_filter_source_ready_count": len(source_ready),
        },
        "sources": sources,
        "profile_location_matches": strong,
        "hard_filter_source_ready_matches": source_ready,
        "boundaries": {
            "existing_connectors_or_targets_only": True,
            "network_gets": True,
            "database_reads": False,
            "database_writes": False,
            "product_assessment_writes": False,
            "hard_filter_authority": False,
            "candidate_fact_reads": False,
            "capability_fit_authority": False,
            "ranking_or_top5_writes": False,
            "provider_or_llm_requests": 0,
            "application_or_submission_actions": False,
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
    print("DEMO HARD-FILTER READINESS SCOUT")
    print("============================================")
    print(f"CONNECTORS={summary['connector_count']}")
    print(f"HEALTHY_CONNECTORS={summary['healthy_connector_count']}")
    print(f"OBSERVED_JOBS={summary['observed_job_count']}")
    print(f"PROFILE_LOCATION_MATCHES={summary['profile_location_match_count']}")
    print(f"HARD_FILTER_SOURCE_READY={summary['hard_filter_source_ready_count']}")
    for source in report["sources"]:
        print(
            "SOURCE="
            f"{source['source_name']}|{source['status']}|jobs={source['observed_job_count']}|"
            f"profile_location={source['profile_location_match_count']}|"
            f"source_ready={source['hard_filter_source_ready_count']}"
        )
        if source["error"]:
            print(f"SOURCE_ERROR={source['source_name']}|{source['error']}")
    for row in report["profile_location_matches"]:
        print(
            "CANDIDATE_EVIDENCE="
            f"{row['source_name']}|ready={str(row['hard_filter_source_evidence_complete']).lower()}|"
            f"employment={row.get('employment_type')}|"
            f"languages={','.join(row.get('required_languages') or []) or '-'}|"
            f"hours={row.get('weekly_hours_min')}-{row.get('weekly_hours_max')}|"
            f"structured_employment={row.get('structured_employment_type') or '-'}|"
            f"structured_schedule={row.get('structured_schedule') or '-'}|"
            f"{row['company_name']}|{row['title']}|{row['location']}"
        )
    print("DATABASE_WRITES=0")
    print("HARD_FILTER_AUTHORITY=false")
    print(f"artifact={args.output.resolve()}")
    print("DEMO_HARD_FILTER_READINESS_SCOUT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
