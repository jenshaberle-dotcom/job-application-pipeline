"""EO-002B URL Finder validation metrics.

The functions in this module are deliberately pure and report-oriented. They do
not reset candidates, write candidate URLs, register connectors, activate
sources, touch Bronze/Silver data or change schedules. The module turns existing
Origin Source Discovery payloads into a compact campaign metric so the project
can decide whether the current bottleneck is URL discovery, gate evidence or the
candidate-promotion threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

SUCCESS_TIER_A = "A"
SUCCESS_TIER_B = "B"
SUCCESS_TIER_C = "C"
SUCCESS_TIER_D = "D"

SELECTED_DECISIONS = {"origin_url_candidate_selected", "selected", "select_candidate"}
MANUAL_REVIEW_DECISIONS = {"manual_review_required", "manual_review_candidate"}


@dataclass(frozen=True)
class UrlFinderValidationMetric:
    """Compact, JSON-serializable URL Finder validation result for one candidate."""

    candidate_id: int | None
    company_key: str
    company_name: str
    candidate_status: str | None
    candidate_url_before: str | None
    selected_url: str | None
    alternative_url_count: int
    rejected_url_count: int
    confidence_score: float
    decision: str
    risk_level: str | None
    success_tier: str
    gate_stop: str | None
    false_negative_candidate: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _safe_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _list_count(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def classify_success_tier(*, decision: str, confidence_score: float, selected_url: str | None) -> str:
    """Classify one URL Finder outcome into a campaign-friendly tier.

    A: selected URL with high confidence.
    B: selected or manual-review candidate with enough confidence for human review.
    C: no selected URL, but the agent produced some usable manual-review signal.
    D: not found / rejected / no useful URL signal.
    """

    normalized = str(decision or "").strip()
    if selected_url and normalized in SELECTED_DECISIONS and confidence_score >= 0.78:
        return SUCCESS_TIER_A
    if selected_url and confidence_score >= 0.55:
        return SUCCESS_TIER_B
    if normalized in MANUAL_REVIEW_DECISIONS and confidence_score >= 0.55:
        return SUCCESS_TIER_C
    return SUCCESS_TIER_D


def is_false_negative_candidate(payload: Mapping[str, object]) -> bool:
    """Return true when payload metadata marks this as a false-negative validation case."""

    risk = str(payload.get("candidate_risk_level") or payload.get("fn_pressure_level") or "").lower()
    company_key = str(payload.get("company_key") or "").lower()
    reason = str(payload.get("reason") or "").lower()
    return (
        risk in {"critical", "high", "false_negative", "fn_critical"}
        or "false negative" in reason
        or company_key in {"hannover_ruck", "hannover_re"}
    )


def metric_from_discovery_payload(
    payload: Mapping[str, object],
    *,
    gate_stop: str | None = None,
) -> UrlFinderValidationMetric:
    """Build an EO-002B validation metric from Origin Source Discovery JSON."""

    decision = str(payload.get("decision") or "")
    confidence = _safe_float(payload.get("confidence_score"))
    selected_url = str(payload.get("selected_url") or "").strip() or None
    return UrlFinderValidationMetric(
        candidate_id=_safe_int(payload.get("candidate_id")),
        company_key=str(payload.get("company_key") or ""),
        company_name=str(payload.get("company_name") or ""),
        candidate_status=str(payload.get("candidate_status") or "") or None,
        candidate_url_before=str(payload.get("candidate_url_before") or "") or None,
        selected_url=selected_url,
        alternative_url_count=_list_count(payload.get("alternatives")),
        rejected_url_count=_list_count(payload.get("rejected")),
        confidence_score=confidence,
        decision=decision,
        risk_level=str(payload.get("risk_level") or "") or None,
        success_tier=classify_success_tier(
            decision=decision,
            confidence_score=confidence,
            selected_url=selected_url,
        ),
        gate_stop=gate_stop,
        false_negative_candidate=is_false_negative_candidate(payload),
        reason=str(payload.get("reason") or ""),
    )


def summarize_metrics(metrics: list[UrlFinderValidationMetric]) -> dict[str, object]:
    """Aggregate URL Finder validation metrics without hiding per-candidate evidence."""

    tier_counts: dict[str, int] = {tier: 0 for tier in (SUCCESS_TIER_A, SUCCESS_TIER_B, SUCCESS_TIER_C, SUCCESS_TIER_D)}
    for metric in metrics:
        tier_counts[metric.success_tier] = tier_counts.get(metric.success_tier, 0) + 1
    selected = sum(1 for metric in metrics if metric.selected_url)
    false_negative_count = sum(1 for metric in metrics if metric.false_negative_candidate)
    return {
        "candidate_count": len(metrics),
        "selected_url_count": selected,
        "manual_or_failed_count": len(metrics) - selected,
        "false_negative_candidate_count": false_negative_count,
        "success_tier_counts": tier_counts,
        "boundary": {
            "read_only_url_finder_validation": True,
            "no_candidate_url_write": True,
            "no_connector_registration": True,
            "no_source_activation": True,
            "no_bronze_silver_write": True,
            "no_scheduler_change": True,
        },
    }


def report_payload(metrics: list[UrlFinderValidationMetric], *, benchmark_label: str) -> dict[str, object]:
    """Return a durable JSON report payload for human review exports."""

    return {
        "campaign": "EO-002B Candidate Reprocessing & URL Finder Validation",
        "benchmark_label": benchmark_label,
        "summary": summarize_metrics(metrics),
        "metrics": [metric.to_dict() for metric in metrics],
        "next_decision_questions": [
            "Did the URL Finder select trustworthy origin URLs for A/B-tier candidates?",
            "Do C/D-tier candidates stop because URL discovery is weak, or because gate evidence is missing?",
            "Do false-negative candidates such as Hannover Rück still fail despite search-result context?",
            "Is a Türsteher threshold change justified by evidence, or should URL/evidence discovery improve first?",
        ],
    }
