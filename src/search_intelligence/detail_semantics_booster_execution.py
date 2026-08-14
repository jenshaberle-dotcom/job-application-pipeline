"""Authority-neutral Detail Semantics booster execution for LLM-BOOST-001.

This controller executes only the semantic model portion of the canonical booster
plan after the pure Detail Semantics gap contract has made it eligible. Ordinary
semantic ambiguity never invokes Tavily here. Model callbacks may propose role,
seniority, skills, location and remote hypotheses only when each proposed field
has bounded evidence on the already-supported detail page.

Semantic resolution means that the bounded requested semantic field set has been
filled through deterministic validation. Existing profile/geography product
contracts are retained as independent authority observations; they neither grant
semantic completeness nor become writable from this controller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Callable, Mapping

from src.search_intelligence.detail_semantics_gap import (
    DetailSemanticsGapDecision,
    SEMANTIC_FIELD_NAMES,
    SemanticEvidenceReference,
)
from src.search_intelligence.llm_booster_policy import BoosterStage, PlannedStage


@dataclass
class SemanticProgressLedger:
    """Per-case semantic identity ledger shared by all model stages."""

    attempted_hypothesis_fingerprints: set[str] = field(default_factory=set)

    def novel_hypothesis(self, fingerprint: str) -> bool:
        normalized = str(fingerprint or "").strip()
        if not normalized or normalized in self.attempted_hypothesis_fingerprints:
            return False
        self.attempted_hypothesis_fingerprints.add(normalized)
        return True

    def to_json(self) -> dict[str, object]:
        return {
            "attempted_hypothesis_fingerprints": sorted(
                self.attempted_hypothesis_fingerprints
            )
        }


@dataclass(frozen=True)
class DetailSemanticsHypothesisObservation:
    status: str
    request_attempted: bool
    semantic_fields: Mapping[str, object]
    evidence_references: tuple[SemanticEvidenceReference, ...]
    model: str | None = None
    response_id: str | None = None
    estimated_cost_usd: float = 0.0
    rationale: str = ""
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "status": self.status,
            "request_attempted": self.request_attempted,
            "semantic_fields": dict(self.semantic_fields),
            "evidence_references": [
                item.to_json() for item in self.evidence_references
            ],
            "model": self.model,
            "response_id": self.response_id,
            "estimated_cost_usd": self.estimated_cost_usd,
            "rationale": self.rationale,
            "product_authority": self.product_authority,
        }


@dataclass(frozen=True)
class DetailSemanticsValidationObservation:
    """Deterministic validation result for one model semantic hypothesis."""

    accepted: bool
    classification: str
    profile_contract_satisfied: bool
    geography_contract_satisfied: bool
    accepted_semantic_fields: Mapping[str, object]
    accepted_evidence_references: tuple[SemanticEvidenceReference, ...]
    failure_reason: str | None = None
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "classification": self.classification,
            "profile_contract_satisfied": self.profile_contract_satisfied,
            "geography_contract_satisfied": self.geography_contract_satisfied,
            "accepted_semantic_fields": dict(self.accepted_semantic_fields),
            "accepted_evidence_references": [
                item.to_json() for item in self.accepted_evidence_references
            ],
            "failure_reason": self.failure_reason,
            "product_authority": self.product_authority,
        }


ModelCallback = Callable[
    [
        BoosterStage,
        Mapping[str, object],
        tuple[SemanticEvidenceReference, ...],
        SemanticProgressLedger,
    ],
    DetailSemanticsHypothesisObservation,
]
ValidateCallback = Callable[
    [DetailSemanticsHypothesisObservation],
    DetailSemanticsValidationObservation,
]


@dataclass(frozen=True)
class DetailSemanticsBoosterStageEvidence:
    stage: BoosterStage
    attempted: bool
    status: str
    reason_code: str
    provider_requests: int
    produced_field_names: tuple[str, ...] = ()
    evidence_reference_count: int = 0
    hypothesis_fingerprint: str | None = None
    deterministic_validation_outcome: str | None = None
    progressed: bool = False
    estimated_cost_usd: float = 0.0
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        payload["produced_field_names"] = list(self.produced_field_names)
        return payload


@dataclass(frozen=True)
class DetailSemanticsBoosterExecution:
    gap_fingerprint: str
    unchanged_evidence_skip: bool
    deterministic_resolved: bool
    requested_semantic_fields: tuple[str, ...]
    stages: tuple[DetailSemanticsBoosterStageEvidence, ...]
    semantic_fields: Mapping[str, object]
    evidence_references: tuple[SemanticEvidenceReference, ...]
    profile_contract_satisfied: bool
    geography_contract_satisfied: bool
    provider_requests: int
    llm_requests: int
    product_writes: int = 0
    semantic_authority: bool = False
    product_authority: bool = False

    @property
    def missing_semantic_fields(self) -> tuple[str, ...]:
        return tuple(
            field
            for field in self.requested_semantic_fields
            if field not in self.semantic_fields
        )

    @property
    def resolved(self) -> bool:
        return bool(self.deterministic_resolved or not self.missing_semantic_fields)

    @property
    def estimated_model_cost_usd(self) -> float:
        return sum(item.estimated_cost_usd for item in self.stages)

    def to_json(self) -> dict[str, object]:
        return {
            "gap_fingerprint": self.gap_fingerprint,
            "unchanged_evidence_skip": self.unchanged_evidence_skip,
            "deterministic_resolved": self.deterministic_resolved,
            "requested_semantic_fields": list(self.requested_semantic_fields),
            "missing_semantic_fields": list(self.missing_semantic_fields),
            "stages": [item.to_json() for item in self.stages],
            "semantic_fields": dict(self.semantic_fields),
            "evidence_references": [
                item.to_json() for item in self.evidence_references
            ],
            "profile_contract_satisfied": self.profile_contract_satisfied,
            "geography_contract_satisfied": self.geography_contract_satisfied,
            "resolved": self.resolved,
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "estimated_model_cost_usd": round(self.estimated_model_cost_usd, 8),
            "product_writes": self.product_writes,
            "semantic_authority": self.semantic_authority,
            "product_authority": self.product_authority,
        }


def _normalize_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item) for item in value]
    if isinstance(value, set):
        return sorted((_normalize_json(item) for item in value), key=repr)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def semantic_hypothesis_fingerprint(
    *,
    semantic_fields: Mapping[str, object],
    evidence_references: tuple[SemanticEvidenceReference, ...],
) -> str:
    """Stable identity for one model-produced semantic hypothesis."""

    field_names = {str(key).strip().lower() for key in semantic_fields}
    unsupported = sorted(field_names.difference(SEMANTIC_FIELD_NAMES))
    if unsupported:
        raise ValueError(f"unsupported semantic hypothesis fields: {unsupported}")
    payload = {
        "semantic_fields": {
            str(key).strip().lower(): _normalize_json(value)
            for key, value in sorted(
                semantic_fields.items(), key=lambda pair: str(pair[0])
            )
        },
        "evidence_references": [
            item.to_json()
            for item in sorted(
                evidence_references,
                key=lambda item: (
                    item.field,
                    item.source_url,
                    item.span_start if item.span_start is not None else -1,
                    item.span_end if item.span_end is not None else -1,
                    item.value or "",
                    item.evidence,
                ),
            )
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _skipped_stage(
    stage: PlannedStage, reason: str
) -> DetailSemanticsBoosterStageEvidence:
    return DetailSemanticsBoosterStageEvidence(
        stage=stage.stage,
        attempted=False,
        status="skipped",
        reason_code=reason,
        provider_requests=0,
    )


def _reference_failure_reason(
    *,
    detail_url: str,
    field_names: tuple[str, ...],
    references: tuple[SemanticEvidenceReference, ...],
) -> str | None:
    reference_fields: set[str] = set()
    for reference in references:
        if reference.field not in SEMANTIC_FIELD_NAMES:
            return "unsupported_evidence_reference_field"
        if reference.source_url.strip() != detail_url.strip():
            return "cross_detail_evidence_reference"
        if not reference.evidence.strip():
            return "empty_evidence_reference"
        if reference.span_start is None or reference.span_end is None:
            return "evidence_span_required"
        if reference.span_start < 0 or reference.span_end < reference.span_start:
            return "invalid_evidence_span"
        reference_fields.add(reference.field)
    if set(field_names).difference(reference_fields):
        return "missing_field_evidence_reference"
    return None


def _reference_identity(reference: SemanticEvidenceReference) -> tuple[object, ...]:
    return (
        reference.field,
        reference.source_url,
        reference.evidence,
        reference.value,
        reference.span_start,
        reference.span_end,
    )


def _validation_failure_reason(
    *,
    hypothesis: DetailSemanticsHypothesisObservation,
    validation: DetailSemanticsValidationObservation,
) -> str | None:
    accepted_names = {
        str(key).strip().lower() for key in validation.accepted_semantic_fields
    }
    hypothesis_names = {
        str(key).strip().lower() for key in hypothesis.semantic_fields
    }
    if accepted_names.difference(SEMANTIC_FIELD_NAMES):
        return "validator_returned_unsupported_semantic_field"
    if accepted_names.difference(hypothesis_names):
        return "validator_broadened_semantic_hypothesis"
    hypothesis_refs = {
        _reference_identity(reference) for reference in hypothesis.evidence_references
    }
    if any(
        _reference_identity(reference) not in hypothesis_refs
        for reference in validation.accepted_evidence_references
    ):
        return "validator_broadened_evidence_reference"
    if validation.accepted and not accepted_names:
        return "validator_accepted_empty_semantics"
    return None


def _missing_requested_fields(
    *,
    requested: tuple[str, ...],
    fields: Mapping[str, object],
) -> tuple[str, ...]:
    return tuple(field for field in requested if field not in fields)


def _fail_closed_tail(
    *,
    stages: list[DetailSemanticsBoosterStageEvidence],
    remaining: tuple[PlannedStage, ...],
    reason: str,
) -> None:
    stages.extend(_skipped_stage(stage, reason) for stage in remaining)


def execute_detail_semantics_booster(
    *,
    detail_url: str,
    decision: DetailSemanticsGapDecision,
    initial_semantic_fields: Mapping[str, object],
    initial_evidence_references: tuple[SemanticEvidenceReference, ...],
    model: ModelCallback,
    validate: ValidateCallback,
) -> DetailSemanticsBoosterExecution:
    """Execute bounded semantic hypotheses with deterministic final authority."""

    stage_records: list[DetailSemanticsBoosterStageEvidence] = []
    current_fields: dict[str, object] = dict(initial_semantic_fields)
    current_references: list[SemanticEvidenceReference] = list(
        initial_evidence_references
    )
    requested = decision.requested_semantic_fields
    profile_satisfied = decision.profile_contract_satisfied
    geography_satisfied = decision.geography_contract_satisfied
    provider_requests = 0
    llm_requests = 0
    ledger = SemanticProgressLedger()

    deterministic = decision.booster_plan.stages[0]
    stage_records.append(
        DetailSemanticsBoosterStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=decision.deterministic_attempted,
            status=(
                "resolved"
                if decision.deterministic_resolved
                else decision.classification
            ),
            reason_code=deterministic.reason_code,
            provider_requests=0,
            progressed=decision.deterministic_resolved,
        )
    )

    if not decision.semantic_booster_eligible:
        reason = (
            "unchanged_detail_semantic_evidence"
            if decision.unchanged_evidence_skip
            else "detail_semantic_booster_not_eligible"
        )
        stage_records.extend(
            _skipped_stage(stage, reason)
            for stage in decision.booster_plan.stages[1:]
        )
        return DetailSemanticsBoosterExecution(
            gap_fingerprint=decision.evidence_fingerprint,
            unchanged_evidence_skip=decision.unchanged_evidence_skip,
            deterministic_resolved=decision.deterministic_resolved,
            requested_semantic_fields=requested,
            stages=tuple(stage_records),
            semantic_fields=current_fields,
            evidence_references=tuple(current_references),
            profile_contract_satisfied=profile_satisfied,
            geography_contract_satisfied=geography_satisfied,
            provider_requests=0,
            llm_requests=0,
        )

    tavily = decision.booster_plan.stages[1]
    stage_records.append(_skipped_stage(tavily, tavily.reason_code))

    model_stages = tuple(decision.booster_plan.stages[2:6])
    for index, planned in enumerate(model_stages):
        observation = model(
            planned.stage,
            dict(current_fields),
            tuple(current_references),
            ledger,
        )
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        llm_requests += request_count
        field_names = tuple(
            sorted(str(key).strip().lower() for key in observation.semantic_fields)
        )
        estimated_cost = float(observation.estimated_cost_usd or 0.0)

        if observation.product_authority:
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_product_authority_claim_rejected",
                    provider_requests=request_count,
                    produced_field_names=field_names,
                    evidence_reference_count=len(observation.evidence_references),
                    estimated_cost_usd=estimated_cost,
                )
            )
            _fail_closed_tail(
                stages=stage_records,
                remaining=model_stages[index + 1 :]
                + (decision.booster_plan.stages[6],),
                reason="prior_stage_failed_closed",
            )
            break

        ceiling = planned.hard_cost_ceiling_usd
        if estimated_cost < 0 or (ceiling is not None and estimated_cost > ceiling):
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_cost_ceiling_exceeded",
                    provider_requests=request_count,
                    produced_field_names=field_names,
                    evidence_reference_count=len(observation.evidence_references),
                    estimated_cost_usd=estimated_cost,
                )
            )
            _fail_closed_tail(
                stages=stage_records,
                remaining=model_stages[index + 1 :]
                + (decision.booster_plan.stages[6],),
                reason="prior_stage_failed_closed",
            )
            break

        if observation.status != "completed":
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status=observation.status,
                    reason_code=planned.reason_code,
                    provider_requests=request_count,
                    estimated_cost_usd=estimated_cost,
                )
            )
            continue

        if not field_names:
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="no_semantic_hypothesis",
                    reason_code="model_returned_no_semantic_fields",
                    provider_requests=request_count,
                    estimated_cost_usd=estimated_cost,
                )
            )
            continue

        reference_failure = _reference_failure_reason(
            detail_url=detail_url,
            field_names=field_names,
            references=observation.evidence_references,
        )
        if reference_failure:
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code=reference_failure,
                    provider_requests=request_count,
                    produced_field_names=field_names,
                    evidence_reference_count=len(observation.evidence_references),
                    estimated_cost_usd=estimated_cost,
                )
            )
            continue

        try:
            hypothesis_fingerprint = semantic_hypothesis_fingerprint(
                semantic_fields=observation.semantic_fields,
                evidence_references=observation.evidence_references,
            )
        except ValueError:
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="unsupported_semantic_hypothesis_field",
                    provider_requests=request_count,
                    produced_field_names=field_names,
                    evidence_reference_count=len(observation.evidence_references),
                    estimated_cost_usd=estimated_cost,
                )
            )
            continue

        if not ledger.novel_hypothesis(hypothesis_fingerprint):
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="duplicate_no_progress",
                    reason_code="duplicate_semantic_hypothesis_fingerprint",
                    provider_requests=request_count,
                    produced_field_names=field_names,
                    evidence_reference_count=len(observation.evidence_references),
                    hypothesis_fingerprint=hypothesis_fingerprint,
                    estimated_cost_usd=estimated_cost,
                )
            )
            continue

        validation = validate(observation)
        if validation.product_authority:
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="validator_product_authority_claim_rejected",
                    provider_requests=request_count,
                    produced_field_names=field_names,
                    evidence_reference_count=len(observation.evidence_references),
                    hypothesis_fingerprint=hypothesis_fingerprint,
                    deterministic_validation_outcome=validation.classification,
                    estimated_cost_usd=estimated_cost,
                )
            )
            _fail_closed_tail(
                stages=stage_records,
                remaining=model_stages[index + 1 :]
                + (decision.booster_plan.stages[6],),
                reason="prior_stage_failed_closed",
            )
            break

        validation_failure = _validation_failure_reason(
            hypothesis=observation,
            validation=validation,
        )
        if validation_failure:
            stage_records.append(
                DetailSemanticsBoosterStageEvidence(
                    stage=planned.stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code=validation_failure,
                    provider_requests=request_count,
                    produced_field_names=field_names,
                    evidence_reference_count=len(observation.evidence_references),
                    hypothesis_fingerprint=hypothesis_fingerprint,
                    deterministic_validation_outcome=validation.classification,
                    estimated_cost_usd=estimated_cost,
                )
            )
            _fail_closed_tail(
                stages=stage_records,
                remaining=model_stages[index + 1 :]
                + (decision.booster_plan.stages[6],),
                reason="prior_stage_failed_closed",
            )
            break

        prior_missing = _missing_requested_fields(
            requested=requested,
            fields=current_fields,
        )
        if validation.accepted:
            current_fields.update(dict(validation.accepted_semantic_fields))
            for reference in validation.accepted_evidence_references:
                if reference not in current_references:
                    current_references.append(reference)
            profile_satisfied = bool(
                profile_satisfied or validation.profile_contract_satisfied
            )
            geography_satisfied = bool(
                geography_satisfied or validation.geography_contract_satisfied
            )
        current_missing = _missing_requested_fields(
            requested=requested,
            fields=current_fields,
        )
        progressed = current_missing != prior_missing
        resolved = not current_missing
        stage_records.append(
            DetailSemanticsBoosterStageEvidence(
                stage=planned.stage,
                attempted=observation.request_attempted,
                status="resolved" if resolved else "validated_unresolved",
                reason_code=planned.reason_code,
                provider_requests=request_count,
                produced_field_names=field_names,
                evidence_reference_count=len(observation.evidence_references),
                hypothesis_fingerprint=hypothesis_fingerprint,
                deterministic_validation_outcome=validation.classification,
                progressed=progressed,
                estimated_cost_usd=estimated_cost,
            )
        )
        if resolved:
            _fail_closed_tail(
                stages=stage_records,
                remaining=model_stages[index + 1 :]
                + (decision.booster_plan.stages[6],),
                reason="prior_stage_resolved",
            )
            break
    else:
        deep = decision.booster_plan.stages[6]
        stage_records.append(
            DetailSemanticsBoosterStageEvidence(
                stage=BoosterStage.DEEP_EVIDENCE,
                attempted=True,
                status="residual_unresolved",
                reason_code=deep.reason_code,
                provider_requests=0,
            )
        )

    return DetailSemanticsBoosterExecution(
        gap_fingerprint=decision.evidence_fingerprint,
        unchanged_evidence_skip=False,
        deterministic_resolved=decision.deterministic_resolved,
        requested_semantic_fields=requested,
        stages=tuple(stage_records),
        semantic_fields=current_fields,
        evidence_references=tuple(current_references),
        profile_contract_satisfied=profile_satisfied,
        geography_contract_satisfied=geography_satisfied,
        provider_requests=provider_requests,
        llm_requests=llm_requests,
    )


__all__ = [
    "DetailSemanticsBoosterExecution",
    "DetailSemanticsBoosterStageEvidence",
    "DetailSemanticsHypothesisObservation",
    "DetailSemanticsValidationObservation",
    "SemanticProgressLedger",
    "execute_detail_semantics_booster",
    "semantic_hypothesis_fingerprint",
]
