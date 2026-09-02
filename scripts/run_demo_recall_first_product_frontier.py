"""Read-only DEMO-001 frontier audit after recall-first assessment materialization.

The runner keeps current Employer-Origin authority strict while deliberately avoiding
a title-only role prefilter. It reports the full current Product-V1 cohort for the
requested sources and independently probes the authoritative top job's Application
Workspace even when the full demo preflight is still blocked.

No database write, provider call, ranking mutation, application persistence,
submission, or send action is performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from scripts.run_product_v1_capability_evidence_audit import (
    _authorized_sources,
    _read_rows,
    build_report,
)
from scripts.run_product_v1_control_center import load_product_v1_payload
from scripts.run_product_v1_demo_workspace_probe import run_workspace_probe_single_fetch


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "recall_first_product_frontier.json"
DEFAULT_SOURCES = ("personio:eraneos", "personio:1komma5grad")


def select_recall_first_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    authorized_sources: Sequence[str],
) -> list[dict[str, object]]:
    """Keep all current rows from authorized Employer Origins; never gate on title."""
    authorized = {str(value) for value in authorized_sources}
    return [
        dict(row)
        for row in rows
        if str(row.get("source_name") or "") in authorized
        and str(row.get("lifecycle_status") or "") == "active_confirmed"
    ]


def selected_top_job(payload: Mapping[str, object]) -> dict[str, object] | None:
    raw = payload.get("top_jobs")
    if not isinstance(raw, list):
        return None
    candidates = [dict(item) for item in raw if isinstance(item, Mapping)]
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            int(row.get("product_rank") or 999),
            -float(row.get("overall_quality_score") or 0.0),
            int(row.get("silver_job_id") or 0),
        )
    )
    return candidates[0]


def application_status_for_job(
    payload: Mapping[str, object], silver_job_id: int
) -> str | None:
    raw = payload.get("application_readiness")
    if not isinstance(raw, list):
        return None
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        try:
            current_id = int(item.get("silver_job_id") or 0)
        except (TypeError, ValueError):
            continue
        if current_id == silver_job_id:
            value = item.get("application_readiness_status")
            return str(value) if value is not None else None
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_names = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in args.source_name
            if str(value).strip()
        )
    ) or DEFAULT_SOURCES

    authorized = _authorized_sources()
    capability_rows = select_recall_first_rows(
        _read_rows(source_names=source_names, silver_job_ids=()),
        authorized_sources=authorized,
    )
    capability_report = build_report(capability_rows)

    payload = load_product_v1_payload()
    top_job = selected_top_job(payload)
    workspace: dict[str, object]
    application_status: str | None = None
    if top_job is None:
        workspace = {
            "state": "blocked",
            "silver_job_id": None,
            "blocking_checks": ["authoritative_top_job"],
            "reason": "no top job is available",
        }
    else:
        silver_job_id = int(top_job["silver_job_id"])
        application_status = application_status_for_job(payload, silver_job_id)
        workspace = run_workspace_probe_single_fetch(silver_job_id=silver_job_id)

    report = {
        "schema": "job_application_pipeline.demo_recall_first_product_frontier.v1",
        "mode": "read_only",
        "sources": list(source_names),
        "capability_evidence": capability_report,
        "selected_top_job": top_job,
        "application_readiness_status": application_status,
        "workspace_probe": workspace,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "job_detail_http_gets": 1 if top_job is not None else 0,
            "provider_requests": 0,
            "ranking_or_top5_writes": False,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = capability_report["summary"]
    print("============================================")
    print("DEMO RECALL-FIRST PRODUCT FRONTIER")
    print("============================================")
    print(f"CURRENT_AUTHORIZED_JOBS={summary['job_count']}")
    print(
        "READINESS_COUNTS="
        + json.dumps(summary["readiness_counts"], sort_keys=True)
    )
    print(
        "UNKNOWN_COMPONENT_COUNTS="
        + json.dumps(summary["unknown_component_counts"], sort_keys=True)
    )
    if top_job is None:
        print("SELECTED_JOB=NONE")
    else:
        print(
            "SELECTED_JOB="
            f"{top_job.get('silver_job_id')}|{top_job.get('company_name')}|{top_job.get('title')}"
        )
    print(f"APPLICATION_READINESS={application_status or 'missing'}")
    print(f"WORKSPACE_STATE={str(workspace.get('state') or 'blocked').upper()}")
    print(
        "WORKSPACE_BLOCKERS="
        + json.dumps(workspace.get("blocking_checks") or [], sort_keys=True)
    )
    if workspace.get("reason"):
        print(f"WORKSPACE_REASON={workspace['reason']}")
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print("APPLICATION_WRITES=0")
    print(f"artifact={args.output.resolve()}")
    print("DEMO_RECALL_FIRST_PRODUCT_FRONTIER=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
