"""Product V1 Application Workspace drafting binding.

The Product path now uses embedded Codex for one bounded responsibility only:
adapting the approved CV profile/competency text and the application-letter text
to the exact selected vacancy. Deterministic context, source truth, template
authority, rendering, submission boundaries and all writes remain outside Codex.

If Codex allowance/credits/authentication are unavailable, the draft stops
visibly. JAP no longer substitutes deterministic filler prose for an
operator-facing application.
"""
from __future__ import annotations

import hashlib
import json

from scripts.product_v1_application_workspace_runtime import (
    application_workspace_payload,
    load_application_workspace,
    require_live_application_target,
)
from src.search_intelligence.product_v1_codex_application_adapter import (
    request_codex_application_adaptation,
)


def _source_manifest_sha256(context: object) -> str:
    payload = context.source_manifest()
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _blocked_payload(*, context: object, reasons: list[str]) -> dict[str, object]:
    return {
        "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
        "status": "blocked",
        "blocked_reasons": reasons,
        "workspace": context.canonical_payload(),
        "draft_mode": "codex_embedded_v1",
        "codex_requests": 0,
        "provider_requests": 0,
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
    }


def generate_application_draft_payload(silver_job_id: int) -> dict[str, object]:
    require_live_application_target(silver_job_id)
    context, final_url, fetched_title, evidence_mode, job_detail_http_gets = (
        load_application_workspace(silver_job_id)
    )
    if not context.generation_ready:
        return _blocked_payload(
            context=context,
            reasons=list(context.blocked_reasons),
        )
    if not context.claim_plan:
        return _blocked_payload(
            context=context,
            reasons=["candidate_job_claim_plan_required"],
        )

    result = request_codex_application_adaptation(context=context)
    if result.package is None:
        return {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
            "status": "draft_unavailable",
            "reason": result.reason or "Embedded Codex drafting is unavailable.",
            "reason_code": result.reason_code or "codex_unavailable",
            "retryable": result.reason_code
            in {
                "codex_capacity_unavailable",
                "codex_timeout",
                "codex_execution_failed",
            },
            "draft_mode": "codex_embedded_v1",
            "codex_model": result.model,
            "codex_version": result.codex_version,
            "codex_requests": int(result.attempted),
            "provider_requests": int(result.attempted),
            "llm_requests": int(result.attempted),
            "fallback_generated": False,
            "fallback_policy": "no_low_quality_prose_fallback",
            "workspace": context.canonical_payload(),
            "live_job_evidence": {
                "final_url": final_url,
                "fetched_title": fetched_title,
                "detail_sha256": context.target.detail_sha256,
                "evidence_mode": evidence_mode,
            },
            "vacancy_revalidation_http_gets": 1,
            "lifecycle_health_observation_writes": 0,
            "job_detail_http_gets": job_detail_http_gets,
            "current_observation_detail_reuse": int(
                evidence_mode == "exact_persisted_observation"
            ),
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }

    package = dict(result.package)
    package["source_manifest_sha256"] = _source_manifest_sha256(context)
    package["candidate_fact_keys_used"] = sorted(
        entry.fact_key for entry in context.claim_plan
    )

    return {
        "schema": "job_application_pipeline.product_v1_application_draft_demo.v2",
        "status": "draft_for_review",
        "draft_mode": "codex_embedded_v1",
        "fallback_reason": None,
        "fallback_generated": False,
        "quality_contract": "f6_template_authority_v1",
        "codex_adaptation_contract": "f6_codex_adaptation_v1",
        "layout_policy": "preserve_exact_template_layout_modify_text_zones_only",
        "codex_model": result.model,
        "codex_version": result.codex_version,
        "codex_requests": 1,
        "provider_requests": 1,
        "llm_requests": 1,
        "base_cv_text_shared_with_codex": True,
        "base_application_letter_text_shared_with_codex": False,
        "render_status": "template_bound_renderer_qualified_review_export_available",
        "legacy_generic_document_export": False,
        "package": package,
        "live_job_evidence": {
            "final_url": final_url,
            "fetched_title": fetched_title,
            "detail_sha256": context.target.detail_sha256,
            "evidence_mode": evidence_mode,
        },
        "job_detail_http_gets": job_detail_http_gets,
        "current_observation_detail_reuse": int(
            evidence_mode == "exact_persisted_observation"
        ),
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
        "draft_approval_authority": False,
        "application_authority": False,
        "submission_authority": False,
        "send_authority": False,
    }


__all__ = ["application_workspace_payload", "generate_application_draft_payload"]
