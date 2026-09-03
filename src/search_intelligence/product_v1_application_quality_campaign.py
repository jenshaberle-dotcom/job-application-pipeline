"""Application-specific bounded quality campaign for DEMO-001.

The shared LLM booster cost ceilings were calibrated on compact origin prompts.
Application drafting carries substantially larger vacancy and approved base-document
context, so this surface owns a separate conservative envelope without weakening any
other booster surface. Provider output still has no application, submission or product
authority and must pass the existing deterministic draft validator.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping

from src.search_intelligence.llm_booster_policy import BoosterStage
from src.search_intelligence.product_v1_application_context import ProductV1ApplicationContext
from src.search_intelligence.product_v1_application_drafter import (
    ApplicationDraftPackage,
    ApplicationDraftStageEvidence,
    MODEL_STAGES,
    ModelCallback,
    ProductV1ApplicationDraftExecution,
)


APPLICATION_DRAFT_HARD_COST_CEILING_USD: Mapping[BoosterStage, float] = {
    BoosterStage.LUNA_MEDIUM: 0.05,
    BoosterStage.TERRA_MEDIUM: 0.10,
    BoosterStage.SOL_MEDIUM: 0.20,
    BoosterStage.LUNA_MAX: 0.15,
}
APPLICATION_DRAFT_CAMPAIGN_COST_CEILING_USD = 0.25


def _package_fingerprint(package: ApplicationDraftPackage) -> str:
    encoded = json.dumps(
        package.canonical_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def execute_quality_application_drafter(
    *,
    context: ProductV1ApplicationContext,
    model: ModelCallback,
) -> ProductV1ApplicationDraftExecution:
    """Run the existing validated model cascade with application-sized cost bounds."""

    ready = context.generation_ready and bool(context.claim_plan)
    stages: list[ApplicationDraftStageEvidence] = [
        ApplicationDraftStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=True,
            status="ready" if ready else "blocked",
            reason_code=(
                "source_grounded_application_context_ready"
                if ready
                else "source_grounded_application_context_incomplete"
            ),
            provider_requests=0,
        ),
        ApplicationDraftStageEvidence(
            stage=BoosterStage.TAVILY,
            attempted=False,
            status="skipped",
            reason_code="external_search_not_indicated_for_application_drafting",
            provider_requests=0,
        ),
    ]
    provider_requests = 0
    accepted_package: ApplicationDraftPackage | None = None
    campaign_cost = 0.0

    for stage in MODEL_STAGES:
        if not ready or accepted_package is not None:
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=False,
                    status="skipped",
                    reason_code=(
                        "validated_draft_already_available"
                        if accepted_package is not None
                        else "application_context_not_ready"
                    ),
                    provider_requests=0,
                )
            )
            continue

        observation = model(stage)
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        cost = float(observation.estimated_cost_usd or 0.0)
        campaign_cost += max(0.0, cost)

        if (
            observation.draft_approval_authority
            or observation.application_authority
            or observation.submission_authority
            or observation.product_authority
        ):
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_application_authority_claim_rejected",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break

        if (
            cost < 0
            or cost > APPLICATION_DRAFT_HARD_COST_CEILING_USD[stage]
            or campaign_cost > APPLICATION_DRAFT_CAMPAIGN_COST_CEILING_USD
        ):
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="application_quality_cost_ceiling_exceeded",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break

        if observation.status == "completed" and observation.package is not None:
            accepted_package = observation.package
            stages.append(
                ApplicationDraftStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="draft_for_review",
                    reason_code="source_grounded_quality_draft_validated",
                    provider_requests=request_count,
                    package_fingerprint=_package_fingerprint(observation.package),
                    estimated_cost_usd=cost,
                )
            )
            continue

        stages.append(
            ApplicationDraftStageEvidence(
                stage=stage,
                attempted=observation.request_attempted,
                status="unresolved",
                reason_code=(
                    "draft_validation_failed_closed"
                    if observation.status == "failed_closed"
                    else "no_validated_draft"
                ),
                provider_requests=request_count,
                estimated_cost_usd=cost,
            )
        )

    stages.append(
        ApplicationDraftStageEvidence(
            stage=BoosterStage.DEEP_EVIDENCE,
            attempted=False,
            status="skipped",
            reason_code="deep_external_evidence_not_activated_for_application_drafting",
            provider_requests=0,
        )
    )
    return ProductV1ApplicationDraftExecution(
        context=context,
        package=accepted_package,
        stages=tuple(stages),
        provider_requests=provider_requests,
        llm_requests=provider_requests,
    )


__all__ = [
    "APPLICATION_DRAFT_CAMPAIGN_COST_CEILING_USD",
    "APPLICATION_DRAFT_HARD_COST_CEILING_USD",
    "execute_quality_application_drafter",
]
