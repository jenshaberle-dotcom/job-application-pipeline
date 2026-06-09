from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from src.search_intelligence.market_sensor_controlled_activation import (
    BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
    BA_SOURCE_NAME,
    EXPECTED_BA_REMOTE_TERMS,
    MarketSensorProfileState,
    MarketSensorTermState,
)

CONFIRMATION_TOKEN = "ACTIVATE_BA_REMOTE_NATIONWIDE_REVIEW_PROFILE"


@dataclass(frozen=True)
class Sensor001GActivationTarget:
    profile_id: int
    profile_name: str
    source_name: str
    current_is_active: bool
    search_location: str | None
    search_radius_km: int | None
    page_size: int
    active_terms: tuple[str, ...]
    missing_expected_terms: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Sensor001GActivationGateReport:
    overall_status: str
    source_status: str
    recommended_decision: str
    confidence: str
    activation_target: Sensor001GActivationTarget | None
    findings: tuple[str, ...]
    next_action: str
    safety_boundary: Mapping[str, bool]
    confirmation_token_required: str

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": "sensor001g.ba_remote_nationwide_controlled_activation_gate.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "SENSOR-001G BA Remote/Nationwide Controlled Activation Gate",
            "source_name": BA_SOURCE_NAME,
            "review_profile_name": BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            "overall_status": self.overall_status,
            "source_status": self.source_status,
            "recommended_decision": self.recommended_decision,
            "confidence": self.confidence,
            "activation_target": self.activation_target.as_dict() if self.activation_target else None,
            "findings": list(self.findings),
            "next_action": self.next_action,
            "safety_boundary": dict(self.safety_boundary),
            "confirmation_token_required": self.confirmation_token_required,
        }
        return payload


def build_sensor001g_activation_gate(
    *,
    sensor001f_report: Mapping[str, Any],
    profiles: Iterable[MarketSensorProfileState],
    terms: Iterable[MarketSensorTermState],
    apply_requested: bool = False,
    confirmation_token: str | None = None,
    apply_executed: bool = False,
) -> Sensor001GActivationGateReport:
    source_status = str(sensor001f_report.get("overall_status") or "unknown")
    recommended_decision = str(sensor001f_report.get("recommended_decision") or "unknown")
    confidence = str(sensor001f_report.get("confidence") or "unknown")
    safety_boundary = _safety_boundary(apply_requested=apply_requested, apply_executed=apply_executed)

    if source_status != "decision_ready":
        return Sensor001GActivationGateReport(
            overall_status="activation_blocked_by_sensor001f_status",
            source_status=source_status,
            recommended_decision=recommended_decision,
            confidence=confidence,
            activation_target=None,
            findings=("SENSOR-001F is not decision_ready; do not activate the BA remote/nationwide profile.",),
            next_action="Repair or rerun SENSOR-001E/F before controlled activation.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    if recommended_decision != "activate_controlled_profile":
        return Sensor001GActivationGateReport(
            overall_status="activation_blocked_by_sensor001f_recommendation",
            source_status=source_status,
            recommended_decision=recommended_decision,
            confidence=confidence,
            activation_target=None,
            findings=("SENSOR-001F does not recommend controlled activation.",),
            next_action="Follow the SENSOR-001F recommendation instead of activating this profile.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    target_result = _build_activation_target(tuple(profiles), tuple(terms))
    if isinstance(target_result, Sensor001GActivationGateReport):
        return target_result
    target = target_result

    if apply_executed:
        return Sensor001GActivationGateReport(
            overall_status="activation_applied",
            source_status=source_status,
            recommended_decision=recommended_decision,
            confidence=confidence,
            activation_target=target,
            findings=(
                "BA remote/nationwide review profile activation was applied.",
                "No raw_jobs, ingestion_runs, candidate, gate, connector, Bronze, Silver, or Gold mutation was performed by SENSOR-001G.",
            ),
            next_action="Run validation and then monitor the next controlled BA ingestion result before broadening activation.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    if target.current_is_active:
        return Sensor001GActivationGateReport(
            overall_status="already_active_controlled_profile",
            source_status=source_status,
            recommended_decision=recommended_decision,
            confidence=confidence,
            activation_target=target,
            findings=("BA remote/nationwide review profile is already active; no additional activation write is needed.",),
            next_action="Proceed with bounded monitoring and avoid duplicate activation attempts.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    if not apply_requested:
        return Sensor001GActivationGateReport(
            overall_status="activation_apply_ready",
            source_status=source_status,
            recommended_decision=recommended_decision,
            confidence=confidence,
            activation_target=target,
            findings=(
                "SENSOR-001F recommends controlled activation and the inactive review profile is ready.",
                "Dry run only: no database write was performed.",
            ),
            next_action=(
                "Review activation_target, then rerun with --apply and the confirmation token only after explicit approval."
            ),
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    if confirmation_token != CONFIRMATION_TOKEN:
        return Sensor001GActivationGateReport(
            overall_status="activation_apply_blocked_by_missing_confirmation",
            source_status=source_status,
            recommended_decision=recommended_decision,
            confidence=confidence,
            activation_target=target,
            findings=("--apply was requested but the confirmation token was missing or incorrect.",),
            next_action=f"Rerun with --apply --confirm {CONFIRMATION_TOKEN} only after explicit approval.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    return Sensor001GActivationGateReport(
        overall_status="activation_apply_authorized",
        source_status=source_status,
        recommended_decision=recommended_decision,
        confidence=confidence,
        activation_target=target,
        findings=("Apply request is authorized; the runner may now activate the review profile in one bounded DB update.",),
        next_action="Execute the bounded profile activation update, then rerun the gate report.",
        safety_boundary=safety_boundary,
        confirmation_token_required=CONFIRMATION_TOKEN,
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SENSOR-001G BA Remote/Nationwide Controlled Activation Gate",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- recommended_decision: `{report.get('recommended_decision')}`",
        f"- confidence: `{report.get('confidence')}`",
        "",
        "## Activation target",
        "",
    ]
    target = report.get("activation_target")
    if not target:
        lines.append("- none")
    else:
        for key, value in target.items():
            lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Findings", ""])
    for finding in report.get("findings", []):
        lines.append(f"- {finding}")

    lines.extend(["", "## Safety boundary", ""])
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(
        [
            "",
            "## Confirmation token",
            "",
            f"`{report.get('confirmation_token_required')}`",
            "",
            "## Next action",
            "",
            str(report.get("next_action", "")),
            "",
        ]
    )
    return "\n".join(lines)


def _build_activation_target(
    profiles: tuple[MarketSensorProfileState, ...],
    terms: tuple[MarketSensorTermState, ...],
) -> Sensor001GActivationTarget | Sensor001GActivationGateReport:
    review_profiles = tuple(
        profile
        for profile in profiles
        if profile.source_name == BA_SOURCE_NAME
        and profile.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME
    )
    safety_boundary = _safety_boundary(apply_requested=False, apply_executed=False)

    if not review_profiles:
        return Sensor001GActivationGateReport(
            overall_status="activation_blocked_by_missing_review_profile",
            source_status="decision_ready",
            recommended_decision="activate_controlled_profile",
            confidence="unknown",
            activation_target=None,
            findings=("BA remote/nationwide review profile is missing.",),
            next_action="Repair SENSOR-001C/074 review profile state before activation.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    if len(review_profiles) > 1:
        return Sensor001GActivationGateReport(
            overall_status="activation_blocked_by_duplicate_review_profiles",
            source_status="decision_ready",
            recommended_decision="activate_controlled_profile",
            confidence="unknown",
            activation_target=None,
            findings=("More than one BA remote/nationwide review profile exists; this is a stop signal.",),
            next_action="Resolve duplicate profile state before activation.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    profile = review_profiles[0]
    active_terms = tuple(
        term.search_term
        for term in terms
        if term.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME and term.is_active
    )
    missing_terms = tuple(term for term in EXPECTED_BA_REMOTE_TERMS if term not in active_terms)

    if profile.search_location is not None or profile.search_radius_km is not None:
        return Sensor001GActivationGateReport(
            overall_status="activation_blocked_by_profile_scope_mismatch",
            source_status="decision_ready",
            recommended_decision="activate_controlled_profile",
            confidence="unknown",
            activation_target=None,
            findings=("Review profile must keep NULL location/radius for remote/nationwide semantics.",),
            next_action="Repair profile scope before activation.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    target = Sensor001GActivationTarget(
        profile_id=profile.id,
        profile_name=profile.profile_name,
        source_name=profile.source_name,
        current_is_active=profile.is_active,
        search_location=profile.search_location,
        search_radius_km=profile.search_radius_km,
        page_size=profile.page_size,
        active_terms=active_terms,
        missing_expected_terms=missing_terms,
    )

    if missing_terms:
        return Sensor001GActivationGateReport(
            overall_status="activation_blocked_by_missing_terms",
            source_status="decision_ready",
            recommended_decision="activate_controlled_profile",
            confidence="unknown",
            activation_target=target,
            findings=("Review profile is missing expected active terms: " + ", ".join(missing_terms),),
            next_action="Repair review profile terms before activation.",
            safety_boundary=safety_boundary,
            confirmation_token_required=CONFIRMATION_TOKEN,
        )

    return target


def _safety_boundary(*, apply_requested: bool, apply_executed: bool) -> dict[str, bool]:
    return {
        "external_requests": False,
        "database_reads": True,
        "database_writes": bool(apply_executed),
        "profile_activation_write": bool(apply_executed),
        "raw_jobs_write": False,
        "ingestion_run_write": False,
        "scheduler_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
        "bronze_silver_gold_mutation": False,
        "productive_activation": bool(apply_executed),
        "apply_requested": bool(apply_requested),
    }
