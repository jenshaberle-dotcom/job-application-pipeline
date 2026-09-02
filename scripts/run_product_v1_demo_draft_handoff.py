"""Validate the review-draft proof carried by the single-fetch Workspace probe."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from scripts.run_product_v1_demo_workspace_probe import (
    WorkspaceProbeStop,
    selected_job_id_from_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFLIGHT = ROOT / ".runtime" / "demo" / "product_v1_demo_preflight.json"
DEFAULT_WORKSPACE = ROOT / ".runtime" / "demo" / "product_v1_demo_workspace_probe.json"
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "product_v1_demo_draft_probe.json"


class DraftHandoffStop(RuntimeError):
    pass


def _artifact_sha256(path: Path) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise DraftHandoffStop(f"readiness artifact is unreadable: {path}") from exc


def _read(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftHandoffStop(f"workspace probe artifact is unreadable: {path}") from exc
    if not isinstance(value, Mapping):
        raise DraftHandoffStop("workspace probe artifact root must be an object")
    return value


def evaluate_handoff(
    *,
    silver_job_id: int,
    report: Mapping[str, object],
    expected_preflight_sha256: str | None = None,
    workspace_artifact_sha256: str | None = None,
) -> dict[str, object]:
    if report.get("state") != "pass":
        raise DraftHandoffStop("workspace probe is not PASS")
    try:
        workspace_job_id = int(report.get("silver_job_id") or 0)
    except (TypeError, ValueError) as exc:
        raise DraftHandoffStop("workspace job identity is invalid") from exc

    workspace = report.get("workspace")
    live = report.get("live_job_evidence")
    carried = report.get("evidence_first_draft")
    boundaries = report.get("boundaries")
    if not all(isinstance(item, Mapping) for item in (workspace, live, carried, boundaries)):
        raise DraftHandoffStop("workspace probe is missing carried draft evidence")
    workspace = workspace  # type: ignore[assignment]
    live = live  # type: ignore[assignment]
    carried = carried  # type: ignore[assignment]
    boundaries = boundaries  # type: ignore[assignment]

    package = carried.get("package")
    claim_plan = workspace.get("claim_plan")
    if not isinstance(package, Mapping) or not isinstance(claim_plan, list) or not claim_plan:
        raise DraftHandoffStop("carried review package or claim plan is missing")

    allowed_keys = {
        str(entry.get("fact_key"))
        for entry in claim_plan
        if isinstance(entry, Mapping) and str(entry.get("fact_key") or "").strip()
    }
    allowed_refs = {
        (
            str(ref.get("evidence") or ""),
            int(ref.get("span_start") or -1),
            int(ref.get("span_end") or -1),
        )
        for entry in claim_plan
        if isinstance(entry, Mapping) and isinstance(entry.get("job_references"), list)
        for ref in entry["job_references"]
        if isinstance(ref, Mapping)
    }
    fragments = package.get("fragments")
    used = package.get("candidate_fact_keys_used")
    if not isinstance(fragments, list) or not fragments or not isinstance(used, list):
        raise DraftHandoffStop("carried review package shape is invalid")

    references_bound = True
    for fragment in fragments:
        if not isinstance(fragment, Mapping):
            references_bound = False
            continue
        keys = fragment.get("candidate_fact_keys")
        refs = fragment.get("job_evidence")
        if not isinstance(keys, list) or any(str(key) not in allowed_keys for key in keys):
            references_bound = False
        if not isinstance(refs, list):
            references_bound = False
            continue
        for ref in refs:
            if not isinstance(ref, Mapping):
                references_bound = False
                continue
            candidate = (
                str(ref.get("evidence") or ""),
                int(ref.get("span_start") or -1),
                int(ref.get("span_end") or -1),
            )
            if candidate not in allowed_refs:
                references_bound = False

    live_sha = str(live.get("detail_sha256") or "")
    used_keys = {str(key) for key in used if str(key).strip()}
    lineage_sha = str(report.get("preflight_artifact_sha256") or "")
    lineage_required = expected_preflight_sha256 is not None
    lineage_bound = (
        not lineage_required
        or (
            len(expected_preflight_sha256 or "") == 64
            and lineage_sha == expected_preflight_sha256
        )
    )
    checks = {
        "selected_job_exact_bound": workspace_job_id == silver_job_id,
        "review_package_present": package.get("status") == "draft_for_review",
        "candidate_facts_from_claim_plan": bool(used_keys) and used_keys <= allowed_keys,
        "vacancy_references_from_workspace": references_bound,
        "live_detail_fingerprint_bound": (
            len(live_sha) == 64 and str(carried.get("detail_sha256") or "") == live_sha
        ),
        "preflight_artifact_exact_bound": lineage_bound,
        "zero_authority": all(
            package.get(field) is False
            for field in (
                "draft_approval_authority",
                "application_authority",
                "submission_authority",
                "product_authority",
            )
        ),
        "provider_free": int(carried.get("provider_requests") or 0) == 0,
        "zero_writes": all(
            int(carried.get(field) or 0) == 0
            for field in (
                "database_writes",
                "application_writes",
                "submission_writes",
                "send_actions",
            )
        ),
        "single_fetch_handoff": int(boundaries.get("job_detail_http_gets") or 0) == 1,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "job_application_pipeline.product_v1_demo_draft_probe.v3",
        "state": "pass" if not blockers else "blocked",
        "silver_job_id": silver_job_id,
        "draft_mode": "deterministic_evidence_first",
        "checks": checks,
        "blocking_checks": blockers,
        "preflight_artifact_sha256": lineage_sha or None,
        "workspace_artifact_sha256": workspace_artifact_sha256,
        "package": dict(package),
        "live_job_evidence": dict(live),
        "boundaries": {
            "workspace_job_detail_http_gets": 1,
            "draft_probe_http_gets": 0,
            "provider_requests": 0,
            "database_reads": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        },
    }


def blocked(*, silver_job_id: int | None, exc: BaseException) -> dict[str, object]:
    return {
        "schema": "job_application_pipeline.product_v1_demo_draft_probe.v3",
        "state": "blocked",
        "silver_job_id": silver_job_id,
        "checks": {},
        "blocking_checks": ["draft_handoff"],
        "reason": " ".join(str(exc).split())[:700],
        "boundaries": {"draft_probe_http_gets": 0, "provider_requests": 0, "database_writes": 0, "submission_writes": 0, "send_actions": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--workspace-probe", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    silver_job_id: int | None = None
    preflight_path = args.preflight.resolve()
    workspace_path = args.workspace_probe.resolve()
    try:
        silver_job_id = selected_job_id_from_preflight(preflight_path)
        result = evaluate_handoff(
            silver_job_id=silver_job_id,
            report=_read(workspace_path),
            expected_preflight_sha256=_artifact_sha256(preflight_path),
            workspace_artifact_sha256=_artifact_sha256(workspace_path),
        )
    except (WorkspaceProbeStop, DraftHandoffStop, OSError, ValueError) as exc:
        result = blocked(silver_job_id=silver_job_id, exc=exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"STATE={str(result.get('state') or 'blocked').upper()}")
    print("DRAFT_PROBE_HTTP_GETS=0")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    return 0 if result.get("state") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
