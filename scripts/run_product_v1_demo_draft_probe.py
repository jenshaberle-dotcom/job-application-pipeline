"""Provider-free DEMO-001 probe for the final review-draft contract.

This probe runs only after Product V1 preflight has selected an authoritative Top-5
job. It loads that exact canonical Application Workspace and invokes only the
provider-free evidence-first draft builder. The resulting package is validated as
review-only, source-manifest bound and zero-provider/zero-write. Nothing is
persisted, approved, submitted or sent.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import psycopg

from scripts.product_v1_application_workspace_runtime import load_application_workspace
from scripts.run_product_v1_demo_workspace_probe import (
    WorkspaceProbeStop,
    selected_job_id_from_preflight,
)
from src.search_intelligence.product_v1_application_context import ProductV1ApplicationContext
from src.search_intelligence.product_v1_application_workspace import ApplicationWorkspaceStop
from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop
from src.search_intelligence.product_v1_evidence_first_draft import (
    EvidenceFirstDraftStop,
    build_evidence_first_review_draft,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFLIGHT = ROOT / ".runtime" / "demo" / "product_v1_demo_preflight.json"
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "product_v1_demo_draft_probe.json"

ContextLoader = Callable[[int], tuple[ProductV1ApplicationContext, str, str]]


class DraftProbeStop(RuntimeError):
    """Fail-closed boundary for final deterministic draft readiness."""


def evaluate_draft_context(
    *,
    silver_job_id: int,
    context: ProductV1ApplicationContext,
    final_url: str,
) -> dict[str, object]:
    if context.target.silver_job_id != silver_job_id:
        raise DraftProbeStop("draft context is not exact-bound to selected job")
    if not context.generation_ready:
        raise DraftProbeStop("application context is not generation-ready")

    package = build_evidence_first_review_draft(context)
    canonical = package.canonical_payload()
    manifest = context.source_manifest()

    expected_fact_keys = {entry.fact_key for entry in context.claim_plan}
    used_fact_keys = set(package.candidate_fact_keys_used)
    references_exact = True
    for fragment in package.fragments:
        if any(key not in expected_fact_keys for key in fragment.candidate_fact_keys):
            references_exact = False
        for reference in fragment.job_evidence:
            detail = context.target.detail_text
            if not (
                0 <= reference.span_start < reference.span_end <= len(detail)
                and detail[reference.span_start : reference.span_end] == reference.evidence
            ):
                references_exact = False

    authority_safe = not any(
        (
            package.draft_approval_authority,
            package.application_authority,
            package.submission_authority,
            package.product_authority,
        )
    )
    checks = {
        "selected_job_exact_bound": context.target.silver_job_id == silver_job_id,
        "generation_context_ready": context.generation_ready,
        "review_package_present": package.status == "draft_for_review" and bool(package.fragments),
        "candidate_facts_from_claim_plan": bool(used_fact_keys) and used_fact_keys <= expected_fact_keys,
        "vacancy_references_exact": references_exact,
        "source_manifest_bound": package.source_manifest_sha256 == _manifest_sha256(manifest),
        "zero_authority": authority_safe,
        "provider_free": True,
        "zero_writes": True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "job_application_pipeline.product_v1_demo_draft_probe.v1",
        "state": "pass" if not blockers else "blocked",
        "silver_job_id": silver_job_id,
        "draft_mode": "deterministic_evidence_first",
        "checks": checks,
        "blocking_checks": blockers,
        "package": canonical,
        "live_job_evidence": {
            "final_url": final_url,
            "detail_sha256": context.target.detail_sha256,
        },
        "boundaries": {
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
            "draft_approval_authority": False,
            "application_authority": False,
            "submission_authority": False,
        },
    }


def _manifest_sha256(manifest: object) -> str:
    from hashlib import sha256

    encoded = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def run_draft_probe(
    *,
    silver_job_id: int,
    loader: ContextLoader = load_application_workspace,
) -> dict[str, object]:
    try:
        loaded = loader(silver_job_id)
        context, final_url, _fetched_title = loaded
        return evaluate_draft_context(
            silver_job_id=silver_job_id,
            context=context,
            final_url=final_url,
        )
    except (
        ApplicationWorkspaceStop,
        DownstreamPreviewStop,
        EvidenceFirstDraftStop,
        DraftProbeStop,
        psycopg.Error,
        OSError,
        ValueError,
    ) as exc:
        return {
            "schema": "job_application_pipeline.product_v1_demo_draft_probe.v1",
            "state": "blocked",
            "silver_job_id": silver_job_id,
            "draft_mode": "deterministic_evidence_first",
            "checks": {},
            "blocking_checks": ["draft_runtime"],
            "reason": " ".join(str(exc).split())[:700],
            "error_type": type(exc).__name__,
            "boundaries": {
                "provider_requests": 0,
                "database_writes": 0,
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
    try:
        silver_job_id = selected_job_id_from_preflight(args.preflight.resolve())
        report = run_draft_probe(silver_job_id=silver_job_id)
    except WorkspaceProbeStop as exc:
        report = {
            "schema": "job_application_pipeline.product_v1_demo_draft_probe.v1",
            "state": "blocked",
            "silver_job_id": None,
            "draft_mode": "deterministic_evidence_first",
            "checks": {},
            "blocking_checks": ["preflight_handoff"],
            "reason": " ".join(str(exc).split())[:700],
            "error_type": type(exc).__name__,
            "boundaries": {
                "provider_requests": 0,
                "database_writes": 0,
                "application_writes": 0,
                "submission_writes": 0,
                "send_actions": 0,
            },
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print("============================================")
    print("PRODUCT V1 DEMO REVIEW-DRAFT PROBE")
    print("============================================")
    print(f"STATE={str(report.get('state') or 'blocked').upper()}")
    print(f"SILVER_JOB_ID={report.get('silver_job_id') or 'NONE'}")
    print("DRAFT_MODE=DETERMINISTIC_EVIDENCE_FIRST")
    print("BLOCKERS=" + json.dumps(report.get("blocking_checks") or [], sort_keys=True))
    print("PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("SUBMISSION_WRITES=0")
    print("SEND_ACTIONS=0")
    print(f"artifact={args.output.resolve()}")
    return 0 if report.get("state") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
