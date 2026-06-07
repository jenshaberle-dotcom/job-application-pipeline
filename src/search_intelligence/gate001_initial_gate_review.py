"""GATE-001 Initial Gate Review Foundation.

Read-mostly decision layer for the first SZ2 evidence/gate transition after
CAND-001 persisted a validated origin URL into candidate state.  The module is
pure Python and deliberately separates evaluation from database writes so the
CLI can run dry-run first and apply only under an explicit boundary.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
import ipaddress

SOURCE_DISCOVERY_GATE = "source_discovery"
TECHNICAL_REACHABILITY_GATE = "technical_reachability_gate"
RISK_GATE = "risk_gate"

INITIAL_GATE_ORDER: dict[str, int] = {
    SOURCE_DISCOVERY_GATE: 2,
    TECHNICAL_REACHABILITY_GATE: 4,
    RISK_GATE: 3,
}

MISSING_URL_MARKERS = {"", "none", "null", "<empty>"}
STRONG_RISK_MARKERS = {
    "access denied",
    "blocked",
    "bot detection",
    "captcha",
    "cloudflare challenge",
    "forbidden",
    "hcaptcha",
    "recaptcha",
}
PRIVATE_HOST_MARKERS = {"localhost", "metadata.google.internal"}
READ_ONLY_BOUNDARY: dict[str, bool] = {
    "dry_run_first": True,
    "explicit_apply_required": True,
    "no_candidate_url_write": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_scheduler_change": True,
    "no_bronze_silver_write": True,
    "sz2_evidence_and_gate_transition": True,
}


@dataclass(frozen=True)
class CandidateSnapshot:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None


@dataclass(frozen=True)
class ProbeResult:
    url: str
    final_url: str | None
    reachable: bool
    career_like: bool
    status_code: int | None
    title: str | None
    response_bytes: int
    reason: str
    risk_markers: tuple[str, ...] = ()
    blocked_by_security: bool = False


@dataclass(frozen=True)
class InitialGateEvaluation:
    candidate_id: int
    company_key: str
    company_name: str
    gate_name: str
    gate_order: int
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any]
    apply_allowed: bool
    manual_review_required: bool
    safety_zone: str = "SZ2_EVIDENCE_AND_GATES"


@dataclass(frozen=True)
class CandidateInitialGatePlan:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str | None
    evaluations: tuple[InitialGateEvaluation, ...]
    recommended_next_safe_action: str
    recommendation_reason: str
    applied: bool = False


@dataclass(frozen=True)
class InitialGateReviewSummary:
    candidate_count: int
    evaluation_count: int
    write_recommended_count: int
    applied_count: int
    passed_count: int
    manual_review_required_count: int
    failed_count: int
    deferred_count: int
    decision_counts: dict[str, int]
    gate_status_counts: dict[str, int]
    gate_name_counts: dict[str, int]
    recommendation_counts: dict[str, int]
    boundary: dict[str, bool]


def normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if stripped.lower() in MISSING_URL_MARKERS:
        return None
    return stripped


def host_is_disallowed(hostname: str | None) -> tuple[bool, str | None]:
    if not hostname:
        return True, "missing hostname"
    host = hostname.strip().lower().rstrip(".")
    if host in PRIVATE_HOST_MARKERS or host.endswith(".local") or host.endswith(".localhost"):
        return True, "local/private hostname blocked"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False, None
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        return True, "private/local/reserved IP blocked"
    return False, None


def security_precheck_url(url: str | None) -> tuple[bool, str | None]:
    normalized = normalize_url(url)
    if not normalized:
        return False, "missing URL"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported URL scheme"
    blocked, reason = host_is_disallowed(parsed.hostname)
    if blocked:
        return False, reason or "host blocked"
    return True, None


def risk_markers_from_probe(probe: ProbeResult | None) -> tuple[str, ...]:
    if probe is None:
        return ()
    markers = {str(marker).strip().lower() for marker in probe.risk_markers if str(marker).strip()}
    reason = (probe.reason or "").lower()
    title = (probe.title or "").lower()
    for marker in STRONG_RISK_MARKERS:
        if marker in reason or marker in title:
            markers.add(marker)
    return tuple(sorted(markers))


def _base_evidence(candidate: CandidateSnapshot, *, reviewed_by: str, source: str = "persisted_candidate_url") -> dict[str, Any]:
    return {
        "company_key": candidate.company_key,
        "candidate_url": normalize_url(candidate.candidate_url),
        "evidence_source": source,
        "reviewed_by": reviewed_by,
        "boundary": dict(READ_ONLY_BOUNDARY),
    }


def evaluate_source_discovery_gate(candidate: CandidateSnapshot, *, reviewed_by: str) -> InitialGateEvaluation:
    url = normalize_url(candidate.candidate_url)
    evidence = _base_evidence(candidate, reviewed_by=reviewed_by)
    if url:
        return InitialGateEvaluation(
            candidate.candidate_id,
            candidate.company_key,
            candidate.company_name,
            SOURCE_DISCOVERY_GATE,
            INITIAL_GATE_ORDER[SOURCE_DISCOVERY_GATE],
            "passed",
            "passed",
            None,
            evidence | {"url_present": True},
            apply_allowed=True,
            manual_review_required=False,
        )
    return InitialGateEvaluation(
        candidate.candidate_id,
        candidate.company_key,
        candidate.company_name,
        SOURCE_DISCOVERY_GATE,
        INITIAL_GATE_ORDER[SOURCE_DISCOVERY_GATE],
        "manual_review_required",
        "manual_review_required",
        "candidate_url is missing; CAND-001 or manual review must persist a validated origin URL first",
        evidence | {"url_present": False},
        apply_allowed=True,
        manual_review_required=True,
    )


def evaluate_technical_reachability_gate(
    candidate: CandidateSnapshot,
    *,
    probe: ProbeResult | None,
    reviewed_by: str,
) -> InitialGateEvaluation:
    url = normalize_url(candidate.candidate_url)
    evidence = _base_evidence(candidate, reviewed_by=reviewed_by)
    allowed, security_reason = security_precheck_url(url)
    if not allowed:
        return InitialGateEvaluation(
            candidate.candidate_id,
            candidate.company_key,
            candidate.company_name,
            TECHNICAL_REACHABILITY_GATE,
            INITIAL_GATE_ORDER[TECHNICAL_REACHABILITY_GATE],
            "manual_review_required",
            "manual_review_required",
            f"URL security precheck failed: {security_reason}",
            evidence | {"security_precheck": "blocked", "security_reason": security_reason},
            apply_allowed=True,
            manual_review_required=True,
        )
    if probe is None:
        return InitialGateEvaluation(
            candidate.candidate_id,
            candidate.company_key,
            candidate.company_name,
            TECHNICAL_REACHABILITY_GATE,
            INITIAL_GATE_ORDER[TECHNICAL_REACHABILITY_GATE],
            "deferred",
            "manual_review_required",
            "bounded HTTP probe was not executed",
            evidence | {"probe_executed": False},
            apply_allowed=True,
            manual_review_required=True,
        )
    probe_evidence = asdict(probe)
    if probe.blocked_by_security:
        return InitialGateEvaluation(
            candidate.candidate_id,
            candidate.company_key,
            candidate.company_name,
            TECHNICAL_REACHABILITY_GATE,
            INITIAL_GATE_ORDER[TECHNICAL_REACHABILITY_GATE],
            "manual_review_required",
            "manual_review_required",
            f"bounded probe blocked by security: {probe.reason}",
            evidence | {"probe": probe_evidence},
            apply_allowed=True,
            manual_review_required=True,
        )
    if probe.reachable and probe.career_like:
        return InitialGateEvaluation(
            candidate.candidate_id,
            candidate.company_key,
            candidate.company_name,
            TECHNICAL_REACHABILITY_GATE,
            INITIAL_GATE_ORDER[TECHNICAL_REACHABILITY_GATE],
            "passed",
            "passed",
            None,
            evidence | {"probe": probe_evidence},
            apply_allowed=True,
            manual_review_required=False,
        )
    return InitialGateEvaluation(
        candidate.candidate_id,
        candidate.company_key,
        candidate.company_name,
        TECHNICAL_REACHABILITY_GATE,
        INITIAL_GATE_ORDER[TECHNICAL_REACHABILITY_GATE],
        "manual_review_required",
        "manual_review_required",
        probe.reason or "URL was not reachable or not career-like in bounded probe",
        evidence | {"probe": probe_evidence},
        apply_allowed=True,
        manual_review_required=True,
    )


def evaluate_risk_gate(
    candidate: CandidateSnapshot,
    *,
    probe: ProbeResult | None,
    reviewed_by: str,
) -> InitialGateEvaluation:
    evidence = _base_evidence(candidate, reviewed_by=reviewed_by)
    markers = risk_markers_from_probe(probe)
    if probe is None:
        return InitialGateEvaluation(
            candidate.candidate_id,
            candidate.company_key,
            candidate.company_name,
            RISK_GATE,
            INITIAL_GATE_ORDER[RISK_GATE],
            "deferred",
            "manual_review_required",
            "bounded HTTP probe was not executed; risk gate cannot be passed",
            evidence | {"risk_markers": list(markers), "probe_executed": False},
            apply_allowed=True,
            manual_review_required=True,
        )
    if markers:
        return InitialGateEvaluation(
            candidate.candidate_id,
            candidate.company_key,
            candidate.company_name,
            RISK_GATE,
            INITIAL_GATE_ORDER[RISK_GATE],
            "manual_review_required",
            "manual_review_required",
            "bounded probe found risk markers requiring review",
            evidence | {"risk_markers": list(markers), "probe": asdict(probe)},
            apply_allowed=True,
            manual_review_required=True,
        )
    return InitialGateEvaluation(
        candidate.candidate_id,
        candidate.company_key,
        candidate.company_name,
        RISK_GATE,
        INITIAL_GATE_ORDER[RISK_GATE],
        "passed",
        "passed",
        None,
        evidence | {"risk_markers": [], "probe": asdict(probe)},
        apply_allowed=True,
        manual_review_required=False,
    )


def build_initial_gate_plan(
    candidate: CandidateSnapshot,
    *,
    probe: ProbeResult | None,
    reviewed_by: str,
) -> CandidateInitialGatePlan:
    evaluations = [evaluate_source_discovery_gate(candidate, reviewed_by=reviewed_by)]
    if normalize_url(candidate.candidate_url):
        evaluations.append(evaluate_technical_reachability_gate(candidate, probe=probe, reviewed_by=reviewed_by))
        evaluations.append(evaluate_risk_gate(candidate, probe=probe, reviewed_by=reviewed_by))
    if all(e.gate_status == "passed" for e in evaluations):
        next_action = "run_detail_evidence_discovery_plan"
        reason = "initial source, reachability and risk gates are passed; continue with bounded detail evidence discovery."
    elif any(e.manual_review_required for e in evaluations):
        next_action = "manual_review_initial_gate_outcome"
        reason = "one or more initial gates require review before downstream evidence discovery."
    else:
        next_action = "defer_until_probe_or_candidate_url_available"
        reason = "initial gate review is incomplete and should not progress automatically."
    return CandidateInitialGatePlan(
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_url=normalize_url(candidate.candidate_url),
        evaluations=tuple(evaluations),
        recommended_next_safe_action=next_action,
        recommendation_reason=reason,
    )


def summarize_plans(plans: Sequence[CandidateInitialGatePlan]) -> InitialGateReviewSummary:
    evaluations = [evaluation for plan in plans for evaluation in plan.evaluations]
    return InitialGateReviewSummary(
        candidate_count=len(plans),
        evaluation_count=len(evaluations),
        write_recommended_count=sum(1 for evaluation in evaluations if evaluation.apply_allowed),
        applied_count=sum(1 for plan in plans if plan.applied),
        passed_count=sum(1 for evaluation in evaluations if evaluation.gate_status == "passed"),
        manual_review_required_count=sum(1 for evaluation in evaluations if evaluation.manual_review_required),
        failed_count=sum(1 for evaluation in evaluations if evaluation.gate_status == "failed"),
        deferred_count=sum(1 for evaluation in evaluations if evaluation.gate_status == "deferred"),
        decision_counts=dict(Counter(evaluation.decision for evaluation in evaluations)),
        gate_status_counts=dict(Counter(evaluation.gate_status for evaluation in evaluations)),
        gate_name_counts=dict(Counter(evaluation.gate_name for evaluation in evaluations)),
        recommendation_counts=dict(Counter(plan.recommended_next_safe_action for plan in plans)),
        boundary=dict(READ_ONLY_BOUNDARY),
    )


def plan_to_dict(plan: CandidateInitialGatePlan) -> dict[str, Any]:
    return {
        "candidate_id": plan.candidate_id,
        "company_key": plan.company_key,
        "company_name": plan.company_name,
        "candidate_url": plan.candidate_url,
        "evaluations": [asdict(evaluation) for evaluation in plan.evaluations],
        "recommended_next_safe_action": plan.recommended_next_safe_action,
        "recommendation_reason": plan.recommendation_reason,
        "applied": plan.applied,
    }


def report_payload(*, benchmark_label: str, plans: Sequence[CandidateInitialGatePlan]) -> dict[str, Any]:
    summary = summarize_plans(plans)
    return {
        "benchmark_label": benchmark_label,
        "campaign": "GATE-001 Initial Gate Review Foundation",
        "summary": asdict(summary),
        "plans": [plan_to_dict(plan) for plan in plans],
        "decision_questions": [
            "Can persisted candidate_url state pass source_discovery, technical reachability and risk gates?",
            "Which candidates can move to bounded detail evidence discovery?",
            "Which initial gate failures are recoverable URL/runtime issues versus safety risks?",
        ],
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GATE-001 Initial Gate Review Foundation",
        "",
        f"Benchmark label: `{payload['benchmark_label']}`",
        "",
        "## Boundary",
        "",
        "This report is an SZ2 evidence/gate transition plan. It does not write candidate URLs, connectors, sources, Bronze/Silver data or scheduler state. Gate writes require explicit apply mode.",
        "",
        "## Summary",
        "",
        f"- Candidates: {summary['candidate_count']}",
        f"- Gate evaluations: {summary['evaluation_count']}",
        f"- Write recommended: {summary['write_recommended_count']}",
        f"- Applied: {summary['applied_count']}",
        f"- Passed: {summary['passed_count']}",
        f"- Manual review required: {summary['manual_review_required_count']}",
        f"- Deferred: {summary['deferred_count']}",
        "",
        "## Candidate Plans",
        "",
        "| Company | Candidate URL | Gate | Status | Decision | Next Safe Action | Review |",
        "|---|---|---|---|---|---|---|",
    ]
    for plan in payload["plans"]:
        for evaluation in plan["evaluations"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(plan["company_key"]),
                        str(plan.get("candidate_url") or "<none>"),
                        str(evaluation["gate_name"]),
                        str(evaluation["gate_status"]),
                        str(evaluation["decision"]),
                        str(plan["recommended_next_safe_action"]),
                        "yes" if evaluation["manual_review_required"] else "no",
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Recommendation Counts", "", "| Recommendation | Count |", "|---|---:|"])
    for recommendation, count in summary["recommendation_counts"].items():
        lines.append(f"| {recommendation} | {count} |")
    lines.extend(["", "## Gate Status Counts", "", "| Status | Count |", "|---|---:|"])
    for status, count in summary["gate_status_counts"].items():
        lines.append(f"| {status} | {count} |")
    return "\n".join(lines).rstrip() + "\n"
