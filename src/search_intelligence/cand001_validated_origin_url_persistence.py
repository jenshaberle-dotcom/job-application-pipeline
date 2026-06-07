"""CAND-001 Validated Origin URL Persistence Gate.

This module plans the SZ1 transition from a freshly validated Origin Source
Discovery result into ``employer_origin_source_candidates.candidate_url``.
It deliberately separates planning from applying: a selected URL is not written
unless the caller uses an explicit apply path and records an audit review.

The URL Finder report JSON remains review evidence only.  The write source must
be a live bounded URL-Finder validation result or an explicit human-reviewed URL
provided to the CAND-001 runner; exports must not become hidden pipeline inputs.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

CAMPAIGN = "CAND-001 Validated Origin URL Persistence Gate"

BOUNDARY: dict[str, bool] = {
    "sz1_candidate_metadata_transition": True,
    "dry_run_first": True,
    "explicit_apply_required": True,
    "no_gate_write": True,
    "no_evidence_write": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_scheduler_change": True,
    "no_export_as_input_source_of_truth": True,
}

MISSING_URL_MARKERS = {"", "none", "null", "<empty>"}
GOOD_URL_FINDER_TIERS = {"A", "B"}
GOOD_URL_FINDER_DECISIONS = {"origin_url_candidate_selected", "selected", "select_candidate"}


@dataclass(frozen=True)
class CandidatePersistenceSnapshot:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None
    risk_level: str | None = None


@dataclass(frozen=True)
class OriginUrlValidationEvidence:
    selected_url: str | None
    success_tier: str | None
    decision: str | None
    confidence_score: float | None
    reason: str | None
    risk_level: str | None
    source: str = "live_url_finder_validation"


@dataclass(frozen=True)
class PersistencePlanItem:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_status: str
    previous_candidate_url: str | None
    selected_url: str | None
    selected_url_source: str
    url_finder_tier: str | None
    url_finder_decision: str | None
    confidence_score: float | None
    decision: str
    review_status: str
    safety_zone: str
    manual_review_required: bool
    apply_allowed: bool
    applied: bool
    audit_review_id: int | None
    reason: str


@dataclass(frozen=True)
class PersistenceSummary:
    candidate_count: int
    write_recommended_count: int
    applied_count: int
    already_persisted_count: int
    manual_review_required_count: int
    protected_count: int
    no_selected_url_count: int
    conflict_count: int
    decision_counts: dict[str, int]
    boundary: dict[str, bool]


def normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if stripped.lower() in MISSING_URL_MARKERS:
        return None
    return stripped


def same_url(left: str | None, right: str | None) -> bool:
    return (normalize_url(left) or "").rstrip("/") == (normalize_url(right) or "").rstrip("/")


def evidence_from_origin_discovery_payload(payload: Mapping[str, Any]) -> OriginUrlValidationEvidence:
    selected_url = normalize_url(payload.get("selected_url"))
    decision = str(payload.get("decision") or "") or None
    confidence_score = _float_or_none(payload.get("confidence_score"))
    explicit_tier = str(payload.get("success_tier") or payload.get("url_finder_tier") or "").strip().upper()
    success_tier = explicit_tier or derive_success_tier(
        decision=decision,
        confidence_score=confidence_score,
        selected_url=selected_url,
    )

    return OriginUrlValidationEvidence(
        selected_url=selected_url,
        success_tier=success_tier,
        decision=decision,
        confidence_score=confidence_score,
        reason=str(payload.get("reason") or "") or None,
        risk_level=str(payload.get("risk_level") or "") or None,
        source="live_url_finder_validation",
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def derive_success_tier(
    *,
    decision: str | None,
    confidence_score: float | None,
    selected_url: str | None,
) -> str | None:
    """Derive an EO-002B-style success tier when live discovery payload lacks one."""

    normalized_decision = str(decision or "").strip()
    confidence = confidence_score if confidence_score is not None else 0.0
    if selected_url and normalized_decision in GOOD_URL_FINDER_DECISIONS and confidence >= 0.78:
        return "A"
    if selected_url and confidence >= 0.55:
        return "B"
    return None


def _is_good_validated_url(evidence: OriginUrlValidationEvidence) -> bool:
    return (
        normalize_url(evidence.selected_url) is not None
        and (evidence.success_tier or "") in GOOD_URL_FINDER_TIERS
        and (evidence.decision or "") in GOOD_URL_FINDER_DECISIONS
    )


def build_persistence_plan_item(
    candidate: CandidatePersistenceSnapshot,
    evidence: OriginUrlValidationEvidence,
    *,
    include_active_controlled: bool = False,
    duplicate_selected_url_exists: bool = False,
    applied: bool = False,
    audit_review_id: int | None = None,
) -> PersistencePlanItem:
    previous = normalize_url(candidate.candidate_url)
    selected = normalize_url(evidence.selected_url)

    if candidate.status == "active_controlled" and not include_active_controlled:
        decision = "skip_protected_active_controlled"
        review_status = "skipped"
        reason = "Candidate is active_controlled and protected by default; pass explicit override to review it."
        return _plan(candidate, evidence, decision, review_status, False, True, applied, audit_review_id, reason)

    if not selected:
        decision = "no_selected_url"
        review_status = "manual_review_required"
        reason = "No selected validated origin URL is available from live URL-Finder validation."
        return _plan(candidate, evidence, decision, review_status, False, True, applied, audit_review_id, reason)

    if not _is_good_validated_url(evidence):
        decision = "manual_review_required"
        review_status = "manual_review_required"
        reason = "Selected URL exists, but URL-Finder tier or decision is not strong enough for SZ1 persistence."
        return _plan(candidate, evidence, decision, review_status, False, True, applied, audit_review_id, reason)

    if previous and same_url(previous, selected):
        decision = "no_action_already_persisted"
        review_status = "no_action"
        reason = "Candidate already stores the validated origin URL."
        return _plan(candidate, evidence, decision, review_status, False, False, applied, audit_review_id, reason)

    if previous and not same_url(previous, selected):
        decision = "manual_review_required_url_conflict"
        review_status = "manual_review_required"
        reason = "Candidate already has a different candidate_url; URL replacement requires a separate repair/review flow."
        return _plan(candidate, evidence, decision, review_status, False, True, applied, audit_review_id, reason)

    if duplicate_selected_url_exists:
        decision = "manual_review_required_duplicate_url"
        review_status = "manual_review_required"
        reason = "Another candidate already uses the selected URL for this company; duplicate identity review is required."
        return _plan(candidate, evidence, decision, review_status, False, True, applied, audit_review_id, reason)

    decision = "persist_validated_candidate_url"
    review_status = "applied" if applied else "write_recommended"
    reason = "Live URL-Finder validation selected an A/B-tier origin URL and candidate_url is empty; SZ1 persistence is allowed only with explicit apply and audit review."
    return _plan(candidate, evidence, decision, review_status, True, True, applied, audit_review_id, reason)


def _plan(
    candidate: CandidatePersistenceSnapshot,
    evidence: OriginUrlValidationEvidence,
    decision: str,
    review_status: str,
    apply_allowed: bool,
    manual_review_required: bool,
    applied: bool,
    audit_review_id: int | None,
    reason: str,
) -> PersistencePlanItem:
    return PersistencePlanItem(
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_status=candidate.status,
        previous_candidate_url=normalize_url(candidate.candidate_url),
        selected_url=normalize_url(evidence.selected_url),
        selected_url_source=evidence.source,
        url_finder_tier=evidence.success_tier,
        url_finder_decision=evidence.decision,
        confidence_score=evidence.confidence_score,
        decision=decision,
        review_status=review_status,
        safety_zone="SZ1_CANDIDATE_METADATA",
        manual_review_required=manual_review_required,
        apply_allowed=apply_allowed,
        applied=applied,
        audit_review_id=audit_review_id,
        reason=reason,
    )


def summarize_plan(items: Sequence[PersistencePlanItem]) -> PersistenceSummary:
    decision_counts = Counter(item.decision for item in items)
    return PersistenceSummary(
        candidate_count=len(items),
        write_recommended_count=decision_counts.get("persist_validated_candidate_url", 0),
        applied_count=sum(1 for item in items if item.applied),
        already_persisted_count=decision_counts.get("no_action_already_persisted", 0),
        manual_review_required_count=sum(1 for item in items if item.manual_review_required),
        protected_count=decision_counts.get("skip_protected_active_controlled", 0),
        no_selected_url_count=decision_counts.get("no_selected_url", 0),
        conflict_count=decision_counts.get("manual_review_required_url_conflict", 0) + decision_counts.get("manual_review_required_duplicate_url", 0),
        decision_counts=dict(sorted(decision_counts.items())),
        boundary=dict(BOUNDARY),
    )


def report_payload(*, benchmark_label: str, items: Sequence[PersistencePlanItem]) -> dict[str, Any]:
    summary = summarize_plan(items)
    return {
        "benchmark_label": benchmark_label,
        "campaign": CAMPAIGN,
        "summary": asdict(summary),
        "items": [asdict(item) for item in items],
        "decision_questions": [
            "Which A/B-tier live URL-Finder selections are ready for SZ1 candidate_url persistence?",
            "Which candidates are blocked by active_controlled protection, URL conflicts or weak URL-Finder evidence?",
            "Can downstream gate/evidence analysis proceed from persisted candidate state, or only from report evidence?",
        ],
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# CAND-001 Validated Origin URL Persistence Gate",
        "",
        f"Benchmark label: `{payload['benchmark_label']}`",
        "",
        "## Boundary",
        "",
        "This report is an SZ1 candidate-metadata transition plan. Candidate URL writes require explicit apply mode and audit review. It does not write gate reviews, evidence rows, connectors, sources, Bronze/Silver data or scheduler state.",
        "",
        "## Summary",
        "",
        f"- Candidates: {summary['candidate_count']}",
        f"- Write recommended: {summary['write_recommended_count']}",
        f"- Applied: {summary['applied_count']}",
        f"- Already persisted: {summary['already_persisted_count']}",
        f"- Manual review required: {summary['manual_review_required_count']}",
        f"- Protected: {summary['protected_count']}",
        f"- No selected URL: {summary['no_selected_url_count']}",
        f"- Conflicts: {summary['conflict_count']}",
        "",
        "## Candidate URL Persistence Plan",
        "",
        "| Company | Previous URL | Selected URL | Decision | Review Status | Applied | Zone |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in payload["items"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item["company_key"]),
                    str(item.get("previous_candidate_url") or "<none>"),
                    str(item.get("selected_url") or "<none>"),
                    str(item["decision"]),
                    str(item["review_status"]),
                    "yes" if item.get("applied") else "no",
                    str(item["safety_zone"]),
                ]
            )
            + " |"
        )
    lines.extend([
        "",
        "## Decision Counts",
        "",
        "| Decision | Count |",
        "|---|---:|",
    ])
    for decision, count in summary["decision_counts"].items():
        lines.append(f"| {decision} | {count} |")
    lines.extend([
        "",
        "## Notes",
        "",
        "- URL-Finder report exports are review context, not the source of truth for writes.",
        "- Apply mode must rerun or receive explicitly reviewed URL evidence under the CAND-001 command boundary.",
        "- Downstream gate/evidence execution remains deferred until candidate_url is persisted or explicitly reviewed.",
    ])
    return "\n".join(lines) + "\n"
