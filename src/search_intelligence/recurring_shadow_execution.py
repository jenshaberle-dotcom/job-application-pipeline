"""Bounded product-neutral recurring shadow execution for LLM-BOOST-001.

This controller may execute provider/model callbacks only after the pure
``RecurringShadowSelection`` contract has made a truthful cross-execution case
eligible. Provider output is only a hypothesis. A separate deterministic
validator owns rescue/progress evidence; neither callback can write product
state or claim product authority here.

The module itself performs no network, database, lifecycle, ranking, application
or product operation. Callbacks are injected explicitly so the complete envelope
is synthetically testable without a live provider.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
import hashlib
import json

from src.search_intelligence.llm_booster_policy import (
    BoosterPlan,
    BoosterStage,
    BoosterSurface,
    PlannedStage,
)
from src.search_intelligence.recurring_connector_economics import (
    OpportunityCostObservation,
    RecurringEvidenceRecord,
    RecurringOpportunityCostLedger,
)
from src.search_intelligence.recurring_shadow_selection import RecurringShadowSelection


@dataclass(frozen=True)
class RecurringShadowHypothesisObservation:
    """One provider-produced shadow hypothesis with no truth authority."""

    status: str
    request_attempted: bool
    hypothesis: Mapping[str, object]
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0
    provider: str | None = None
    model: str | None = None
    response_id: str | None = None
    product_authority: bool = False


@dataclass(frozen=True)
class RecurringShadowValidationObservation:
    """Independent deterministic validation of one provider hypothesis."""

    validated_rescue: bool
    progressed: bool
    reason_code: str
    product_authority: bool = False


StageCallback = Callable[
    [PlannedStage, Mapping[str, object]],
    RecurringShadowHypothesisObservation,
]
ValidateCallback = Callable[
    [PlannedStage, Mapping[str, object], RecurringEvidenceRecord],
    RecurringShadowValidationObservation,
]


@dataclass(frozen=True)
class RecurringShadowStageEvidence:
    stage: BoosterStage
    attempted: bool
    status: str
    reason_code: str
    provider_requests: int
    llm_requests: int
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0
    hypothesis_fingerprint: str | None = None
    hypothesis_field_names: tuple[str, ...] = ()
    validated_rescue: bool = False
    progressed: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        payload["hypothesis_field_names"] = list(self.hypothesis_field_names)
        return payload


@dataclass(frozen=True)
class RecurringShadowExecution:
    fingerprint: str
    selection_reason_code: str
    plan: BoosterPlan | None
    stages: tuple[RecurringShadowStageEvidence, ...]
    shadow_sample_eligible: bool
    validated_rescue: bool
    progressed: bool
    provider_requests: int
    llm_requests: int
    estimated_cost_usd: float
    latency_ms: int
    product_writes: int = 0
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "selection_reason_code": self.selection_reason_code,
            "plan": self.plan.to_json() if self.plan else None,
            "stages": [stage.to_json() for stage in self.stages],
            "shadow_sample_eligible": self.shadow_sample_eligible,
            "validated_rescue": self.validated_rescue,
            "progressed": self.progressed,
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "estimated_cost_usd": round(self.estimated_cost_usd, 8),
            "latency_ms": self.latency_ms,
            "product_writes": self.product_writes,
            "product_authority": self.product_authority,
        }


def _canonical_hypothesis_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("shadow hypothesis cannot contain non-finite floats")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TypeError("shadow hypothesis mapping keys must be strings")
            normalized[key] = _canonical_hypothesis_value(nested)
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, (list, tuple)):
        return [_canonical_hypothesis_value(item) for item in value]
    raise TypeError("shadow hypothesis must be JSON-compatible")


def recurring_shadow_hypothesis_fingerprint(hypothesis: Mapping[str, object]) -> str:
    canonical = _canonical_hypothesis_value(hypothesis)
    encoded = json.dumps(
        canonical,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _skipped_stage(stage: PlannedStage, reason_code: str) -> RecurringShadowStageEvidence:
    return RecurringShadowStageEvidence(
        stage=stage.stage,
        attempted=False,
        status="skipped",
        reason_code=reason_code,
        provider_requests=0,
        llm_requests=0,
    )


def _execution(
    *,
    current: RecurringEvidenceRecord,
    selection: RecurringShadowSelection,
    plan: BoosterPlan | None,
    stages: list[RecurringShadowStageEvidence],
) -> RecurringShadowExecution:
    return RecurringShadowExecution(
        fingerprint=current.fingerprint,
        selection_reason_code=selection.reason_code,
        plan=plan,
        stages=tuple(stages),
        shadow_sample_eligible=selection.shadow_sample_eligible,
        validated_rescue=any(stage.validated_rescue for stage in stages),
        progressed=any(stage.progressed for stage in stages),
        provider_requests=sum(stage.provider_requests for stage in stages),
        llm_requests=sum(stage.llm_requests for stage in stages),
        estimated_cost_usd=sum(stage.estimated_cost_usd for stage in stages),
        latency_ms=sum(stage.latency_ms for stage in stages),
    )


def _skip_tail(
    *,
    stages: list[RecurringShadowStageEvidence],
    remaining: tuple[PlannedStage, ...],
    reason_code: str,
) -> None:
    stages.extend(_skipped_stage(stage, reason_code) for stage in remaining)


def _record_spend(
    *,
    ledger: RecurringOpportunityCostLedger,
    current: RecurringEvidenceRecord,
    selection: RecurringShadowSelection,
    planned: PlannedStage,
    provider_requests: int,
    llm_requests: int,
    cost_usd: float,
    latency_ms: int,
    validated_rescue: bool,
    progressed: bool,
) -> bool:
    economics = selection.economics_decision
    if economics is None:
        return False
    return ledger.record(
        OpportunityCostObservation(
            fingerprint=current.fingerprint,
            delta_kind=economics.delta_kind,
            gap_kind=economics.gap_kind,
            stage=planned.stage,
            provider_requests=provider_requests,
            llm_requests=llm_requests,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            validated_rescue=validated_rescue,
            progressed=progressed,
        )
    )


def execute_recurring_shadow(
    *,
    selection: RecurringShadowSelection,
    current: RecurringEvidenceRecord,
    shadow_context: Mapping[str, object],
    ledger: RecurringOpportunityCostLedger,
    execute_stage: StageCallback,
    validate: ValidateCallback,
) -> RecurringShadowExecution:
    """Execute one bounded recurring shadow cascade with deterministic validation."""

    economics = selection.economics_decision
    plan = economics.booster_plan if economics is not None else None
    stages: list[RecurringShadowStageEvidence] = []

    if (
        not selection.shadow_sample_eligible
        or economics is None
        or not economics.booster_eligible
        or plan is None
    ):
        if plan is not None:
            stages.extend(
                _skipped_stage(stage, "recurring_shadow_selection_not_eligible")
                for stage in plan.stages
            )
        return _execution(
            current=current,
            selection=selection,
            plan=plan,
            stages=stages,
        )

    if (
        economics.fingerprint != current.fingerprint
        or plan.surface != BoosterSurface.RECURRING_CONNECTOR
        or plan.product_authority
        or economics.product_authority
        or selection.product_authority
    ):
        if plan.stages:
            stages.extend(
                _skipped_stage(stage, "recurring_shadow_authority_invariant_failed")
                for stage in plan.stages
            )
        return _execution(
            current=current,
            selection=selection,
            plan=plan,
            stages=stages,
        )

    deterministic = plan.stages[0]
    if deterministic.stage != BoosterStage.DETERMINISTIC:
        stages.extend(
            _skipped_stage(stage, "recurring_shadow_plan_order_invalid")
            for stage in plan.stages
        )
        return _execution(
            current=current,
            selection=selection,
            plan=plan,
            stages=stages,
        )
    stages.append(
        RecurringShadowStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=False,
            status="already_completed",
            reason_code=deterministic.reason_code,
            provider_requests=0,
            llm_requests=0,
        )
    )

    external_stages = tuple(plan.stages[1:])
    for index, planned in enumerate(external_stages):
        remaining = external_stages[index + 1 :]

        if planned.stage == BoosterStage.DEEP_EVIDENCE:
            stages.append(
                RecurringShadowStageEvidence(
                    stage=planned.stage,
                    attempted=False,
                    status="residual_unresolved",
                    reason_code=planned.reason_code,
                    provider_requests=0,
                    llm_requests=0,
                )
            )
            break

        if not planned.eligible:
            stages.append(_skipped_stage(planned, planned.reason_code))
            continue

        if ledger.contains(fingerprint=current.fingerprint, stage=planned.stage):
            stages.append(
                _skipped_stage(planned, "duplicate_shadow_stage_spend_suppressed")
            )
            _skip_tail(
                stages=stages,
                remaining=remaining,
                reason_code="duplicate_shadow_stage_requires_new_evidence",
            )
            break

        observation = execute_stage(planned, shadow_context)
        provider_requests = int(observation.request_attempted)
        llm_requests = int(observation.request_attempted and planned.model is not None)
        cost = float(observation.estimated_cost_usd)
        latency = int(observation.latency_ms)

        boundary_failure: str | None = None
        hypothesis_fingerprint: str | None = None
        hypothesis_fields: tuple[str, ...] = ()
        if observation.product_authority:
            boundary_failure = "provider_product_authority_claim_rejected"
        elif cost < 0:
            boundary_failure = "negative_shadow_cost_rejected"
        elif latency < 0:
            boundary_failure = "negative_shadow_latency_rejected"
        elif not observation.request_attempted and (
            cost != 0.0 or latency != 0 or observation.hypothesis
        ):
            boundary_failure = "non_attempted_shadow_stage_has_effects"
        elif observation.request_attempted and observation.status != "completed":
            boundary_failure = "shadow_provider_stage_not_completed"
        else:
            try:
                hypothesis_fingerprint = recurring_shadow_hypothesis_fingerprint(
                    observation.hypothesis
                )
                hypothesis_fields = tuple(sorted(observation.hypothesis))
            except (TypeError, ValueError):
                boundary_failure = "invalid_shadow_hypothesis_payload"

        ceiling = planned.hard_cost_ceiling_usd
        if (
            boundary_failure is None
            and ceiling is not None
            and cost > float(ceiling)
        ):
            boundary_failure = "shadow_stage_cost_ceiling_exceeded"

        if boundary_failure is not None:
            if observation.request_attempted and cost >= 0 and latency >= 0:
                _record_spend(
                    ledger=ledger,
                    current=current,
                    selection=selection,
                    planned=planned,
                    provider_requests=provider_requests,
                    llm_requests=llm_requests,
                    cost_usd=cost,
                    latency_ms=latency,
                    validated_rescue=False,
                    progressed=False,
                )
            stages.append(
                RecurringShadowStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code=boundary_failure,
                    provider_requests=provider_requests,
                    llm_requests=llm_requests,
                    estimated_cost_usd=max(0.0, cost),
                    latency_ms=max(0, latency),
                    hypothesis_fingerprint=hypothesis_fingerprint,
                    hypothesis_field_names=hypothesis_fields,
                )
            )
            _skip_tail(
                stages=stages,
                remaining=remaining,
                reason_code="prior_shadow_stage_failed_closed",
            )
            break

        validation = validate(planned, observation.hypothesis, current)
        validation_failure: str | None = None
        if validation.product_authority:
            validation_failure = "validator_product_authority_claim_rejected"
        elif validation.validated_rescue and not validation.progressed:
            validation_failure = "validated_rescue_without_progress_rejected"

        if validation_failure is not None:
            _record_spend(
                ledger=ledger,
                current=current,
                selection=selection,
                planned=planned,
                provider_requests=provider_requests,
                llm_requests=llm_requests,
                cost_usd=cost,
                latency_ms=latency,
                validated_rescue=False,
                progressed=False,
            )
            stages.append(
                RecurringShadowStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code=validation_failure,
                    provider_requests=provider_requests,
                    llm_requests=llm_requests,
                    estimated_cost_usd=cost,
                    latency_ms=latency,
                    hypothesis_fingerprint=hypothesis_fingerprint,
                    hypothesis_field_names=hypothesis_fields,
                )
            )
            _skip_tail(
                stages=stages,
                remaining=remaining,
                reason_code="prior_shadow_stage_failed_closed",
            )
            break

        recorded = _record_spend(
            ledger=ledger,
            current=current,
            selection=selection,
            planned=planned,
            provider_requests=provider_requests,
            llm_requests=llm_requests,
            cost_usd=cost,
            latency_ms=latency,
            validated_rescue=validation.validated_rescue,
            progressed=validation.progressed,
        )
        if not recorded:
            stages.append(
                RecurringShadowStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="shadow_economics_duplicate_race_rejected",
                    provider_requests=provider_requests,
                    llm_requests=llm_requests,
                    estimated_cost_usd=cost,
                    latency_ms=latency,
                    hypothesis_fingerprint=hypothesis_fingerprint,
                    hypothesis_field_names=hypothesis_fields,
                )
            )
            _skip_tail(
                stages=stages,
                remaining=remaining,
                reason_code="prior_shadow_stage_failed_closed",
            )
            break

        stages.append(
            RecurringShadowStageEvidence(
                stage=planned.stage,
                attempted=observation.request_attempted,
                status=("validated_rescue" if validation.validated_rescue else "unresolved"),
                reason_code=validation.reason_code,
                provider_requests=provider_requests,
                llm_requests=llm_requests,
                estimated_cost_usd=cost,
                latency_ms=latency,
                hypothesis_fingerprint=hypothesis_fingerprint,
                hypothesis_field_names=hypothesis_fields,
                validated_rescue=validation.validated_rescue,
                progressed=validation.progressed,
            )
        )

        if validation.validated_rescue:
            _skip_tail(
                stages=stages,
                remaining=remaining,
                reason_code="prior_shadow_stage_validated_rescue",
            )
            break

    return _execution(
        current=current,
        selection=selection,
        plan=plan,
        stages=stages,
    )


__all__ = [
    "RecurringShadowExecution",
    "RecurringShadowHypothesisObservation",
    "RecurringShadowStageEvidence",
    "RecurringShadowValidationObservation",
    "execute_recurring_shadow",
    "recurring_shadow_hypothesis_fingerprint",
]
