"""DEMO-001 quality binding for the Product V1 Application Workspace.

Workspace/context authority stays in the canonical runtime. The bounded model callback
uses approved base-document text as explicitly authorized style/structure context. A
validated draft is then rendered locally into four review-only application files.
"""
from __future__ import annotations

import os

from scripts.product_v1_application_workspace_runtime import (
    _evidence_first_draft_payload,
    application_workspace_payload,
    load_application_workspace,
)
from src.search_intelligence.product_v1_application_document_package import (
    build_application_document_package_payload,
)
from src.search_intelligence.product_v1_application_drafter import (
    execute_product_v1_application_drafter,
)
from src.search_intelligence.product_v1_application_drafter_quality import (
    openai_quality_application_draft_model_callback,
)


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
        return _evidence_first_draft_payload(
            context=context,
            final_url=final_url,
            fetched_title=fetched_title,
            fallback_reason="provider_key_unavailable",
        )

    execution = execute_product_v1_application_drafter(
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
        return _evidence_first_draft_payload(
            context=context,
            final_url=final_url,
            fetched_title=fetched_title,
            fallback_reason="quality_provider_campaign_unresolved",
            provider_requests=execution.provider_requests,
            llm_requests=execution.llm_requests,
            estimated_model_cost_usd=execution.estimated_model_cost_usd,
            stages=[stage.to_json() for stage in execution.stages],
        ) | {
            "quality_contract": "base_document_style_context_v3",
            "unresolved_provider_stage_count": len(unresolved),
        }

    document_package = build_application_document_package_payload(
        context=context,
        package=execution.package,
    )
    payload = execution.to_json()
    payload.update(
        {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
            "status": "draft_for_review",
            "draft_mode": "provider_validated_quality_v3",
            "fallback_reason": None,
            "quality_contract": "base_document_style_context_v3",
            "base_document_text_shared_with_provider": True,
            "document_package": document_package,
            "live_job_evidence": {
                "final_url": final_url,
                "fetched_title": fetched_title,
                "detail_sha256": context.target.detail_sha256,
            },
        }
    )
    return payload


__all__ = ["application_workspace_payload", "generate_application_draft_payload"]
