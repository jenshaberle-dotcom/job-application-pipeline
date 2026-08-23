"""Pure admission policy for optional ML and LLM booster capabilities.

A booster is evaluated at one explicit decision surface. Admission only means that
an offline/shadow evaluation is worth running; it never authorizes provider calls,
training execution, product writes, ranking authority, or application actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class BoosterFamily(str, Enum):
    ML = "ml"
    LLM = "llm"


ADMISSION_REASON_CODES: tuple[str, ...] = (
    "baseline_not_measured",
    "no_measured_residual",
    "grounded_evaluation_missing",
    "observability_missing",
    "authority_boundary_missing",
    "problem_fit_below_threshold",
    "evidence_quality_below_threshold",
    "operational_risk_above_threshold",
    "ml_repeatability_below_threshold",
    "ml_volume_below_threshold",
    "expected_net_value_below_threshold",
)


@dataclass(frozen=True)
class BoosterAdmissionPolicy:
    """Operator/product-owned thresholds for deciding whether shadow evidence is worth collecting."""

    minimum_expected_net_value: float
    minimum_problem_fit: float
    minimum_evidence_quality: float
    maximum_operational_risk: float
    minimum_ml_repeatability: float
    minimum_ml_decision_volume: int

    def __post_init__(self) -> None:
        _require_unit_interval("minimum_problem_fit", self.minimum_problem_fit)
        _require_unit_interval("minimum_evidence_quality", self.minimum_evidence_quality)
        _require_unit_interval("maximum_operational_risk", self.maximum_operational_risk)
        _require_unit_interval("minimum_ml_repeatability", self.minimum_ml_repeatability)
        if self.minimum_expected_net_value < 0:
            raise ValueError("minimum_expected_net_value must be non-negative")
        if self.minimum_ml_decision_volume < 0:
            raise ValueError("minimum_ml_decision_volume must be non-negative")


@dataclass(frozen=True)
class BoosterOpportunityEvidence:
    """Measured planning evidence for one booster family on one bounded decision surface."""

    surface_id: str
    family: BoosterFamily
    baseline_measured: bool
    decision_volume: int
    deterministic_residual_rate: float
    expected_rescue_rate: float
    expected_value_per_rescue: float
    estimated_incremental_cost_per_escalated_case: float
    estimated_fixed_validation_cost: float
    problem_fit: float
    evidence_quality: float
    repeatability: float
    operational_risk: float
    grounded_evaluation_ready: bool
    observability_ready: bool
    authority_boundary_defined: bool

    def __post_init__(self) -> None:
        if not self.surface_id.strip():
            raise ValueError("surface_id must be non-empty")
        if self.decision_volume < 0:
            raise ValueError("decision_volume must be non-negative")
        for field_name, value in (
            ("deterministic_residual_rate", self.deterministic_residual_rate),
            ("expected_rescue_rate", self.expected_rescue_rate),
            ("problem_fit", self.problem_fit),
            ("evidence_quality", self.evidence_quality),
            ("repeatability", self.repeatability),
            ("operational_risk", self.operational_risk),
        ):
            _require_unit_interval(field_name, value)
        if self.expected_value_per_rescue < 0:
            raise ValueError("expected_value_per_rescue must be non-negative")
        if self.estimated_incremental_cost_per_escalated_case < 0:
            raise ValueError("estimated_incremental_cost_per_escalated_case must be non-negative")
        if self.estimated_fixed_validation_cost < 0:
            raise ValueError("estimated_fixed_validation_cost must be non-negative")


@dataclass(frozen=True)
class BoosterAdmissionDecision:
    surface_id: str
    family: BoosterFamily
    eligible_for_shadow: bool
    reasons: tuple[str, ...]
    expected_escalated_cases: float
    expected_rescues: float
    expected_gross_value: float
    expected_variable_cost: float
    expected_fixed_cost: float
    expected_net_value: float
    execution_authorized: bool = False
    product_authority: bool = False

    def __post_init__(self) -> None:
        if self.execution_authorized:
            raise ValueError("booster admission may not authorize execution")
        if self.product_authority:
            raise ValueError("booster admission may not claim product authority")


def evaluate_booster_admission(
    evidence: BoosterOpportunityEvidence,
    policy: BoosterAdmissionPolicy,
) -> BoosterAdmissionDecision:
    """Evaluate one task-local booster opportunity without executing the booster."""

    expected_escalated_cases = evidence.decision_volume * evidence.deterministic_residual_rate
    expected_rescues = expected_escalated_cases * evidence.expected_rescue_rate
    expected_gross_value = expected_rescues * evidence.expected_value_per_rescue
    expected_variable_cost = (
        expected_escalated_cases * evidence.estimated_incremental_cost_per_escalated_case
    )
    expected_net_value = (
        expected_gross_value
        - expected_variable_cost
        - evidence.estimated_fixed_validation_cost
    )

    reasons: list[str] = []
    if not evidence.baseline_measured:
        reasons.append("baseline_not_measured")
    if evidence.deterministic_residual_rate <= 0:
        reasons.append("no_measured_residual")
    if not evidence.grounded_evaluation_ready:
        reasons.append("grounded_evaluation_missing")
    if not evidence.observability_ready:
        reasons.append("observability_missing")
    if not evidence.authority_boundary_defined:
        reasons.append("authority_boundary_missing")
    if evidence.problem_fit < policy.minimum_problem_fit:
        reasons.append("problem_fit_below_threshold")
    if evidence.evidence_quality < policy.minimum_evidence_quality:
        reasons.append("evidence_quality_below_threshold")
    if evidence.operational_risk > policy.maximum_operational_risk:
        reasons.append("operational_risk_above_threshold")
    if evidence.family is BoosterFamily.ML:
        if evidence.repeatability < policy.minimum_ml_repeatability:
            reasons.append("ml_repeatability_below_threshold")
        if evidence.decision_volume < policy.minimum_ml_decision_volume:
            reasons.append("ml_volume_below_threshold")
    if expected_net_value < policy.minimum_expected_net_value:
        reasons.append("expected_net_value_below_threshold")

    unknown_reasons = set(reasons) - set(ADMISSION_REASON_CODES)
    if unknown_reasons:
        raise AssertionError(f"unknown booster admission reason(s): {sorted(unknown_reasons)}")

    return BoosterAdmissionDecision(
        surface_id=evidence.surface_id,
        family=evidence.family,
        eligible_for_shadow=not reasons,
        reasons=tuple(reasons),
        expected_escalated_cases=expected_escalated_cases,
        expected_rescues=expected_rescues,
        expected_gross_value=expected_gross_value,
        expected_variable_cost=expected_variable_cost,
        expected_fixed_cost=evidence.estimated_fixed_validation_cost,
        expected_net_value=expected_net_value,
    )


def rank_shadow_candidates(
    opportunities: Iterable[BoosterOpportunityEvidence],
    policy: BoosterAdmissionPolicy,
) -> tuple[BoosterAdmissionDecision, ...]:
    """Return only admitted shadow candidates, highest expected net value first."""

    decisions = (evaluate_booster_admission(item, policy) for item in opportunities)
    admitted = [decision for decision in decisions if decision.eligible_for_shadow]
    return tuple(
        sorted(
            admitted,
            key=lambda decision: (
                -decision.expected_net_value,
                decision.surface_id,
                decision.family.value,
            ),
        )
    )


def _require_unit_interval(field_name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
