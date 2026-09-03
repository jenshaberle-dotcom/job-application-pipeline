from types import SimpleNamespace

from src.search_intelligence.llm_booster_policy import BoosterStage
from src.search_intelligence.product_v1_application_drafter import (
    ApplicationDraftObservation,
    ApplicationDraftPackage,
)
from src.search_intelligence.product_v1_application_quality_campaign import (
    APPLICATION_DRAFT_HARD_COST_CEILING_USD,
    execute_quality_application_drafter,
)


def _context():
    return SimpleNamespace(
        generation_ready=True,
        claim_plan=(SimpleNamespace(fact_key="candidate.fact"),),
        source_manifest=lambda: {"candidate_fact_keys": ["candidate.fact"]},
    )


def _package():
    return ApplicationDraftPackage(
        status="draft_for_review",
        fragments=(),
        rationale="validated by the callback fixture",
        source_manifest_sha256="a" * 64,
        candidate_fact_keys_used=("candidate.fact",),
    )


def test_application_surface_accepts_valid_luna_draft_above_origin_prompt_ceiling() -> None:
    assert APPLICATION_DRAFT_HARD_COST_CEILING_USD[BoosterStage.LUNA_MEDIUM] == 0.05

    def model(stage: BoosterStage) -> ApplicationDraftObservation:
        assert stage is BoosterStage.LUNA_MEDIUM
        return ApplicationDraftObservation(
            status="completed",
            request_attempted=True,
            package=_package(),
            model="gpt-5.6-luna",
            estimated_cost_usd=0.03,
        )

    execution = execute_quality_application_drafter(context=_context(), model=model)

    assert execution.package is not None
    assert execution.provider_requests == 1
    attempted = [stage for stage in execution.stages if stage.attempted and stage.provider_requests]
    assert len(attempted) == 1
    assert attempted[0].status == "draft_for_review"


def test_application_surface_still_fails_closed_above_its_own_ceiling() -> None:
    def model(stage: BoosterStage) -> ApplicationDraftObservation:
        assert stage is BoosterStage.LUNA_MEDIUM
        return ApplicationDraftObservation(
            status="completed",
            request_attempted=True,
            package=_package(),
            model="gpt-5.6-luna",
            estimated_cost_usd=0.051,
        )

    execution = execute_quality_application_drafter(context=_context(), model=model)

    assert execution.package is None
    assert execution.provider_requests == 1
    failed = [stage for stage in execution.stages if stage.status == "failed_closed"]
    assert len(failed) == 1
    assert failed[0].reason_code == "application_quality_cost_ceiling_exceeded"
