from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

FALSE_NEGATIVE_PRIORITY = "False negatives are more expensive than bounded false positives."
HISTORICAL_BURDEN_GUARDRAIL = "Never promote noisy exploration into stable search profiles without measured outcome."


@dataclass(frozen=True)
class AutonomyInput:
    company_key: str
    source_family_candidate: str | None
    suggested_term: str
    confidence_score: Decimal
    confidence_level: str
    sample_size: int
    success_count: int
    failure_count: int
    noise_count: int
    false_negative_risk_level: str | None
    false_negative_sighting_count: int


@dataclass(frozen=True)
class AutonomyDecision:
    recommendation_type: str
    recommendation_status: str
    autonomy_level: str
    guardrail_decision: str
    reason: str
    trial_duration_days: int
    max_result_volume: int
    max_noise_rate: Decimal
    auto_apply_allowed: bool

    @property
    def guardrail_summary(self) -> dict[str, object]:
        return {
            "false_negative_priority": FALSE_NEGATIVE_PRIORITY,
            "historical_burden_guardrail": HISTORICAL_BURDEN_GUARDRAIL,
            "trial_duration_days": self.trial_duration_days,
            "max_result_volume": self.max_result_volume,
            "max_noise_rate": str(self.max_noise_rate),
            "auto_apply_allowed": self.auto_apply_allowed,
        }


def _noise_rate(item: AutonomyInput) -> Decimal:
    if item.sample_size <= 0:
        return Decimal("0")
    return Decimal(item.noise_count) / Decimal(item.sample_size)


def evaluate_autonomy(item: AutonomyInput) -> AutonomyDecision:
    risk = (item.false_negative_risk_level or "low").lower()
    score = item.confidence_score
    noise_rate = _noise_rate(item)

    if item.sample_size <= 0:
        return AutonomyDecision(
            recommendation_type="KEEP_MONITORING",
            recommendation_status="pending_review",
            autonomy_level="manual_approval_required",
            guardrail_decision="insufficient_validation",
            reason="No validation outcome exists yet; keep observing before recommending search strategy changes.",
            trial_duration_days=0,
            max_result_volume=0,
            max_noise_rate=Decimal("0.00"),
            auto_apply_allowed=False,
        )

    if noise_rate >= Decimal("0.50") and item.noise_count >= item.success_count:
        return AutonomyDecision(
            recommendation_type="REJECT_TERM",
            recommendation_status="pending_review",
            autonomy_level="manual_approval_required",
            guardrail_decision="blocked_too_noisy",
            reason="Validated outcomes indicate too much noise; do not expand search strategy from this term.",
            trial_duration_days=0,
            max_result_volume=0,
            max_noise_rate=Decimal("0.00"),
            auto_apply_allowed=False,
        )

    if risk in {"high", "critical"} and item.success_count > 0:
        if item.sample_size >= 5 and score >= Decimal("75") and noise_rate <= Decimal("0.20"):
            return AutonomyDecision(
                recommendation_type="ADD_TRIAL_TERM",
                recommendation_status="auto_eligible",
                autonomy_level="guardrailed_trial_eligible",
                guardrail_decision="auto_trial_eligible",
                reason="High false-negative risk plus enough successful validation evidence makes this term eligible for a bounded trial.",
                trial_duration_days=14,
                max_result_volume=25,
                max_noise_rate=Decimal("0.30"),
                auto_apply_allowed=False,
            )

        return AutonomyDecision(
            recommendation_type="ADD_TRIAL_TERM",
            recommendation_status="pending_review",
            autonomy_level="manual_approval_required",
            guardrail_decision="bounded_trial_recommended",
            reason="High false-negative risk and at least one successful validation justify a bounded trial recommendation, but evidence is not yet strong enough for auto-eligibility.",
            trial_duration_days=14,
            max_result_volume=25,
            max_noise_rate=Decimal("0.30"),
            auto_apply_allowed=False,
        )

    if score >= Decimal("70") and item.sample_size >= 3:
        return AutonomyDecision(
            recommendation_type="KEEP_MONITORING",
            recommendation_status="pending_review",
            autonomy_level="manual_approval_required",
            guardrail_decision="monitor_validated_signal",
            reason="The term has validation evidence, but the current false-negative risk is not high enough for a trial recommendation.",
            trial_duration_days=0,
            max_result_volume=0,
            max_noise_rate=Decimal("0.00"),
            auto_apply_allowed=False,
        )

    return AutonomyDecision(
        recommendation_type="KEEP_MONITORING",
        recommendation_status="pending_review",
        autonomy_level="manual_approval_required",
        guardrail_decision="insufficient_confidence",
        reason="Validation exists but confidence or sample size is not strong enough for adaptation.",
        trial_duration_days=0,
        max_result_volume=0,
        max_noise_rate=Decimal("0.00"),
        auto_apply_allowed=False,
    )
