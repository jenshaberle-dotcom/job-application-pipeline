"""Bounded live proof for demo connector sources with concrete job details.

This runner reuses only the existing DEMO-001 connector registry. It performs live
connector reads, but no DB/source/scheduler/provider/application writes. A source is
`detail_proven` only when at least one returned job has a concrete HTTPS job URL and
substantive detail text from the connector payload. Profile/location proximity is
reported separately and never creates ranking or application authority.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from scripts.run_demo_connector_source_scout import (
    CONNECTOR_SPECS,
    ConnectorSpec,
    _profile_for,
    _search_term,
    record_to_observation,
)
from src.connectors.base import RawJobRecord


DEFAULT_OUTPUT = Path("/tmp/demo_live_detail_tranche.json")
MIN_DETAIL_CHARS = 120
_DETAIL_KEYS = (
    "description",
    "beschreibung",
    "content",
    "job_description",
    "description_text",
    "body_text",
    "page_text",
    "details",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _detail_text(record: RawJobRecord) -> str:
    raw = record.raw_data if isinstance(record.raw_data, Mapping) else {}
    candidates: list[str] = []
    for parent_name in ("job", "detail_evidence"):
        parent = raw.get(parent_name)
        if not isinstance(parent, Mapping):
            continue
        for key in _DETAIL_KEYS:
            value = parent.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(_text(value))
    for key in _DETAIL_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(_text(value))
    return max(candidates, key=len, default="")


def _https_job_url(record: RawJobRecord) -> bool:
    parsed = urlsplit(str(record.source_url or ""))
    return parsed.scheme == "https" and bool(parsed.netloc) and bool(parsed.path.strip("/"))


def qualify_record(record: RawJobRecord) -> dict[str, object]:
    observation = record_to_observation(record)
    detail_text = _detail_text(record)
    detail_proven = _https_job_url(record) and len(detail_text) >= MIN_DETAIL_CHARS
    return {
        **observation,
        "detail_proven": detail_proven,
        "detail_chars": len(detail_text),
        "detail_sha_material_present": bool(detail_text),
    }


def run_source(spec: ConnectorSpec) -> dict[str, object]:
    started = datetime.now(UTC)
    try:
        connector = spec.factory()
        records, final_url = connector.fetch_jobs(
            _profile_for(spec.source_name),
            _search_term(),
        )
        rows = [qualify_record(record) for record in records]
        error = None
        status = "success"
    except Exception as exc:  # noqa: BLE001 - every source must report independently
        rows = []
        final_url = None
        error = f"{type(exc).__name__}: {exc}"
        status = "error"
    finished = datetime.now(UTC)

    detail_rows = [row for row in rows if row["detail_proven"] is True]
    profile_rows = [row for row in detail_rows if row["role_profile_match"] is True]
    target_rows = [
        row for row in profile_rows if row["location_signal_match"] is True
    ]
    return {
        "source_name": spec.source_name,
        "provenance": spec.provenance,
        "status": status,
        "error": error,
        "final_url": final_url,
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "observed_job_count": len(rows),
        "detail_proven_job_count": len(detail_rows),
        "profile_detail_job_count": len(profile_rows),
        "profile_location_detail_job_count": len(target_rows),
        "detail_proven": bool(detail_rows),
        "demo_target_proven": bool(target_rows),
        "jobs": rows,
    }


def build_report(specs: Sequence[ConnectorSpec] = CONNECTOR_SPECS) -> dict[str, object]:
    sources = [run_source(spec) for spec in specs]
    healthy = [row for row in sources if row["status"] == "success"]
    detail_proven = [row for row in sources if row["detail_proven"] is True]
    demo_target = [row for row in sources if row["demo_target_proven"] is True]
    target_jobs = [
        job
        for source in sources
        for job in source["jobs"]
        if isinstance(job, Mapping)
        and job.get("detail_proven") is True
        and job.get("role_profile_match") is True
        and job.get("location_signal_match") is True
    ]
    return {
        "schema": "job_application_pipeline.demo_live_detail_tranche.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "profile": "Machine Learning Engineer + Data Engineering + AI/Data Reliability; Hannover or remote Germany",
        "summary": {
            "connector_count": len(sources),
            "healthy_connector_count": len(healthy),
            "detail_proven_source_count": len(detail_proven),
            "demo_target_proven_source_count": len(demo_target),
            "observed_job_count": sum(int(row["observed_job_count"]) for row in sources),
            "detail_proven_job_count": sum(int(row["detail_proven_job_count"]) for row in sources),
            "profile_location_detail_job_count": len(target_jobs),
        },
        "recommended_demo_sources": [row["source_name"] for row in demo_target],
        "sources": sources,
        "profile_location_detail_jobs": target_jobs,
        "boundaries": {
            "network_reads": True,
            "database_reads": False,
            "database_writes": False,
            "source_activation": False,
            "scheduler_mutation": False,
            "provider_or_llm_requests": 0,
            "ranking_or_top5_authority": False,
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
    print("DEMO LIVE DETAIL TRANCHE")
    print("============================================")
    print(f"CONNECTORS={summary['connector_count']}")
    print(f"HEALTHY={summary['healthy_connector_count']}")
    print(f"DETAIL_PROVEN_SOURCES={summary['detail_proven_source_count']}")
    print(f"DEMO_TARGET_PROVEN_SOURCES={summary['demo_target_proven_source_count']}")
    print(f"OBSERVED_JOBS={summary['observed_job_count']}")
    print(f"DETAIL_PROVEN_JOBS={summary['detail_proven_job_count']}")
    print(f"PROFILE_LOCATION_DETAIL_JOBS={summary['profile_location_detail_job_count']}")
    print("RECOMMENDED_SOURCES=" + ",".join(report["recommended_demo_sources"]))
    for source in report["sources"]:
        print(
            "SOURCE="
            f"{source['source_name']}|{source['status']}|jobs={source['observed_job_count']}|"
            f"detail={source['detail_proven_job_count']}|"
            f"profile_location_detail={source['profile_location_detail_job_count']}"
        )
        if source["error"]:
            print(f"SOURCE_ERROR={source['source_name']}|{source['error']}")
    for row in report["profile_location_detail_jobs"]:
        print(
            "JOB="
            f"{row['source_name']}|{row['role_family']}|{row['company_name']}|"
            f"{row['title']}|{row['location']}|chars={row['detail_chars']}|{row['source_url']}"
        )
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("DEMO_LIVE_DETAIL_TRANCHE=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
