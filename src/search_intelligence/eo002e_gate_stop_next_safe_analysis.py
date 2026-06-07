"""EO-002E Gate Stop / Next-Safe-Action Evidence Analysis.

Read-only analysis layer for the point after EO-002D selected plausible origin
URLs.  The module combines candidate URL state, optional EO-002B URL Finder
reports, persisted gate reviews and recent action-run observations into a
single decision report.  It deliberately does not write candidate URLs, gate
reviews, evidence rows, connector registrations or scheduler state.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
import json

from src.search_intelligence.gate_stop_classification import classify_gate_stop

CAMPAIGN = "EO-002E Gate Stop / Next-Safe-Action Evidence Analysis"

READ_ONLY_BOUNDARY: dict[str, bool] = {
    "read_only_gate_stop_analysis": True,
    "no_candidate_url_write": True,
    "no_gate_write": True,
    "no_evidence_write": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_scheduler_change": True,
}

EARLY_GATE_SEQUENCE: tuple[str, ...] = (
    "candidate_url_persistence",
    "technical_reachability_gate",
    "risk_gate",
    "relevance_gate",
)
DETAIL_EVIDENCE_GATE = "detail_evidence_gate"

STOP_LIKE_STATUSES = {"failed", "manual_review_required", "deferred"}
STOP_LIKE_DECISIONS = {"abort_documented", "manual_review_required"}
PASSED_STATUS = "passed"
MISSING_URL_MARKERS = {"", "none", "null", "<empty>"}


@dataclass(frozen=True)
class UrlFinderEvidence:
    company_key: str
    selected_url: str | None
    success_tier: str | None
    decision: str | None
    confidence_score: float | None
    alternative_url_count: int = 0
    rejected_url_count: int = 0
    false_negative_candidate: bool = False


@dataclass(frozen=True)
class CandidateSnapshot:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None
    risk_level: str | None = None


@dataclass(frozen=True)
class GateReviewSnapshot:
    gate_name: str
    gate_order: int | None
    gate_status: str | None
    decision: str | None
    stop_reason: str | None
    evidence: Mapping[str, Any] | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class ActionRunSnapshot:
    action_type: str
    status: str
    exit_code: int | None = None
    error_summary: str | None = None
    gate_review_created: bool | None = None
    gate_review_gate_name: str | None = None
    gate_review_status: str | None = None
    gate_review_decision: str | None = None
    started_at: str | None = None


@dataclass(frozen=True)
class CandidateGateStopAnalysis:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_status: str
    candidate_url: str | None
    effective_origin_url: str | None
    effective_origin_url_source: str
    selected_url_from_report: str | None
    url_finder_tier: str | None
    url_finder_decision: str | None
    gate_stop: str | None
    gate_stop_decision: str | None
    gate_stop_category: str | None
    gate_stop_terminal: bool
    gate_stop_default_reprocess: str | None
    first_missing_step: str | None
    passed_gate_count: int
    stop_like_gate_count: int
    recent_action_count: int
    latest_action_type: str | None
    latest_action_status: str | None
    latest_action_error: str | None
    recommended_next_safe_action: str
    recommendation_reason: str
    safety_zone: str
    manual_review_required: bool
    false_negative_candidate: bool


@dataclass(frozen=True)
class AnalysisSummary:
    candidate_count: int
    selected_url_count: int
    persisted_candidate_url_count: int
    report_selected_url_only_count: int
    no_origin_url_count: int
    manual_review_required_count: int
    false_negative_candidate_count: int
    recommendation_counts: dict[str, int]
    gate_stop_category_counts: dict[str, int]
    first_missing_step_counts: dict[str, int]
    safety_zone_counts: dict[str, int]
    boundary: dict[str, bool]


def normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if stripped.lower() in MISSING_URL_MARKERS:
        return None
    return stripped


def gate_is_passed(gate: GateReviewSnapshot | None) -> bool:
    return bool(gate and (gate.gate_status or "") == PASSED_STATUS)


def gate_is_stop_like(gate: GateReviewSnapshot | None) -> bool:
    if gate is None:
        return False
    return (gate.gate_status or "") in STOP_LIKE_STATUSES or (gate.decision or "") in STOP_LIKE_DECISIONS


def gate_order_value(gate: GateReviewSnapshot) -> int:
    return gate.gate_order if gate.gate_order is not None else 999


def latest_stop_like_gate(gates: Sequence[GateReviewSnapshot]) -> GateReviewSnapshot | None:
    stop_like = [gate for gate in gates if gate_is_stop_like(gate)]
    if not stop_like:
        return None
    return sorted(stop_like, key=gate_order_value)[0]


def first_missing_step(gates_by_name: Mapping[str, GateReviewSnapshot]) -> str | None:
    for gate_name in EARLY_GATE_SEQUENCE:
        if not gate_is_passed(gates_by_name.get(gate_name)):
            return gate_name
    if not gate_is_passed(gates_by_name.get(DETAIL_EVIDENCE_GATE)):
        return DETAIL_EVIDENCE_GATE
    return None


def choose_effective_origin_url(
    candidate: CandidateSnapshot,
    url_finder: UrlFinderEvidence | None,
) -> tuple[str | None, str]:
    persisted = normalize_url(candidate.candidate_url)
    if persisted:
        return persisted, "persisted_candidate_url"
    selected = normalize_url(url_finder.selected_url if url_finder else None)
    if selected:
        return selected, "validated_url_finder_report"
    return None, "missing"


def _latest_action(action_runs: Sequence[ActionRunSnapshot]) -> ActionRunSnapshot | None:
    return action_runs[0] if action_runs else None


def _recommend_without_origin_url() -> tuple[str, str, str, bool]:
    return (
        "run_origin_url_finder_validation",
        "No persisted candidate URL and no selected URL Finder evidence is available; URL discovery must come before gate review.",
        "SZ0_READ_ONLY",
        False,
    )


def _recommend_validated_url_not_persisted() -> tuple[str, str, str, bool]:
    return (
        "review_candidate_url_write_from_validated_report",
        "URL Finder selected an A/B-style origin URL, but candidate_url is not persisted; write requires explicit SZ1 review/apply boundary.",
        "SZ1_CANDIDATE_METADATA",
        True,
    )


def _recommend_from_stop(classification_category: str | None, terminal: bool) -> tuple[str, str, str, bool]:
    category = classification_category or "unclassified_stop"
    if terminal:
        return (
            "manual_review_terminal_stop",
            "A stop-like gate is classified as terminal; automated retries are blocked without explicit override.",
            "SZ2_EVIDENCE_AND_GATES",
            True,
        )
    if category == "detail_discovery_gap":
        return (
            "run_detail_evidence_discovery_plan",
            "The selected origin source needs bounded detail/job evidence discovery before connector candidacy.",
            "SZ2_EVIDENCE_AND_GATES",
            False,
        )
    if category == "weak_relevance_evidence":
        return (
            "run_relevance_evidence_discovery_plan",
            "The stop is recoverable relevance evidence weakness; run bounded relevance/detail discovery instead of weakening the Türsteher.",
            "SZ2_EVIDENCE_AND_GATES",
            False,
        )
    if category in {"recoverable_url_problem", "technical_reachability_review"}:
        return (
            "run_source_url_recovery_plan",
            "The persisted URL or reachability evidence is recoverable; run bounded URL recovery before gate retry.",
            "SZ1_CANDIDATE_METADATA",
            False,
        )
    return (
        "manual_review_or_targeted_reprocess_plan",
        "The gate stop is reviewable but not specific enough; inspect evidence before changing gates or Türsteher thresholds.",
        "SZ2_EVIDENCE_AND_GATES",
        True,
    )


def _recommend_from_missing_gate(missing_gate: str | None, url_source: str) -> tuple[str, str, str, bool]:
    if missing_gate is None:
        return (
            "delegate_to_connector_candidate_chain_plan",
            "No early/detail gate blocker is visible; delegate to the canonical connector-candidate chain in plan mode.",
            "SZ3_CONNECTOR_ARTIFACTS",
            False,
        )
    if url_source == "validated_url_finder_report":
        return _recommend_validated_url_not_persisted()
    if missing_gate == DETAIL_EVIDENCE_GATE:
        return (
            "run_detail_evidence_discovery_plan",
            "Early gates appear ready/passed but detail_evidence_gate is missing or not passed.",
            "SZ2_EVIDENCE_AND_GATES",
            False,
        )
    return (
        "run_initial_gate_review_plan",
        f"Gate {missing_gate!r} is missing or not passed; run the bounded initial gate review in plan/apply-controlled mode.",
        "SZ2_EVIDENCE_AND_GATES",
        False,
    )


def analyze_candidate(
    candidate: CandidateSnapshot,
    gates: Sequence[GateReviewSnapshot],
    *,
    url_finder: UrlFinderEvidence | None = None,
    action_runs: Sequence[ActionRunSnapshot] = (),
) -> CandidateGateStopAnalysis:
    effective_url, url_source = choose_effective_origin_url(candidate, url_finder)
    gates_by_name = {gate.gate_name: gate for gate in gates}
    stop_gate = latest_stop_like_gate(gates)
    missing_step = first_missing_step(gates_by_name)
    if (
        url_source == "persisted_candidate_url"
        and not stop_gate
        and missing_step == "candidate_url_persistence"
    ):
        missing_step = "initial_gate_review"
    classification = None

    if not effective_url:
        action, reason, zone, review_required = _recommend_without_origin_url()
    elif url_source == "validated_url_finder_report":
        action, reason, zone, review_required = _recommend_validated_url_not_persisted()
    elif stop_gate is not None:
        classification = classify_gate_stop(
            gate_name=stop_gate.gate_name,
            gate_status=stop_gate.gate_status,
            decision=stop_gate.decision,
            stop_reason=stop_gate.stop_reason,
            evidence=stop_gate.evidence or {},
        )
        action, reason, zone, review_required = _recommend_from_stop(classification.category, classification.terminal)
    else:
        action, reason, zone, review_required = _recommend_from_missing_gate(missing_step, url_source)

    latest_action = _latest_action(action_runs)
    passed_count = sum(1 for gate in gates if gate_is_passed(gate))
    stop_count = sum(1 for gate in gates if gate_is_stop_like(gate))

    return CandidateGateStopAnalysis(
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_status=candidate.status,
        candidate_url=normalize_url(candidate.candidate_url),
        effective_origin_url=effective_url,
        effective_origin_url_source=url_source,
        selected_url_from_report=normalize_url(url_finder.selected_url if url_finder else None),
        url_finder_tier=url_finder.success_tier if url_finder else None,
        url_finder_decision=url_finder.decision if url_finder else None,
        gate_stop=stop_gate.gate_name if stop_gate else None,
        gate_stop_decision=stop_gate.decision if stop_gate else None,
        gate_stop_category=classification.category if classification else None,
        gate_stop_terminal=bool(classification.terminal if classification else False),
        gate_stop_default_reprocess=classification.default_reprocess if classification else None,
        first_missing_step=missing_step,
        passed_gate_count=passed_count,
        stop_like_gate_count=stop_count,
        recent_action_count=len(action_runs),
        latest_action_type=latest_action.action_type if latest_action else None,
        latest_action_status=latest_action.status if latest_action else None,
        latest_action_error=latest_action.error_summary if latest_action else None,
        recommended_next_safe_action=action,
        recommendation_reason=reason,
        safety_zone=zone,
        manual_review_required=review_required,
        false_negative_candidate=bool(url_finder.false_negative_candidate if url_finder else False),
    )


def summarize_analyses(analyses: Sequence[CandidateGateStopAnalysis]) -> AnalysisSummary:
    return AnalysisSummary(
        candidate_count=len(analyses),
        selected_url_count=sum(1 for item in analyses if item.selected_url_from_report),
        persisted_candidate_url_count=sum(1 for item in analyses if item.effective_origin_url_source == "persisted_candidate_url"),
        report_selected_url_only_count=sum(1 for item in analyses if item.effective_origin_url_source == "validated_url_finder_report"),
        no_origin_url_count=sum(1 for item in analyses if item.effective_origin_url_source == "missing"),
        manual_review_required_count=sum(1 for item in analyses if item.manual_review_required),
        false_negative_candidate_count=sum(1 for item in analyses if item.false_negative_candidate),
        recommendation_counts=dict(Counter(item.recommended_next_safe_action for item in analyses)),
        gate_stop_category_counts=dict(Counter(item.gate_stop_category or "<none>" for item in analyses)),
        first_missing_step_counts=dict(Counter(item.first_missing_step or "<none>" for item in analyses)),
        safety_zone_counts=dict(Counter(item.safety_zone for item in analyses)),
        boundary=dict(READ_ONLY_BOUNDARY),
    )


def load_url_finder_evidence(report_paths: Iterable[Path]) -> dict[str, UrlFinderEvidence]:
    evidence: dict[str, UrlFinderEvidence] = {}
    for path in report_paths:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"EO-002B URL Finder report not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for metric in payload.get("metrics", []):
            company_key = str(metric.get("company_key") or "").strip()
            if not company_key:
                continue
            evidence[company_key] = UrlFinderEvidence(
                company_key=company_key,
                selected_url=metric.get("selected_url"),
                success_tier=metric.get("success_tier"),
                decision=metric.get("decision"),
                confidence_score=_as_float(metric.get("confidence_score")),
                alternative_url_count=int(metric.get("alternative_url_count") or 0),
                rejected_url_count=int(metric.get("rejected_url_count") or 0),
                false_negative_candidate=bool(metric.get("false_negative_candidate")),
            )
    return evidence


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def report_payload(
    analyses: Sequence[CandidateGateStopAnalysis],
    *,
    benchmark_label: str,
    source_url_finder_reports: Sequence[str] = (),
) -> dict[str, Any]:
    summary = summarize_analyses(analyses)
    return {
        "benchmark_label": benchmark_label,
        "campaign": CAMPAIGN,
        "summary": asdict(summary),
        "candidate_analyses": [asdict(item) for item in analyses],
        "source_url_finder_reports": list(source_url_finder_reports),
        "decision_questions": [
            "For candidates with selected origin URLs, is candidate_url persisted or only present in validation reports?",
            "Which gate or missing step blocks the candidate after URL discovery?",
            "Is the next safe action read-only analysis, SZ1 candidate metadata write, or SZ2 evidence/gate work?",
            "Do false-negative candidates still stop because of evidence discovery rather than candidate promotion?",
        ],
        "recommendations": recommendations(summary),
    }


def recommendations(summary: AnalysisSummary) -> list[str]:
    items: list[str] = []
    if summary.report_selected_url_only_count:
        items.append(
            "persist_selected_url_review_required: some candidates have validated selected URLs but no persisted candidate_url; review SZ1 write/apply path before gate execution."
        )
    if summary.no_origin_url_count:
        items.append(
            "continue_url_finder_validation: some candidates still lack any origin URL evidence."
        )
    if summary.gate_stop_category_counts.get("detail_discovery_gap", 0):
        items.append(
            "prioritize_detail_evidence_discovery: stop analysis shows detail evidence gaps after origin URL discovery."
        )
    if summary.first_missing_step_counts.get("initial_gate_review", 0):
        items.append(
            "run_initial_gate_review_plan: persisted origin URLs are present, but initial gate review is still missing."
        )
    if summary.first_missing_step_counts.get(DETAIL_EVIDENCE_GATE, 0):
        items.append(
            "run_detail_evidence_plan: early gates are no longer the only issue; detail evidence needs bounded discovery."
        )
    if summary.manual_review_required_count:
        items.append(
            "keep_manual_review_boundary: at least one recommendation crosses a write/review boundary; do not auto-apply."
        )
    if not items:
        items.append(
            "delegate_to_connector_candidate_chain_plan: no obvious URL/gate blocker surfaced in the analyzed cohort."
        )
    items.append("keep_scheduler_changes_deferred: this report does not justify scheduler or Wave automation changes.")
    return items


def markdown_report(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    analyses = payload["candidate_analyses"]
    lines: list[str] = []
    lines.append("# EO-002E Gate Stop / Next-Safe-Action Evidence Analysis")
    lines.append("")
    lines.append(f"Benchmark label: `{payload['benchmark_label']}`")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("This report is read-only. It does not write candidate URLs, gate reviews, evidence rows, connectors, sources, Bronze/Silver data or scheduler state.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Candidates: {summary['candidate_count']}")
    lines.append(f"- Selected URLs from URL Finder reports: {summary['selected_url_count']}")
    lines.append(f"- Persisted candidate URLs: {summary['persisted_candidate_url_count']}")
    lines.append(f"- Report-selected URLs not persisted: {summary['report_selected_url_only_count']}")
    lines.append(f"- Missing origin URLs: {summary['no_origin_url_count']}")
    lines.append(f"- Manual review required: {summary['manual_review_required_count']}")
    lines.append(f"- False-negative candidates: {summary['false_negative_candidate_count']}")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    for item in payload.get("recommendations", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Candidate Analysis")
    lines.append("")
    lines.append("| Company | Effective Origin URL | URL Source | Gate Stop | Missing Step | Next Safe Action | Zone | Review |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for item in analyses:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["company_key"]),
                    str(item.get("effective_origin_url") or "<none>"),
                    str(item.get("effective_origin_url_source") or "<none>"),
                    str(item.get("gate_stop") or "<none>"),
                    str(item.get("first_missing_step") or "<none>"),
                    str(item.get("recommended_next_safe_action") or "<none>"),
                    str(item.get("safety_zone") or "<none>"),
                    "yes" if item.get("manual_review_required") else "no",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Recommendation Counts")
    lines.append("")
    lines.append("| Recommendation | Count |")
    lines.append("|---|---:|")
    for key, count in sorted(summary["recommendation_counts"].items()):
        lines.append(f"| {key} | {count} |")
    lines.append("")
    lines.append("## Gate Stop Categories")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|---|---:|")
    for key, count in sorted(summary["gate_stop_category_counts"].items()):
        lines.append(f"| {key} | {count} |")
    lines.append("")
    lines.append("## Source URL Finder Reports")
    lines.append("")
    for report in payload.get("source_url_finder_reports", []):
        lines.append(f"- `{report}`")
    lines.append("")
    return "\n".join(lines)
