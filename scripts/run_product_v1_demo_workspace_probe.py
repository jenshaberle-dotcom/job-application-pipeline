"""Read-only DEMO-001 probe for the selected authoritative Application Workspace.

The probe performs the canonical workspace DB reads plus one bounded employer-origin
vacancy HTTP GET. From that same in-memory context it also builds the deterministic
evidence-first review package used by the provider-free runtime fallback. This makes
the downstream draft readiness proof a single-fetch handoff rather than a second
origin request. No provider, product/application write, submission or send occurs.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Mapping

import psycopg

from scripts.product_v1_application_workspace_runtime import (
    application_workspace_payload,
    load_application_workspace,
)
from src.search_intelligence.product_v1_application_workspace import ApplicationWorkspaceStop
from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop
from src.search_intelligence.product_v1_evidence_first_draft import (
    EvidenceFirstDraftStop,
    build_evidence_first_review_draft,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFLIGHT = ROOT / ".runtime" / "demo" / "product_v1_demo_preflight.json"
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "product_v1_demo_workspace_probe.json"

WorkspaceLoader = Callable[[int], Mapping[str, object]]


class WorkspaceProbeStop(RuntimeError):
    """Fail-closed boundary for an invalid preflight/workspace handoff."""


def _artifact_sha256(path: Path) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise WorkspaceProbeStop(f"readiness artifact is unreadable: {path}") from exc


def _read_json_object(path: Path) -> Mapping[str, object]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceProbeStop(f"preflight artifact is unreadable: {path}") from exc
    if not isinstance(decoded, Mapping):
        raise WorkspaceProbeStop("preflight artifact root must be an object")
    return decoded


def selected_job_id_from_preflight(path: Path) -> int:
    payload = _read_json_object(path)
    if payload.get("state") != "pass":
        raise WorkspaceProbeStop("Product V1 demo preflight is not PASS")
    selected = payload.get("selected_top_job")
    if not isinstance(selected, Mapping):
        raise WorkspaceProbeStop("preflight has no selected authoritative Top-5 job")
    try:
        silver_job_id = int(selected.get("silver_job_id") or 0)
    except (TypeError, ValueError) as exc:
        raise WorkspaceProbeStop("selected silver_job_id is invalid") from exc
    if silver_job_id <= 0:
        raise WorkspaceProbeStop("selected silver_job_id must be positive")
    return silver_job_id


def _workspace_components(payload: Mapping[str, object]) -> tuple[
    Mapping[str, object], Mapping[str, object], Mapping[str, object]
]:
    workspace = payload.get("workspace")
    live_evidence = payload.get("live_job_evidence")
    boundaries = payload.get("boundaries")
    if not isinstance(workspace, Mapping):
        raise WorkspaceProbeStop("workspace payload is missing")
    if not isinstance(live_evidence, Mapping):
        raise WorkspaceProbeStop("live job evidence is missing")
    if not isinstance(boundaries, Mapping):
        raise WorkspaceProbeStop("workspace boundaries are missing")
    return workspace, live_evidence, boundaries


def evaluate_workspace_payload(
    *, silver_job_id: int, payload: Mapping[str, object]
) -> dict[str, object]:
    workspace, live_evidence, boundaries = _workspace_components(payload)
    target = workspace.get("target")
    claim_plan = workspace.get("claim_plan")
    source_manifest = workspace.get("source_manifest")
    documents = source_manifest.get("documents") if isinstance(source_manifest, Mapping) else None

    target_id = 0
    if isinstance(target, Mapping):
        try:
            target_id = int(target.get("silver_job_id") or 0)
        except (TypeError, ValueError):
            target_id = 0

    detail_sha = str(live_evidence.get("detail_sha256") or "")
    boundary_safe = (
        boundaries.get("database_writes") is False
        and int(boundaries.get("provider_requests") or 0) == 0
        and int(boundaries.get("application_writes") or 0) == 0
        and int(boundaries.get("submission_writes") or 0) == 0
        and int(boundaries.get("send_actions") or 0) == 0
    )
    checks = {
        "workspace_status_ready": payload.get("status") == "ready",
        "selected_job_exact_bound": target_id == silver_job_id,
        "generation_ready": workspace.get("generation_ready") is True,
        "claim_plan_present": isinstance(claim_plan, list) and len(claim_plan) > 0,
        "approved_source_documents_present": isinstance(documents, list) and len(documents) >= 2,
        "live_detail_fingerprint_present": (
            len(detail_sha) == 64
            and all(character in "0123456789abcdef" for character in detail_sha)
        ),
        "zero_write_provider_boundary": boundary_safe,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "job_application_pipeline.product_v1_demo_workspace_probe.v3",
        "state": "pass" if not blockers else "blocked",
        "silver_job_id": silver_job_id,
        "checks": checks,
        "blocking_checks": blockers,
        "workspace": dict(workspace),
        "live_job_evidence": dict(live_evidence),
        "boundaries": dict(boundaries),
    }


def run_workspace_probe(
    *,
    silver_job_id: int,
    loader: WorkspaceLoader = application_workspace_payload,
) -> dict[str, object]:
    """Compatibility/test surface for evaluating an already-built workspace payload."""
    try:
        payload = loader(silver_job_id)
        if not isinstance(payload, Mapping):
            raise WorkspaceProbeStop("workspace loader returned a non-object payload")
        return evaluate_workspace_payload(silver_job_id=silver_job_id, payload=payload)
    except (
        ApplicationWorkspaceStop,
        DownstreamPreviewStop,
        WorkspaceProbeStop,
        psycopg.Error,
        OSError,
        ValueError,
    ) as exc:
        return _blocked_report(silver_job_id=silver_job_id, exc=exc)


def run_workspace_probe_single_fetch(*, silver_job_id: int) -> dict[str, object]:
    """Load one canonical workspace and carry its deterministic draft proof forward."""
    try:
        context, final_url, fetched_title = load_application_workspace(silver_job_id)
        payload = {
            "status": "ready" if context.generation_ready else "blocked",
            "workspace": context.canonical_payload(),
            "live_job_evidence": {
                "final_url": final_url,
                "fetched_title": fetched_title,
                "detail_sha256": context.target.detail_sha256,
            },
            "boundaries": {
                "database_reads": True,
                "database_writes": False,
                "job_detail_http_gets": 1,
                "provider_requests": 0,
                "application_writes": 0,
                "submission_writes": 0,
                "send_actions": 0,
            },
        }
        report = evaluate_workspace_payload(silver_job_id=silver_job_id, payload=payload)
        if report["state"] != "pass":
            return report

        package = build_evidence_first_review_draft(context)
        report["evidence_first_draft"] = {
            "draft_mode": "deterministic_evidence_first",
            "package": package.canonical_payload(),
            "detail_sha256": context.target.detail_sha256,
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }
        report["checks"]["evidence_first_draft_built"] = package.status == "draft_for_review"
        if not report["checks"]["evidence_first_draft_built"]:
            report["state"] = "blocked"
            report["blocking_checks"] = ["evidence_first_draft_built"]
        return report
    except (
        ApplicationWorkspaceStop,
        DownstreamPreviewStop,
        EvidenceFirstDraftStop,
        WorkspaceProbeStop,
        psycopg.Error,
        OSError,
        ValueError,
    ) as exc:
        return _blocked_report(silver_job_id=silver_job_id, exc=exc)


def _blocked_report(*, silver_job_id: int | None, exc: BaseException) -> dict[str, object]:
    return {
        "schema": "job_application_pipeline.product_v1_demo_workspace_probe.v3",
        "state": "blocked",
        "silver_job_id": silver_job_id,
        "checks": {},
        "blocking_checks": ["workspace_runtime"],
        "reason": " ".join(str(exc).split())[:700],
        "error_type": type(exc).__name__,
        "boundaries": {
            "database_writes": False,
            "provider_requests": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    preflight_path = args.preflight.resolve()
    try:
        silver_job_id = selected_job_id_from_preflight(preflight_path)
        report = run_workspace_probe_single_fetch(silver_job_id=silver_job_id)
        report["preflight_artifact_sha256"] = _artifact_sha256(preflight_path)
    except WorkspaceProbeStop as exc:
        report = _blocked_report(silver_job_id=None, exc=exc)
        report["blocking_checks"] = ["preflight_handoff"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print("============================================")
    print("PRODUCT V1 DEMO WORKSPACE PROBE")
    print("============================================")
    print(f"STATE={str(report.get('state') or 'blocked').upper()}")
    print(f"SILVER_JOB_ID={report.get('silver_job_id') or 'NONE'}")
    print("BLOCKERS=" + json.dumps(report.get("blocking_checks") or [], sort_keys=True))
    print("JOB_DETAIL_HTTP_GETS=1_MAX")
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print("SUBMISSION_WRITES=0")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_DEMO_WORKSPACE_PROBE=COMPLETE")
    return 0 if report.get("state") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
