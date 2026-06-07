"""EO-002C Reprocessing Metrics & Decision Report.

This module reads EO-002B URL Finder validation JSON reports and turns them
into a compact decision report. It is intentionally read-only: no database
connection, no candidate state change, no gate decision, no connector
registration and no scheduler interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

SUCCESS_TIERS = ("A", "B", "C", "D")


@dataclass(frozen=True)
class DecisionReportMetric:
    """Normalized candidate metric used by the EO-002C decision report."""

    candidate_id: int | None
    company_key: str
    company_name: str
    success_tier: str
    selected_url: str | None
    confidence_score: float
    decision: str
    gate_stop: str | None
    false_negative_candidate: bool
    alternative_url_count: int
    rejected_url_count: int
    risk_level: str | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def normalize_metric(payload: Mapping[str, object]) -> DecisionReportMetric:
    """Normalize one metric dictionary from an EO-002B report."""

    success_tier = str(payload.get("success_tier") or "D").strip().upper()
    if success_tier not in SUCCESS_TIERS:
        success_tier = "D"
    selected_url = str(payload.get("selected_url") or "").strip() or None
    return DecisionReportMetric(
        candidate_id=_as_int_or_none(payload.get("candidate_id")),
        company_key=str(payload.get("company_key") or ""),
        company_name=str(payload.get("company_name") or ""),
        success_tier=success_tier,
        selected_url=selected_url,
        confidence_score=_as_float(payload.get("confidence_score")),
        decision=str(payload.get("decision") or ""),
        gate_stop=str(payload.get("gate_stop") or "") or None,
        false_negative_candidate=_as_bool(payload.get("false_negative_candidate")),
        alternative_url_count=_as_int_or_none(payload.get("alternative_url_count")) or 0,
        rejected_url_count=_as_int_or_none(payload.get("rejected_url_count")) or 0,
        risk_level=str(payload.get("risk_level") or "") or None,
        reason=str(payload.get("reason") or ""),
    )


def load_report(path: Path) -> dict[str, object]:
    """Load one EO-002B JSON report."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_metrics_from_reports(paths: Iterable[Path]) -> list[DecisionReportMetric]:
    """Load and normalize all candidate metrics from EO-002B reports."""

    metrics: list[DecisionReportMetric] = []
    seen_keys: set[tuple[str, int | None, str | None]] = set()
    for path in paths:
        report = load_report(path)
        for raw_metric in report.get("metrics", []):
            if not isinstance(raw_metric, Mapping):
                continue
            metric = normalize_metric(raw_metric)
            dedupe_key = (metric.company_key, metric.candidate_id, metric.selected_url)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            metrics.append(metric)
    return metrics


def count_by(items: Iterable[str | None]) -> dict[str, int]:
    """Count strings for stable JSON/Markdown output."""

    counts: dict[str, int] = {}
    for item in items:
        key = item or "<none>"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])))


def summarize_metrics(metrics: list[DecisionReportMetric]) -> dict[str, object]:
    """Return aggregate metrics for the EO-002C report."""

    candidate_count = len(metrics)
    selected_count = sum(1 for metric in metrics if metric.selected_url)
    false_negative_count = sum(1 for metric in metrics if metric.false_negative_candidate)
    tier_counts = {tier: 0 for tier in SUCCESS_TIERS}
    for metric in metrics:
        tier_counts[metric.success_tier] = tier_counts.get(metric.success_tier, 0) + 1
    selected_rate = selected_count / candidate_count if candidate_count else 0.0
    ab_count = tier_counts.get("A", 0) + tier_counts.get("B", 0)
    ab_rate = ab_count / candidate_count if candidate_count else 0.0
    average_confidence = (
        sum(metric.confidence_score for metric in metrics) / candidate_count if candidate_count else 0.0
    )
    return {
        "candidate_count": candidate_count,
        "selected_url_count": selected_count,
        "selected_url_rate": round(selected_rate, 4),
        "ab_tier_count": ab_count,
        "ab_tier_rate": round(ab_rate, 4),
        "false_negative_candidate_count": false_negative_count,
        "average_confidence_score": round(average_confidence, 4),
        "success_tier_counts": tier_counts,
        "gate_stop_counts": count_by(metric.gate_stop for metric in metrics),
        "decision_counts": count_by(metric.decision for metric in metrics),
        "boundary": {
            "read_only_decision_report": True,
            "no_candidate_write": True,
            "no_gate_write": True,
            "no_connector_registration": True,
            "no_source_activation": True,
            "no_scheduler_change": True,
        },
    }


def build_decision_recommendations(metrics: list[DecisionReportMetric]) -> list[str]:
    """Create evidence-based, non-mutating next-step recommendations."""

    summary = summarize_metrics(metrics)
    candidate_count = int(summary["candidate_count"])
    if candidate_count == 0:
        return [
            "collect_eo002b_validation_data_first: no candidate metrics were available, so no gate or scheduler decision is justified.",
        ]

    selected_rate = float(summary["selected_url_rate"])
    ab_rate = float(summary["ab_tier_rate"])
    false_negative_count = int(summary["false_negative_candidate_count"])
    gate_stops = summary["gate_stop_counts"]
    recommendations: list[str] = []

    if selected_rate < 0.35:
        recommendations.append(
            "prioritize_url_finder_repair: selected-url rate is low; do not weaken the Türsteher before URL discovery improves."
        )
    elif ab_rate >= 0.6:
        recommendations.append(
            "prioritize_gate_stop_analysis: URL Finder output is strong enough to inspect evidence gates and next-safe-action stops."
        )
    else:
        recommendations.append(
            "continue_controlled_validation: URL Finder signal is mixed; keep the guest list bounded and inspect per-candidate evidence."
        )

    if false_negative_count:
        recommendations.append(
            "inspect_false_negative_candidates: critical false-negative candidates remain decision-critical and must be reviewed explicitly."
        )

    if isinstance(gate_stops, Mapping) and gate_stops and gate_stops.get("<none>", 0) < candidate_count:
        recommendations.append(
            "join_gate_review_history_next: gate-stop distribution is visible enough to justify a focused gate-history join, not a broad gate rewrite."
        )
    else:
        recommendations.append(
            "add_gate_stop_join_before_gate_changes: reports lack enough gate-stop context for a responsible Türsteher or gate redesign."
        )

    recommendations.append(
        "keep_scheduler_changes_deferred: Wave/Scheduler automation should wait until EO-002B/EO-002C outcomes are understood."
    )
    return recommendations


def build_decision_report(
    metrics: list[DecisionReportMetric],
    *,
    benchmark_label: str,
    source_reports: Iterable[str],
) -> dict[str, object]:
    """Build the EO-002C JSON report payload."""

    return {
        "campaign": "EO-002C Reprocessing Metrics & Decision Report",
        "benchmark_label": benchmark_label,
        "source_reports": list(source_reports),
        "summary": summarize_metrics(metrics),
        "recommendations": build_decision_recommendations(metrics),
        "false_negative_candidates": [
            metric.to_dict() for metric in metrics if metric.false_negative_candidate
        ],
        "candidate_metrics": [metric.to_dict() for metric in metrics],
        "decision_questions": [
            "Is the URL Finder selecting plausible origin URLs often enough for the current candidate cohort?",
            "Do failures cluster around URL discovery, evidence gates, or missing gate-stop context?",
            "Are false-negative candidates still blocked after the guest-list validation path?",
            "Is a Türsteher change justified by measured downstream outcomes, or is more evidence discovery needed first?",
        ],
    }


def _format_percent(value: object) -> str:
    return f"{float(value) * 100:.1f}%"


def render_markdown_report(report: Mapping[str, object]) -> str:
    """Render a human-readable Markdown decision report."""

    summary = report.get("summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    tier_counts = summary.get("success_tier_counts", {})
    if not isinstance(tier_counts, Mapping):
        tier_counts = {}
    gate_stops = summary.get("gate_stop_counts", {})
    if not isinstance(gate_stops, Mapping):
        gate_stops = {}
    decisions = summary.get("decision_counts", {})
    if not isinstance(decisions, Mapping):
        decisions = {}

    lines = [
        "# EO-002C Reprocessing Metrics & Decision Report",
        "",
        f"Benchmark label: `{report.get('benchmark_label', '')}`",
        "",
        "## Boundary",
        "",
        "This report is read-only. It does not write candidates, gates, connectors, sources, Bronze/Silver data or scheduler state.",
        "",
        "## Summary",
        "",
        "Decision confidence describes confidence in the URL-finder decision such as `selected`, `manual_review_required` or `not_found`. It is not a confidence score for a selected URL when no URL was selected.",
        "",
        f"- Candidates: {summary.get('candidate_count', 0)}",
        f"- Selected URLs: {summary.get('selected_url_count', 0)} ({_format_percent(summary.get('selected_url_rate', 0.0))})",
        f"- A/B-tier candidates: {summary.get('ab_tier_count', 0)} ({_format_percent(summary.get('ab_tier_rate', 0.0))})",
        f"- False-negative candidates: {summary.get('false_negative_candidate_count', 0)}",
        f"- Average decision confidence: {float(summary.get('average_confidence_score', 0.0)):.3f}",
        "",
        "## Success Tiers",
        "",
        "| Tier | Count |",
        "|---|---:|",
    ]
    for tier in SUCCESS_TIERS:
        lines.append(f"| {tier} | {tier_counts.get(tier, 0)} |")

    lines.extend(["", "## Gate Stops", "", "| Gate Stop | Count |", "|---|---:|"])
    for gate_stop, count in gate_stops.items():
        lines.append(f"| {gate_stop} | {count} |")

    lines.extend(["", "## Decisions", "", "| Decision | Count |", "|---|---:|"])
    for decision, count in decisions.items():
        lines.append(f"| {decision} | {count} |")

    lines.extend(["", "## Recommendations", ""])
    for recommendation in report.get("recommendations", []):
        lines.append(f"- {recommendation}")

    false_negatives = report.get("false_negative_candidates", [])
    if isinstance(false_negatives, list) and false_negatives:
        lines.extend(["", "## False-Negative Candidates", "", "| Company | Tier | Selected URL | Decision |", "|---|---|---|---|"])
        for item in false_negatives:
            if not isinstance(item, Mapping):
                continue
            lines.append(
                "| "
                + str(item.get("company_name") or item.get("company_key") or "")
                + " | "
                + str(item.get("success_tier") or "")
                + " | "
                + str(item.get("selected_url") or "<none>")
                + " | "
                + str(item.get("decision") or "")
                + " |"
            )

    lines.extend(["", "## Source Reports", ""])
    for source in report.get("source_reports", []):
        lines.append(f"- `{source}`")

    return "\n".join(lines).rstrip() + "\n"
