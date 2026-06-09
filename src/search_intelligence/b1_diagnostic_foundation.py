"""B1 read-only diagnostic foundation for Market, StepStone, and SENSOR-001F.

B1 intentionally prepares measurement and decision surfaces only. It must not
run external sources, write database state, activate schedulers, or mutate
candidate/gate/connector/Bronze/Silver/Gold state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

from src.search_intelligence.market_sensor_coverage import (
    MarketSensorProfile,
    assess_all_market_sensors,
)
from src.search_intelligence.stepstone_company_discovery_cycle import (
    CompanyCooldown,
    CompanyObservation,
    assess_discovery_observations,
    build_company_discovery_plan,
)

B1_WORK_ITEM = "B1 Market + StepStone Diagnostic Foundation"
MARKET_001 = "MARKET-001 Market Sensor Diagnostic Metrics"
STEPSTONE_001 = "STEPSTONE-001 StepStone Discovery Cycle Diagnostics"
SENSOR_001F = "SENSOR-001F BA Remote/Nationwide Result Decision Scaffold"

SAFETY_BOUNDARY: dict[str, bool] = {
    "read_only_diagnostic": True,
    "external_requests": False,
    "database_writes": False,
    "ingestion_run": False,
    "scheduler_mutation": False,
    "candidate_or_gate_mutation": False,
    "connector_activation": False,
    "bronze_silver_gold_mutation": False,
}

SENSOR_001F_REQUIRED_METRICS = (
    "total_loaded_by_term",
    "inserted_count_by_term",
    "duplicate_count_by_term",
    "distinct_company_count",
    "new_company_count",
    "known_company_overlap_count",
    "remote_signal_count",
    "local_or_hannover_overlap_count",
    "profile_relevant_title_count",
    "irrelevant_title_count",
    "error_count",
)

SENSOR_001F_DECISION_OPTIONS = (
    "activate_controlled_profile",
    "repeat_bounded_sample_with_repaired_terms",
    "keep_review_profile_inactive_and_monitor",
    "reject_or_archive_profile_as_noise",
)


@dataclass(frozen=True)
class Sensor001FSampleResult:
    """Bounded SENSOR-001E result summary for later SENSOR-001F decisions.

    This object is a scaffold input only. B1 does not create these metrics from
    live API calls; the later bounded sample execution may feed them into this
    decision surface.
    """

    total_loaded: int
    inserted_count: int
    duplicate_count: int
    distinct_company_count: int
    new_company_count: int
    remote_signal_count: int
    profile_relevant_title_count: int
    irrelevant_title_count: int
    error_count: int = 0


@dataclass(frozen=True)
class Sensor001FDecisionScaffold:
    status: str
    required_metrics: tuple[str, ...]
    available_metrics: tuple[str, ...]
    missing_metrics: tuple[str, ...]
    decision_options: tuple[str, ...]
    recommended_decision: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "work_item": SENSOR_001F,
            "status": self.status,
            "required_metrics": list(self.required_metrics),
            "available_metrics": list(self.available_metrics),
            "missing_metrics": list(self.missing_metrics),
            "decision_options": list(self.decision_options),
            "recommended_decision": self.recommended_decision,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class B1DiagnosticReport:
    generated_at_utc: str
    work_item: str
    safety_boundary: Mapping[str, bool]
    market_001: Mapping[str, Any]
    stepstone_001: Mapping[str, Any]
    sensor_001f: Sensor001FDecisionScaffold
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "b1.market_stepstone_sensor_diagnostic_foundation.v1",
            "generated_at_utc": self.generated_at_utc,
            "work_item": self.work_item,
            "safety_boundary": dict(self.safety_boundary),
            "market_001": dict(self.market_001),
            "stepstone_001": dict(self.stepstone_001),
            "sensor_001f": self.sensor_001f.as_dict(),
            "next_action": self.next_action,
        }


def build_sensor001f_decision_scaffold(
    sample_result: Sensor001FSampleResult | None = None,
) -> Sensor001FDecisionScaffold:
    """Build a read-only decision surface for the later SENSOR-001F review."""

    if sample_result is None:
        return Sensor001FDecisionScaffold(
            status="awaiting_sensor001e_sample_result",
            required_metrics=SENSOR_001F_REQUIRED_METRICS,
            available_metrics=(),
            missing_metrics=SENSOR_001F_REQUIRED_METRICS,
            decision_options=SENSOR_001F_DECISION_OPTIONS,
            recommended_decision="do_not_decide_before_bounded_sample_result",
            reason=(
                "SENSOR-001F needs bounded SENSOR-001E result metrics before any "
                "activation, rejection, or repeat-sample decision."
            ),
        )

    available = _available_metrics_for_sample_result(sample_result)
    missing = tuple(metric for metric in SENSOR_001F_REQUIRED_METRICS if metric not in available)
    recommendation, reason = _recommend_sensor001f_decision(sample_result, missing)
    status = "decision_ready" if not missing else "decision_blocked_missing_metrics"
    return Sensor001FDecisionScaffold(
        status=status,
        required_metrics=SENSOR_001F_REQUIRED_METRICS,
        available_metrics=available,
        missing_metrics=missing,
        decision_options=SENSOR_001F_DECISION_OPTIONS,
        recommended_decision=recommendation,
        reason=reason,
    )


def build_b1_diagnostic_foundation_report(
    *,
    market_profiles: Sequence[MarketSensorProfile],
    stepstone_cooldowns: Iterable[CompanyCooldown],
    stepstone_observations: Iterable[CompanyObservation],
    source_name: str = "stepstone",
    search_profile_name: str = "data_engineering_hannover",
    search_term: str = "Data Engineer",
    sample_result: Sensor001FSampleResult | None = None,
    now: datetime | None = None,
) -> B1DiagnosticReport:
    """Create the complete B1 read-only diagnostic report."""

    reference_time = now or datetime.now(UTC)
    market_assessments = assess_all_market_sensors(market_profiles)
    cooldown_tuple = tuple(stepstone_cooldowns)
    observation_tuple = tuple(stepstone_observations)
    discovery_plan = build_company_discovery_plan(
        source_name=source_name,
        search_profile_name=search_profile_name,
        search_term=search_term,
        cooldowns=cooldown_tuple,
        now=reference_time,
    )
    discovery_assessment = assess_discovery_observations(
        search_term=search_term,
        observations=observation_tuple,
        cooldown_company_keys=(cooldown.company_key for cooldown in cooldown_tuple),
    )
    sensor_scaffold = build_sensor001f_decision_scaffold(sample_result)

    return B1DiagnosticReport(
        generated_at_utc=reference_time.isoformat(),
        work_item=B1_WORK_ITEM,
        safety_boundary=SAFETY_BOUNDARY,
        market_001={
            "work_item": MARKET_001,
            "assessment_count": len(market_assessments),
            "assessments": [assessment.as_dict() for assessment in market_assessments],
            "purpose": (
                "Measure market-sensor coverage, overlap, and gaps before changing "
                "sensor activation or discovery behavior."
            ),
        },
        stepstone_001={
            "work_item": STEPSTONE_001,
            "discovery_plan": {
                "source_name": discovery_plan.source_name,
                "search_profile_name": discovery_plan.search_profile_name,
                "search_term": discovery_plan.search_term,
                "base_query": discovery_plan.base_query,
                "planned_query": discovery_plan.planned_query,
                "not_company_names": list(discovery_plan.not_company_names),
                "not_company_keys": list(discovery_plan.not_company_keys),
                "action": discovery_plan.action,
                "reason": discovery_plan.reason,
                "boundary": dict(discovery_plan.boundary),
            },
            "discovery_assessment": {
                "search_term": discovery_assessment.search_term,
                "observed_count": discovery_assessment.observed_count,
                "distinct_company_count": discovery_assessment.distinct_company_count,
                "known_cooldown_hit_count": discovery_assessment.known_cooldown_hit_count,
                "new_company_count": discovery_assessment.new_company_count,
                "relevance_hits": discovery_assessment.relevance_hits,
                "drift_hits": discovery_assessment.drift_hits,
                "quality_score": discovery_assessment.quality_score,
                "recommended_interval_days": discovery_assessment.recommended_interval_days,
                "cooldown_proposals": [
                    {
                        "company_key": proposal.company_key,
                        "company_name": proposal.company_name,
                        "evidence_count": proposal.evidence_count,
                        "cooldown_days": proposal.cooldown_days,
                        "reason": proposal.reason,
                        "sample_titles": list(proposal.sample_titles),
                    }
                    for proposal in discovery_assessment.cooldown_proposals
                ],
                "reason": discovery_assessment.reason,
            },
            "purpose": (
                "Expose whether StepStone cycles reveal new companies or repeat known-company blocks "
                "before changing discovery or gate behavior."
            ),
        },
        sensor_001f=sensor_scaffold,
        next_action=(
            "Run B1 against current read-only observations, then request explicit approval before SENSOR-001E."
            if sensor_scaffold.status == "awaiting_sensor001e_sample_result"
            else "Review SENSOR-001F recommendation under approval gates."
        ),
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# B1 Market + StepStone Diagnostic Foundation",
        "",
        f"- schema_version: `{report.get('schema_version')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- work_item: `{report.get('work_item')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")

    market = report.get("market_001", {})
    lines.extend(["", "## MARKET-001", "", str(market.get("purpose", "")), ""])
    for assessment in market.get("assessments", []):
        lines.append(f"- {assessment.get('source_name')}: `{assessment.get('status')}` -> {assessment.get('next_action')}")

    stepstone = report.get("stepstone_001", {})
    plan = stepstone.get("discovery_plan", {})
    assessment = stepstone.get("discovery_assessment", {})
    lines.extend(
        [
            "",
            "## STEPSTONE-001",
            "",
            str(stepstone.get("purpose", "")),
            "",
            f"- action: `{plan.get('action')}`",
            f"- planned_query: `{plan.get('planned_query')}`",
            f"- new_company_count: `{assessment.get('new_company_count')}`",
            f"- quality_score: `{assessment.get('quality_score')}`",
            f"- recommended_interval_days: `{assessment.get('recommended_interval_days')}`",
        ]
    )

    sensor = report.get("sensor_001f", {})
    lines.extend(
        [
            "",
            "## SENSOR-001F scaffold",
            "",
            f"- status: `{sensor.get('status')}`",
            f"- recommended_decision: `{sensor.get('recommended_decision')}`",
            f"- reason: {sensor.get('reason')}",
            "",
            "## Next action",
            "",
            str(report.get("next_action", "")),
            "",
        ]
    )
    return "\n".join(lines)


def sample_b1_inputs() -> dict[str, Any]:
    now = datetime(2026, 6, 8, 19, 0, tzinfo=UTC)
    return {
        "market_profiles": (
            MarketSensorProfile(
                profile_key="ba_data_engineering_hannover",
                source_name="bundesagentur",
                search_location="Hannover",
                search_terms=("Data Engineer", "Analytics Engineer"),
                is_active=True,
            ),
            MarketSensorProfile(
                profile_key="ba_remote_nationwide_review",
                source_name="bundesagentur",
                search_location="Deutschland remote",
                search_terms=("Data Engineer", "Analytics Engineer"),
                is_active=False,
            ),
        ),
        "stepstone_cooldowns": (
            CompanyCooldown(
                company_key="hdi",
                company_name="HDI",
                source_name="stepstone",
                search_profile_name="data_engineering_hannover",
                search_term="Data Engineer",
                cooldown_until=now + timedelta(days=7),
                reason="known repeated company block",
                evidence_count=4,
            ),
        ),
        "stepstone_observations": (
            CompanyObservation(
                company_key="bahlsen",
                company_name="Bahlsen",
                title="Data Engineer Analytics Platform",
            ),
            CompanyObservation(
                company_key="hdi",
                company_name="HDI",
                title="Data Engineer Cloud Platform",
            ),
        ),
        "now": now,
    }


def _available_metrics_for_sample_result(sample_result: Sensor001FSampleResult) -> tuple[str, ...]:
    available = {
        "total_loaded_by_term",
        "inserted_count_by_term",
        "duplicate_count_by_term",
        "distinct_company_count",
        "new_company_count",
        "remote_signal_count",
        "profile_relevant_title_count",
        "irrelevant_title_count",
        "error_count",
    }
    if sample_result.distinct_company_count:
        available.add("known_company_overlap_count")
    if sample_result.remote_signal_count:
        available.add("local_or_hannover_overlap_count")
    return tuple(metric for metric in SENSOR_001F_REQUIRED_METRICS if metric in available)


def _recommend_sensor001f_decision(
    sample_result: Sensor001FSampleResult,
    missing_metrics: tuple[str, ...],
) -> tuple[str, str]:
    if missing_metrics:
        return (
            "repeat_bounded_sample_with_repaired_terms",
            "The sample result is not decision-grade because required metrics are missing.",
        )
    if sample_result.error_count:
        return (
            "repeat_bounded_sample_with_repaired_terms",
            "The sample has errors; repair execution before drawing source-value conclusions.",
        )
    if sample_result.total_loaded == 0:
        return (
            "keep_review_profile_inactive_and_monitor",
            "No visible yield; do not activate based on an empty sample.",
        )
    relevance_ratio = sample_result.profile_relevant_title_count / max(sample_result.total_loaded, 1)
    novelty_ratio = sample_result.new_company_count / max(sample_result.distinct_company_count, 1)
    remote_ratio = sample_result.remote_signal_count / max(sample_result.total_loaded, 1)
    noise_ratio = sample_result.irrelevant_title_count / max(sample_result.total_loaded, 1)
    if relevance_ratio >= 0.6 and novelty_ratio >= 0.3 and remote_ratio >= 0.4 and noise_ratio <= 0.3:
        return (
            "activate_controlled_profile",
            "Bounded sample shows relevant, novel, remote-signal-bearing yield with limited noise.",
        )
    if noise_ratio > 0.5:
        return (
            "reject_or_archive_profile_as_noise",
            "Bounded sample is dominated by irrelevant titles; activation would likely increase noise.",
        )
    return (
        "repeat_bounded_sample_with_repaired_terms",
        "Sample is inconclusive; keep profile inactive and repair terms or measurement before deciding.",
    )
