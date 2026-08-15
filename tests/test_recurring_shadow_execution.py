from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState
from src.search_intelligence.recurring_connector_economics import (
    RecurringDeterministicOutcome,
    RecurringGapKind,
    RecurringOpportunityCostLedger,
    build_recurring_evidence_record,
)
from src.search_intelligence.recurring_observation_delta_projection import (
    RecurringObservationSnapshot,
    project_recurring_observation_deltas,
)
from src.search_intelligence.recurring_shadow_execution import (
    RecurringShadowHypothesisObservation,
    RecurringShadowValidationObservation,
    execute_recurring_shadow,
    recurring_shadow_hypothesis_fingerprint,
)
from src.search_intelligence.recurring_shadow_selection import (
    select_recurring_shadow_candidate,
)

BASE = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
CONNECTOR = "personio:bridgingit"
JOB_ID = "job-42"
URL = "https://bridgingit.jobs.personio.de/job/42"
OBS_CONTRACT = "recurring-observation-evidence.v1"
EXEC_A = "11111111-1111-4111-8111-111111111111"
EXEC_B = "22222222-2222-4222-8222-222222222222"


def _record(outcome: RecurringDeterministicOutcome):
    return build_recurring_evidence_record(
        connector_id=CONNECTOR,
        external_job_id=JOB_ID,
        source_url=URL,
        evidence={"title": "Current", "location": "Hannover"},
        deterministic_outcome=outcome,
    )


def _snapshot(
    *,
    evidence_hash: str,
    minutes: int,
    execution_id: str,
) -> RecurringObservationSnapshot:
    return RecurringObservationSnapshot(
        source_name=CONNECTOR,
        external_job_id=JOB_ID,
        source_url=URL,
        observed_at=BASE + timedelta(minutes=minutes),
        normalized_evidence_hash=evidence_hash,
        evidence_contract_version=OBS_CONTRACT,
        execution_id=execution_id,
    )


def _changed_selection(
    *,
    gap: RecurringGapKind = RecurringGapKind.SEMANTIC_AMBIGUITY,
    tavily_state: TavilyState = TavilyState.DISABLED,
):
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    previous_hash = "a" * 64
    if previous_hash == current.normalized_evidence_hash:
        previous_hash = "b" * 64
    projection = project_recurring_observation_deltas(
        [
            _snapshot(
                evidence_hash=previous_hash,
                minutes=0,
                execution_id=EXEC_A,
            ),
            _snapshot(
                evidence_hash=current.normalized_evidence_hash,
                minutes=1,
                execution_id=EXEC_B,
            ),
        ]
    )[-1]
    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=gap,
        tavily_state=tavily_state,
    )
    assert selection.shadow_sample_eligible is True
    return current, selection


def _unchanged_selection():
    current = _record(RecurringDeterministicOutcome.UNRESOLVED)
    projection = project_recurring_observation_deltas(
        [
            _snapshot(
                evidence_hash=current.normalized_evidence_hash,
                minutes=0,
                execution_id=EXEC_A,
            ),
            _snapshot(
                evidence_hash=current.normalized_evidence_hash,
                minutes=1,
                execution_id=EXEC_B,
            ),
        ]
    )[-1]
    selection = select_recurring_shadow_candidate(
        projection=projection,
        current=current,
        gap_kind=RecurringGapKind.SEMANTIC_AMBIGUITY,
        tavily_state=TavilyState.DISABLED,
    )
    assert selection.shadow_sample_eligible is False
    return current, selection


def _completed_hypothesis(
    stage,
    _context,
    *,
    cost: float = 0.001,
    product_authority: bool = False,
):
    return RecurringShadowHypothesisObservation(
        status="completed",
        request_attempted=True,
        hypothesis={"stage": stage.stage.value, "candidate": "bounded"},
        estimated_cost_usd=cost,
        latency_ms=20,
        provider=stage.provider,
        model=stage.model,
        product_authority=product_authority,
    )


def test_ineligible_unchanged_selection_never_invokes_callbacks() -> None:
    current, selection = _unchanged_selection()
    ledger = RecurringOpportunityCostLedger()

    def forbidden_stage(*_args, **_kwargs):
        raise AssertionError("provider callback must not run")

    def forbidden_validate(*_args, **_kwargs):
        raise AssertionError("validator must not run")

    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={"redacted": True},
        ledger=ledger,
        execute_stage=forbidden_stage,
        validate=forbidden_validate,
    )

    assert result.shadow_sample_eligible is False
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert result.estimated_cost_usd == 0.0
    assert result.product_writes == 0
    assert result.product_authority is False
    assert ledger.summary()["observation_count"] == 0


def test_semantic_shadow_uses_canonical_model_order_and_stops_after_validated_rescue() -> None:
    current, selection = _changed_selection()
    ledger = RecurringOpportunityCostLedger()
    called: list[BoosterStage] = []

    def stage_callback(stage, context):
        assert context == {"redacted": True}
        called.append(stage.stage)
        return _completed_hypothesis(stage, context)

    def validate(stage, hypothesis, record):
        assert record == current
        assert hypothesis["stage"] == stage.stage.value
        rescue = stage.stage == BoosterStage.TERRA_MEDIUM
        return RecurringShadowValidationObservation(
            validated_rescue=rescue,
            progressed=True,
            reason_code=("deterministic_rescue_validated" if rescue else "validated_progress"),
        )

    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={"redacted": True},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=validate,
    )

    assert called == [BoosterStage.LUNA_MEDIUM, BoosterStage.TERRA_MEDIUM]
    assert result.validated_rescue is True
    assert result.progressed is True
    assert result.provider_requests == 2
    assert result.llm_requests == 2
    assert result.product_authority is False
    terra = next(stage for stage in result.stages if stage.stage == BoosterStage.TERRA_MEDIUM)
    assert terra.status == "validated_rescue"
    assert all(
        stage.attempted is False
        for stage in result.stages
        if stage.stage in {BoosterStage.SOL_MEDIUM, BoosterStage.LUNA_MAX}
    )
    summary = ledger.summary()
    assert summary["observation_count"] == 2
    assert summary["validated_rescues"] == 1
    assert summary["product_authority"] is False


def test_external_information_shadow_can_validate_tavily_and_skip_models() -> None:
    current, selection = _changed_selection(
        gap=RecurringGapKind.EXTERNAL_INFORMATION,
        tavily_state=TavilyState.AVAILABLE,
    )
    ledger = RecurringOpportunityCostLedger()
    called: list[BoosterStage] = []

    def stage_callback(stage, context):
        called.append(stage.stage)
        return _completed_hypothesis(stage, context, cost=0.0)

    def validate(stage, _hypothesis, _record):
        return RecurringShadowValidationObservation(
            validated_rescue=True,
            progressed=True,
            reason_code="external_information_rescue_validated",
        )

    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=validate,
    )

    assert called == [BoosterStage.TAVILY]
    assert result.provider_requests == 1
    assert result.llm_requests == 0
    assert result.validated_rescue is True
    tavily = next(stage for stage in result.stages if stage.stage == BoosterStage.TAVILY)
    assert tavily.status == "validated_rescue"


def test_model_hard_cost_ceiling_fails_closed_and_records_observed_spend() -> None:
    current, selection = _changed_selection()
    ledger = RecurringOpportunityCostLedger()
    validator_calls = 0

    def stage_callback(stage, context):
        assert stage.stage == BoosterStage.LUNA_MEDIUM
        return _completed_hypothesis(stage, context, cost=0.011)

    def validate(*_args):
        nonlocal validator_calls
        validator_calls += 1
        raise AssertionError("over-ceiling hypothesis must not be validated")

    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=validate,
    )

    assert validator_calls == 0
    luna = next(stage for stage in result.stages if stage.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "shadow_stage_cost_ceiling_exceeded"
    assert result.provider_requests == 1
    assert result.llm_requests == 1
    assert result.estimated_cost_usd == pytest.approx(0.011)
    assert ledger.summary()["total_cost_usd"] == pytest.approx(0.011)


def test_provider_product_authority_claim_is_rejected_and_stops_cascade() -> None:
    current, selection = _changed_selection()
    ledger = RecurringOpportunityCostLedger()

    def stage_callback(stage, context):
        return _completed_hypothesis(
            stage,
            context,
            product_authority=True,
        )

    def forbidden_validate(*_args):
        raise AssertionError("authority-claiming provider output must not be validated")

    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=forbidden_validate,
    )

    luna = next(stage for stage in result.stages if stage.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "provider_product_authority_claim_rejected"
    assert result.provider_requests == 1
    assert result.product_authority is False
    assert result.product_writes == 0


def test_validator_product_authority_claim_is_rejected() -> None:
    current, selection = _changed_selection()
    ledger = RecurringOpportunityCostLedger()

    def stage_callback(stage, context):
        return _completed_hypothesis(stage, context)

    def validate(*_args):
        return RecurringShadowValidationObservation(
            validated_rescue=True,
            progressed=True,
            reason_code="invalid_authority_claim",
            product_authority=True,
        )

    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=validate,
    )

    luna = next(stage for stage in result.stages if stage.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "validator_product_authority_claim_rejected"
    assert result.validated_rescue is False
    assert result.product_authority is False


def test_shared_ledger_suppresses_same_fingerprint_stage_before_second_callback() -> None:
    current, selection = _changed_selection()
    ledger = RecurringOpportunityCostLedger()
    calls = 0

    def stage_callback(stage, context):
        nonlocal calls
        calls += 1
        return _completed_hypothesis(stage, context)

    def validate(*_args):
        return RecurringShadowValidationObservation(
            validated_rescue=True,
            progressed=True,
            reason_code="rescue",
        )

    first = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=validate,
    )
    second = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=validate,
    )

    assert first.provider_requests == 1
    assert second.provider_requests == 0
    assert calls == 1
    duplicate = next(
        stage for stage in second.stages if stage.stage == BoosterStage.LUNA_MEDIUM
    )
    assert duplicate.reason_code == "duplicate_shadow_stage_spend_suppressed"
    assert ledger.summary()["observation_count"] == 1


def test_non_attempted_stage_with_effects_fails_closed_without_validation() -> None:
    current, selection = _changed_selection()
    ledger = RecurringOpportunityCostLedger()

    def stage_callback(stage, _context):
        return RecurringShadowHypothesisObservation(
            status="completed",
            request_attempted=False,
            hypothesis={"unexpected": True},
            estimated_cost_usd=0.001,
            latency_ms=1,
            model=stage.model,
        )

    def forbidden_validate(*_args):
        raise AssertionError("invalid non-attempted stage must not be validated")

    result = execute_recurring_shadow(
        selection=selection,
        current=current,
        shadow_context={},
        ledger=ledger,
        execute_stage=stage_callback,
        validate=forbidden_validate,
    )

    luna = next(stage for stage in result.stages if stage.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "non_attempted_shadow_stage_has_effects"
    assert result.provider_requests == 0
    assert ledger.summary()["observation_count"] == 0


def test_hypothesis_fingerprint_is_order_stable_and_payload_is_not_exposed() -> None:
    first = recurring_shadow_hypothesis_fingerprint(
        {"b": [2, 1], "a": {"x": "value"}}
    )
    second = recurring_shadow_hypothesis_fingerprint(
        {"a": {"x": "value"}, "b": [2, 1]}
    )

    assert first == second
