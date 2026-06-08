"""Classify employer-origin gate stops for audit and safe reprocessing.

This module deliberately does not mutate candidate or gate state.  It turns the
currently coarse gate status/decision vocabulary into a more precise audit
classification so callers can distinguish terminal stops from recoverable or
review-required evidence gaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.search_intelligence.stop_taxonomy import (
    repair_strategy_for_category,
    taxonomy_entry_for_category,
)


WEAK_RISK_MARKERS = {"captcha", "recaptcha"}
STRONG_ACCESS_RISK_MARKERS = {
    "access denied",
    "bot detection",
    "cloudflare challenge",
    "forbidden",
    "hcaptcha",
}


@dataclass(frozen=True)
class GateStopClassification:
    category: str
    severity: str
    terminal: bool
    default_reprocess: str
    explanation: str
    lifecycle_class: str
    false_negative_risk: str
    repair_strategy_id: str
    recommended_next_safe_action: str
    safety_zone: str
    human_review_required: bool
    dry_run_required: bool
    explicit_apply_required: bool

    def as_evidence(self) -> dict[str, Any]:
        return {
            "stop_category": self.category,
            "stop_lifecycle_class": self.lifecycle_class,
            "stop_severity": self.severity,
            "terminal": self.terminal,
            "default_reprocess": self.default_reprocess,
            "false_negative_risk": self.false_negative_risk,
            "repair_strategy_id": self.repair_strategy_id,
            "recommended_next_safe_action": self.recommended_next_safe_action,
            "safety_zone": self.safety_zone,
            "human_review_required": self.human_review_required,
            "dry_run_required": self.dry_run_required,
            "explicit_apply_required": self.explicit_apply_required,
            "classification_explanation": self.explanation,
        }


def _classification(category: str, explanation: str | None = None) -> GateStopClassification:
    entry = taxonomy_entry_for_category(category)
    strategy = repair_strategy_for_category(category)
    return GateStopClassification(
        category=entry.category,
        severity=entry.severity,
        terminal=entry.terminal,
        default_reprocess=entry.default_reprocess,
        explanation=explanation or entry.description,
        lifecycle_class=entry.lifecycle_class,
        false_negative_risk=entry.false_negative_risk,
        repair_strategy_id=strategy.strategy_id,
        recommended_next_safe_action=strategy.default_next_safe_action,
        safety_zone=strategy.safety_zone,
        human_review_required=strategy.human_review_required,
        dry_run_required=strategy.dry_run_required,
        explicit_apply_required=strategy.explicit_apply_required,
    )


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalized_markers(evidence: Mapping[str, Any]) -> set[str]:
    raw = evidence.get("risk_markers", [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return set()
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def _status_code(evidence: Mapping[str, Any]) -> int | None:
    raw = evidence.get("status_code")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _contains_any(value: str, needles: set[str] | tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(needle in lowered for needle in needles)


def classify_gate_stop(
    *,
    gate_name: str,
    gate_status: str | None,
    decision: str | None,
    stop_reason: str | None,
    evidence: Any,
) -> GateStopClassification:
    """Classify a stop-like gate result without changing the original decision.

    The classification is intentionally conservative: only confirmed access or
    policy risks are terminal by default.  URL and evidence discovery failures
    are treated as recoverable/reviewable so a source is not lost merely because
    a finder/extraction heuristic was incomplete.
    """
    evidence_map = _as_mapping(evidence)
    reason = (stop_reason or "").strip().lower()
    gate = (gate_name or "").strip()
    status = (gate_status or "").strip()
    gate_decision = (decision or "").strip()

    if gate == "technical_reachability_gate":
        code = _status_code(evidence_map)
        if code == 404 or _contains_any(reason, {"http 404", "not found", "no reachable", "request failed"}):
            return _classification(
                "recoverable_url_problem",
                (
                    "The candidate/source URL appears stale, wrong or insufficiently recovered; "
                    "this should not be treated as a confirmed terminal source stop."
                ),
            )
        if status == "failed" or gate_decision == "abort_documented":
            return _classification(
                "technical_reachability_review",
                "Technical reachability failed, but no confirmed terminal access/policy risk was recorded.",
            )

    if gate == "risk_gate":
        markers = _normalized_markers(evidence_map)
        if markers & STRONG_ACCESS_RISK_MARKERS or _contains_any(reason, STRONG_ACCESS_RISK_MARKERS):
            return _classification(
                "terminal_access_risk",
                "The gate evidence contains confirmed access-denied, challenge or bot-defense markers.",
            )
        if markers and markers <= WEAK_RISK_MARKERS and _status_code(evidence_map) == 200:
            return _classification(
                "risk_marker_review",
                (
                    "Only weak captcha/recaptcha markers were found on an otherwise reachable page; "
                    "this is review evidence, not a confirmed terminal access stop."
                ),
            )
        if markers:
            return _classification(
                "risk_marker_review",
                "Risk markers were found, but the evidence is not strong enough to classify as terminal.",
            )

    if gate == "detail_evidence_gate":
        if _contains_any(reason, {"no concrete detail", "detail pages", "detail evidence"}):
            return _classification(
                "detail_discovery_gap",
                "The source/relevance path may be valid, but concrete job-detail evidence was not discovered.",
            )

    if gate == "relevance_gate":
        if status == "manual_review_required" or gate_decision == "manual_review_required":
            return _classification(
                "weak_relevance_evidence",
                "The candidate needs stronger profile/location/remote evidence before progressing.",
            )

    if gate_decision == "abort_documented" or status == "failed":
        return _classification(
            "terminal_unclassified",
            "The gate recorded an abort/failure without a more precise recoverable classification.",
        )

    if status == "manual_review_required" or gate_decision == "manual_review_required":
        return _classification(
            "manual_review_required",
            "The gate needs manual or bounded automated review but is not confirmed terminal.",
        )

    return _classification(
        "not_stop_like",
        "The gate result is not classified as a stop-like decision.",
    )
