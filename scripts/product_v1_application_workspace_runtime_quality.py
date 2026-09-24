"""DEMO-001 quality binding for the Product V1 Application Workspace.

Workspace/context authority stays in the canonical runtime. The bounded model callback
may produce review-only text fragments, but F6 no longer permits the legacy generic
DOCX/A4 renderer. Exact template-bound rendering is a separate authority-gated step.
"""
from __future__ import annotations

import os

from scripts.product_v1_application_workspace_runtime import (
    _evidence_first_draft_payload,
    application_workspace_payload,
    load_application_workspace,
)
from src.search_intelligence.product_v1_application_drafter_quality import (
    openai_quality_application_draft_model_callback,
)
from src.search_intelligence.product_v1_application_quality_campaign import (
    execute_quality_application_drafter,
)


def _fallback_with_template_authority(
    *,
    context: object,
    final_url: str,
    fetched_title: str,
    fallback_reason: str,
    provider_text_shared: bool,
    provider_requests: int = 0,
    llm_requests: int = 0,
    estimated_model_cost_usd: float = 0.0,
    stages: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload = _evidence_first_draft_payload(
        context=context,
        final_url=final_url,
        fetched_title=fetched_title,
        fallback_reason=fallback_reason,
        provider_requests=provider_requests,
        llm_requests=llm_requests,
        estimated_model_cost_usd=estimated_model_cost_usd,
        stages=stages,
    )
    payload.update(
        {
            "quality_contract": "f6_template_authority_v1",
            "base_document_text_shared_with_provider": provider_text_shared,
            "render_status": "template_bound_renderer_qualified_review_export_available",
            "legacy_generic_document_export": False,
        }
    )
    return payload


def generate_application_draft_payload(silver_job_id: int) -> dict[str, object]:
    context, final_url, fetched_title = load_application_workspace(silver_job_id)
    if not context.generation_ready:
        return {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
            "status": "blocked",
            "blocked_reasons": list(context.blocked_reasons),
            "workspace": context.canonical_payload(),
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }
    if not context.claim_plan:
        return {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
            "status": "blocked",
            "blocked_reasons": ["candidate_job_claim_plan_required"],
            "workspace": context.canonical_payload(),
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _fallback_with_template_authority(
            context=context,
            final_url=final_url,
            fetched_title=fetched_title,
            fallback_reason="provider_key_unavailable",
            provider_text_shared=False,
        )

    execution = execute_quality_application_drafter(
        context=context,
        model=openai_quality_application_draft_model_callback(
            context=context,
            api_key=api_key,
        ),
    )
    if execution.package is None:
        unresolved = [
            stage.to_json()
            for stage in execution.stages
            if stage.attempted and stage.status in {"unresolved", "failed_closed"}
        ]
        return _fallback_with_template_authority(
            context=context,
            final_url=final_url,
            fetched_title=fetched_title,
            fallback_reason="quality_provider_campaign_unresolved",
            provider_text_shared=execution.provider_requests > 0,
            provider_requests=execution.provider_requests,
            llm_requests=execution.llm_requests,
            estimated_model_cost_usd=execution.estimated_model_cost_usd,
            stages=[stage.to_json() for stage in execution.stages],
        ) | {
            "unresolved_provider_stage_count": len(unresolved),
        }

    payload = execution.to_json()
    payload.update(
        {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
            "status": "draft_for_review",
            "draft_mode": "provider_validated_quality_v3",
            "fallback_reason": None,
            "quality_contract": "f6_template_authority_v1",
            "base_document_text_shared_with_provider": True,
            "render_status": "template_bound_renderer_qualified_review_export_available",
            "legacy_generic_document_export": False,
            "live_job_evidence": {
                "final_url": final_url,
                "fetched_title": fetched_title,
                "detail_sha256": context.target.detail_sha256,
            },
        }
    )
    return payload


__all__ = ["application_workspace_payload", "generate_application_draft_payload"]
