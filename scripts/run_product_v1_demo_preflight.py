"""Read-only live-demo preflight for the Product V1 Control Center.

The preflight never creates product truth. It inspects the current runtime database,
current Control Center payload, private Candidate Fact readiness, and frontend build
surface to determine whether the live vertical slice can be shown truthfully:

market/source -> connector health -> Bronze -> Silver -> Product V1 -> Top 5 ->
application preparation.

No provider call, source activation, database write, application mutation, submission,
or send action is performed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from scripts.run_product_v1_control_center import load_product_v1_payload
from src.job_lifecycle_health import EMPLOYER_ORIGIN_HEALTH_SOURCE_TYPES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "product_v1_demo_preflight.json"
DEFAULT_FRONTEND_DIST = ROOT / "frontend" / "control-center" / "dist"


@dataclass(frozen=True)
class Gate:
    name: str
    status: str
    detail: str
    blocking: bool

    def to_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "blocking": self.blocking,
        }


def _relation_exists(conn: psycopg.Connection[object], relation_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{relation_name}",))
        row = cur.fetchone()
    return bool(row and row[0])


def _candidate_fact_readiness() -> dict[str, object]:
    required = {
        "candidate_fact_profiles",
        "candidate_facts",
    }
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        present = {name: _relation_exists(conn, name) for name in sorted(required)}
        if not all(present.values()):
            return {
                "relations": present,
                "profile_present": False,
                "profile_status": "missing",
                "profile_sha256": None,
                "approved_fact_count": 0,
            }
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    profile.status,
                    profile.payload_sha256,
                    count(fact.fact_key) FILTER (
                        WHERE fact.approval_status = 'approved'
                    )::integer AS approved_fact_count
                FROM candidate_fact_profiles profile
                LEFT JOIN candidate_facts fact
                  ON fact.profile_key = profile.profile_key
                WHERE profile.profile_key = 'default'
                GROUP BY profile.status, profile.payload_sha256
                """
            )
            row = cur.fetchone()
    if row is None:
        return {
            "relations": present,
            "profile_present": False,
            "profile_status": "missing",
            "profile_sha256": None,
            "approved_fact_count": 0,
        }
    return {
        "relations": present,
        "profile_present": True,
        "profile_status": str(row["status"]),
        "profile_sha256": str(row["payload_sha256"]),
        "approved_fact_count": int(row["approved_fact_count"] or 0),
    }


def _application_status_for_job(
    rows: Sequence[Mapping[str, object]], silver_job_id: int
) -> str | None:
    for row in rows:
        try:
            row_id = int(row.get("silver_job_id") or 0)
        except (TypeError, ValueError):
            continue
        if row_id == silver_job_id:
            value = row.get("application_readiness_status")
            return str(value) if value is not None else None
    return None


def _top_job_candidate(payload: Mapping[str, object]) -> dict[str, object] | None:
    raw = payload.get("top_jobs")
    if not isinstance(raw, list):
        return None
    eligible: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        if (
            str(row.get("canonical_source_type") or "")
            in EMPLOYER_ORIGIN_HEALTH_SOURCE_TYPES
            and str(row.get("origin_validation_status") or "") == "validated"
            and str(row.get("activity_status") or "") == "active"
            and str(row.get("hard_filter_status") or "") == "passed"
            and str(row.get("product_readiness_status") or "") == "rankable"
        ):
            eligible.append(row)
    if not eligible:
        return None
    eligible.sort(
        key=lambda row: (
            int(row.get("product_rank") or 999),
            -float(row.get("overall_quality_score") or 0.0),
            int(row.get("silver_job_id") or 0),
        )
    )
    return eligible[0]


def _demo_sources(payload: Mapping[str, object], limit: int = 3) -> list[dict[str, object]]:
    overview = payload.get("source_connector_overview")
    if not isinstance(overview, Mapping):
        return []
    raw_sources = overview.get("sources")
    if not isinstance(raw_sources, list):
        return []

    ranked: list[tuple[tuple[int, int, int, int, str], dict[str, object]]] = []
    for raw in raw_sources:
        if not isinstance(raw, Mapping):
            continue
        source = dict(raw)
        connector = source.get("connector") if isinstance(source.get("connector"), Mapping) else {}
        activation = source.get("activation") if isinstance(source.get("activation"), Mapping) else {}
        ingestion = source.get("last_ingestion") if isinstance(source.get("last_ingestion"), Mapping) else {}
        layers = source.get("layers") if isinstance(source.get("layers"), Mapping) else {}
        implemented = bool(connector.get("implemented"))
        active = activation.get("active") is True
        ingested = str(ingestion.get("status") or "").casefold() in {"success", "succeeded", "completed"}
        silver_count = int(layers.get("silver_count") or 0)
        bronze_count = int(layers.get("bronze_count") or 0)
        source_name = str(source.get("source_name") or "")
        score = (
            1 if silver_count > 0 else 0,
            1 if bronze_count > 0 else 0,
            1 if ingested else 0,
            1 if implemented and active else 0,
            source_name,
        )
        if implemented or bronze_count > 0 or silver_count > 0:
            ranked.append((score, source))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [source for _score, source in ranked[:limit]]


def _gate(
    name: str,
    condition: bool,
    *,
    passed: str,
    failed: str,
    blocking: bool = True,
) -> Gate:
    return Gate(
        name=name,
        status="pass" if condition else "blocked",
        detail=passed if condition else failed,
        blocking=blocking and not condition,
    )


def build_demo_preflight(
    *,
    payload: Mapping[str, object],
    candidate_fact_readiness: Mapping[str, object],
    frontend_dist: Path,
    openai_key_present: bool,
) -> dict[str, object]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    application_sources = (
        payload.get("application_sources_ready")
        if isinstance(payload.get("application_sources_ready"), Mapping)
        else {}
    )
    application_rows = (
        payload.get("application_readiness")
        if isinstance(payload.get("application_readiness"), list)
        else []
    )

    selected = _top_job_candidate(payload)
    selected_id = int(selected.get("silver_job_id") or 0) if selected else 0
    application_status = (
        _application_status_for_job(application_rows, selected_id) if selected_id else None
    )
    sources = _demo_sources(payload)

    approved_fact_count = int(candidate_fact_readiness.get("approved_fact_count") or 0)
    profile_approved = candidate_fact_readiness.get("profile_status") == "approved"
    base_cv_ready = application_sources.get("base_cv") is True
    base_letter_ready = application_sources.get("base_application_letter") is True
    frontend_ready = (frontend_dist / "index.html").is_file()

    gates = [
        _gate(
            "control_center_payload",
            bool(summary),
            passed="Product V1 payload is readable.",
            failed="Product V1 payload has no summary.",
        ),
        _gate(
            "source_story",
            len(sources) >= 1,
            passed=f"{len(sources)} demo source(s) expose connector/layer truth.",
            failed="No implemented or materialized source is available for the demo story.",
        ),
        _gate(
            "authoritative_top_job",
            selected is not None,
            passed=(
                f"Top job #{selected.get('product_rank')} {selected.get('company_name')} / "
                f"{selected.get('title')} is eligible for the application workspace."
                if selected
                else ""
            ),
            failed="No current employer-origin validated active hard-filter-passed Top-5 job exists.",
        ),
        _gate(
            "application_readiness",
            application_status == "ready_for_generation",
            passed="Selected job is ready_for_generation.",
            failed=f"Selected job application readiness is {application_status or 'unavailable'}.",
        ),
        _gate(
            "candidate_fact_profile",
            profile_approved and approved_fact_count > 0,
            passed=f"Approved private Candidate Fact profile exposes {approved_fact_count} approved fact(s).",
            failed=(
                f"Candidate Fact profile status={candidate_fact_readiness.get('profile_status')} "
                f"approved_facts={approved_fact_count}."
            ),
        ),
        _gate(
            "base_cv",
            base_cv_ready,
            passed="Approved base CV is registered.",
            failed="Approved base CV is missing.",
        ),
        _gate(
            "base_application_letter",
            base_letter_ready,
            passed="Approved base application letter is registered.",
            failed="Approved base application letter is missing.",
        ),
        _gate(
            "frontend_build",
            frontend_ready,
            passed=f"Built Control Center found at {frontend_dist}.",
            failed=f"Control Center build is missing at {frontend_dist}.",
        ),
        _gate(
            "draft_provider_key",
            openai_key_present,
            passed="OPENAI_API_KEY is present for an operator-triggered review draft.",
            failed="OPENAI_API_KEY is not present; live draft generation is unavailable.",
        ),
    ]

    blockers = [gate.name for gate in gates if gate.blocking]
    state = "pass" if not blockers else "blocked"
    return {
        "schema": "job_application_pipeline.product_v1_demo_preflight.v1",
        "state": state,
        "demo_story": [
            "discovery_and_market_evidence",
            "employer_origin",
            "connector_and_source_health",
            "bronze",
            "silver",
            "gold_product_v1",
            "authoritative_top5",
            "application_workspace",
            "draft_for_review",
        ],
        "summary": dict(summary),
        "demo_sources": sources,
        "selected_top_job": selected,
        "selected_application_readiness": application_status,
        "candidate_fact_readiness": dict(candidate_fact_readiness),
        "application_sources_ready": dict(application_sources),
        "frontend_dist": str(frontend_dist),
        "openai_key_present": openai_key_present,
        "gates": [gate.to_json() for gate in gates],
        "blocking_gates": blockers,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "provider_requests": 0,
            "source_activation": False,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
            "fake_product_truth": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontend-dist", type=Path, default=DEFAULT_FRONTEND_DIST)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = load_product_v1_payload()
    candidate_fact_readiness = _candidate_fact_readiness()
    report = build_demo_preflight(
        payload=payload,
        candidate_fact_readiness=candidate_fact_readiness,
        frontend_dist=args.frontend_dist.resolve(),
        openai_key_present=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    print("============================================")
    print("PRODUCT V1 LIVE DEMO PREFLIGHT")
    print("============================================")
    print(f"STATE={str(report['state']).upper()}")
    print(f"CURRENT_ACTIVE={report['summary'].get('current_active_job_count', 0)}")
    print(f"RANKABLE={report['summary'].get('rankable_job_count', 0)}")
    print(f"TOP5={report['summary'].get('top_job_count', 0)}")
    print(f"DEMO_SOURCES={len(report['demo_sources'])}")
    selected = report.get("selected_top_job")
    if isinstance(selected, Mapping):
        print(f"SELECTED_JOB={selected.get('silver_job_id')}|{selected.get('company_name')}|{selected.get('title')}")
    else:
        print("SELECTED_JOB=NONE")
    print("BLOCKERS=" + json.dumps(report["blocking_gates"], sort_keys=True))
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print("SUBMISSION_WRITES=0")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_DEMO_PREFLIGHT=COMPLETE")
    return 0 if report["state"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
