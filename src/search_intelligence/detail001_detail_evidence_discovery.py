"""DETAIL-001 Detail Evidence Discovery Foundation.

This module models the SZ2 transition after CAND-001 and GATE-001: persisted
origin URLs with passed early gates need bounded job/detail evidence before the
connector-candidate chain can continue.  The module is deliberately pure Python:
it evaluates prepared probe results and produces a write plan/report, while the
runner owns HTTP and database boundaries.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

CAMPAIGN = "DETAIL-001 Detail Evidence Discovery Foundation"
DETAIL_EVIDENCE_GATE = "detail_evidence_gate"
EARLY_GATE_SEQUENCE = (
    "source_discovery",
    "technical_reachability_gate",
    "risk_gate",
)
MISSING_URL_MARKERS = {"", "none", "null", "<empty>"}

BOUNDARY: dict[str, bool] = {
    "sz2_evidence_and_gates": True,
    "dry_run_first": True,
    "explicit_apply_required": True,
    "bounded_http_only": True,
    "no_raw_html_persistence": True,
    "no_candidate_url_write": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_scheduler_change": True,
    "no_bronze_silver_write": True,
}


@dataclass(frozen=True)
class CandidateDetailEvidenceSnapshot:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None


@dataclass(frozen=True)
class GateSnapshot:
    gate_name: str
    gate_status: str
    decision: str | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class DetailProbeEvidence:
    url: str
    final_url: str | None
    status_code: int | None
    title: str | None
    response_bytes: int
    profile_hits: tuple[str, ...]
    location_hits: tuple[str, ...]
    remote_hits: tuple[str, ...]
    flexibility_hits: tuple[str, ...] = ()
    source_url: str | None = None
    reason: str | None = None

    @property
    def reachable(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 400

    @property
    def has_profile_evidence(self) -> bool:
        return bool(self.profile_hits)

    @property
    def has_target_or_remote_evidence(self) -> bool:
        return bool(self.location_hits or self.remote_hits)

    @property
    def supported(self) -> bool:
        return self.reachable and self.has_profile_evidence and self.has_target_or_remote_evidence


@dataclass(frozen=True)
class DetailEvidencePlan:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_status: str
    candidate_url: str | None
    gate_name: str
    gate_order: int
    gate_status: str
    decision: str
    stop_reason: str | None
    evidence: dict[str, Any]
    apply_allowed: bool
    manual_review_required: bool
    recommended_next_safe_action: str
    recommendation_reason: str
    safety_zone: str = "SZ2_EVIDENCE_AND_GATES"
    applied: bool = False
    gate_review_id: int | None = None
    written_detail_evidence_count: int = 0


@dataclass(frozen=True)
class DetailEvidenceSummary:
    candidate_count: int
    applied_count: int
    write_recommended_count: int
    passed_count: int
    manual_review_required_count: int
    deferred_count: int
    supported_detail_evidence_count: int
    detail_candidate_count: int
    requested_url_count: int
    decision_counts: dict[str, int]
    gate_status_counts: dict[str, int]
    recommendation_counts: dict[str, int]
    boundary: dict[str, bool]


def normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if stripped.lower() in MISSING_URL_MARKERS:
        return None
    return stripped


def gate_is_passed(gate: GateSnapshot | None) -> bool:
    return bool(gate and gate.gate_status == "passed")


def gates_by_name(gates: Sequence[GateSnapshot]) -> dict[str, GateSnapshot]:
    return {gate.gate_name: gate for gate in gates}


def first_missing_early_gate(gates: Sequence[GateSnapshot]) -> str | None:
    lookup = gates_by_name(gates)
    for gate_name in EARLY_GATE_SEQUENCE:
        if not gate_is_passed(lookup.get(gate_name)):
            return gate_name
    return None


def early_gates_ready(gates: Sequence[GateSnapshot]) -> bool:
    return first_missing_early_gate(gates) is None


def host_and_pattern(url: str | None) -> dict[str, str | None]:
    parsed = urlparse(str(url or ""))
    path = parsed.path or ""
    path_pattern: str | None = None
    for marker in ("/job/", "/jobs/", "/stellen/", "/stellenangebote/", "/vacancy/", "/vacancies/"):
        if marker in path.lower():
            path_pattern = marker.rstrip("/") + "/..."
            break
    return {"host": parsed.netloc.lower() or None, "path_pattern": path_pattern}


def discovery_was_attempted(
    *,
    requested_urls: Sequence[str],
    rejected_urls: Sequence[str],
    discovery_evidence: Mapping[str, Any] | None,
) -> bool:
    """Return whether bounded discovery/probing actually ran.

    A DETAIL-001 run can execute bounded seed/list probing and still discover no
    concrete job-detail candidates.  That is a real auditable gate stop, not a
    missing execution.  Only a deliberately unprobed plan, for example via
    ``--no-probe``, should remain deferred as ``not_executed``.
    """

    if requested_urls or rejected_urls:
        return True
    repair_evidence = dict(discovery_evidence or {}).get("repair_agent_evidence")
    if isinstance(repair_evidence, Mapping):
        return bool(repair_evidence.get("repair_attempted"))
    return False


def _probe_to_dict(probe: DetailProbeEvidence) -> dict[str, Any]:
    pattern = host_and_pattern(probe.final_url or probe.url)
    return {
        "url": probe.url,
        "final_url": probe.final_url,
        "source_url": probe.source_url,
        "status_code": probe.status_code,
        "title": probe.title,
        "response_bytes": probe.response_bytes,
        "profile_hits": list(probe.profile_hits),
        "location_hits": list(probe.location_hits),
        "remote_hits": list(probe.remote_hits),
        "flexibility_hits": list(probe.flexibility_hits),
        "supported": probe.supported,
        "reason": probe.reason,
        "evidence_host": pattern["host"],
        "path_pattern": pattern["path_pattern"],
        "raw_html_persisted": False,
    }


def _base_evidence(
    candidate: CandidateDetailEvidenceSnapshot,
    *,
    reviewed_by: str,
    requested_urls: Sequence[str],
    rejected_urls: Sequence[str],
    discovery_evidence: Mapping[str, Any] | None,
    detail_candidate_count: int,
    probes: Sequence[DetailProbeEvidence],
) -> dict[str, Any]:
    supported = [probe for probe in probes if probe.supported]
    return {
        "campaign": CAMPAIGN,
        "company_key": candidate.company_key,
        "candidate_url": normalize_url(candidate.candidate_url),
        "reviewed_by": reviewed_by,
        "boundary": dict(BOUNDARY),
        "detail_candidates_considered": detail_candidate_count,
        "detail_pages_requested": len(probes),
        "supported_detail_candidates": len(supported),
        "requested_urls": list(requested_urls),
        "rejected_urls": list(rejected_urls),
        "details": [_probe_to_dict(probe) for probe in probes],
        "supported_details": [_probe_to_dict(probe) for probe in supported],
        "discovery_evidence": dict(discovery_evidence or {}),
    }


def _plan(
    candidate: CandidateDetailEvidenceSnapshot,
    *,
    gate_status: str,
    decision: str,
    stop_reason: str | None,
    evidence: dict[str, Any],
    apply_allowed: bool,
    manual_review_required: bool,
    recommended_next_safe_action: str,
    recommendation_reason: str,
    applied: bool = False,
    gate_review_id: int | None = None,
    written_detail_evidence_count: int = 0,
) -> DetailEvidencePlan:
    return DetailEvidencePlan(
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        candidate_status=candidate.status,
        candidate_url=normalize_url(candidate.candidate_url),
        gate_name=DETAIL_EVIDENCE_GATE,
        gate_order=8,
        gate_status=gate_status,
        decision=decision,
        stop_reason=stop_reason,
        evidence=evidence,
        apply_allowed=apply_allowed,
        manual_review_required=manual_review_required,
        recommended_next_safe_action=recommended_next_safe_action,
        recommendation_reason=recommendation_reason,
        applied=applied,
        gate_review_id=gate_review_id,
        written_detail_evidence_count=written_detail_evidence_count,
    )


def build_detail_evidence_plan(
    candidate: CandidateDetailEvidenceSnapshot,
    gates: Sequence[GateSnapshot],
    probes: Sequence[DetailProbeEvidence],
    *,
    reviewed_by: str,
    requested_urls: Sequence[str] = (),
    rejected_urls: Sequence[str] = (),
    discovery_evidence: Mapping[str, Any] | None = None,
    detail_candidate_count: int | None = None,
    applied: bool = False,
    gate_review_id: int | None = None,
    written_detail_evidence_count: int = 0,
) -> DetailEvidencePlan:
    """Build a DETAIL-001 gate/evidence write plan for one candidate."""

    candidate_url = normalize_url(candidate.candidate_url)
    candidate_count = len(probes) if detail_candidate_count is None else max(detail_candidate_count, len(probes))
    evidence = _base_evidence(
        candidate,
        reviewed_by=reviewed_by,
        requested_urls=requested_urls,
        rejected_urls=rejected_urls,
        discovery_evidence=discovery_evidence,
        detail_candidate_count=candidate_count,
        probes=probes,
    )

    if not candidate_url:
        evidence |= {"decision_taxonomy": "missing_candidate_url", "confidence_score": 0.0}
        return _plan(
            candidate,
            gate_status="deferred",
            decision="defer",
            stop_reason="candidate_url is missing; CAND-001 must persist a validated origin URL first",
            evidence=evidence,
            apply_allowed=False,
            manual_review_required=False,
            recommended_next_safe_action="run_origin_url_finder_validation",
            recommendation_reason="Detail evidence discovery requires a persisted origin URL from SZ1.",
            applied=applied,
            gate_review_id=gate_review_id,
            written_detail_evidence_count=written_detail_evidence_count,
        )

    missing_gate = first_missing_early_gate(gates)
    if missing_gate:
        evidence |= {
            "decision_taxonomy": "initial_gate_not_ready",
            "first_missing_early_gate": missing_gate,
            "confidence_score": 0.0,
        }
        return _plan(
            candidate,
            gate_status="deferred",
            decision="defer",
            stop_reason=f"early gate {missing_gate!r} is not passed; detail evidence discovery is blocked",
            evidence=evidence,
            apply_allowed=False,
            manual_review_required=False,
            recommended_next_safe_action="run_initial_gate_review_plan",
            recommendation_reason="Source discovery, technical reachability and risk gates must pass before detail evidence writes.",
            applied=applied,
            gate_review_id=gate_review_id,
            written_detail_evidence_count=written_detail_evidence_count,
        )

    attempted = discovery_was_attempted(
        requested_urls=requested_urls,
        rejected_urls=rejected_urls,
        discovery_evidence=discovery_evidence,
    )
    evidence |= {"bounded_discovery_attempted": attempted}

    if not probes and candidate_count == 0 and not attempted:
        evidence |= {
            "decision_taxonomy": "not_executed",
            "confidence_score": 0.0,
            "confidence_reason": "no bounded detail probe was executed",
        }
        return _plan(
            candidate,
            gate_status="deferred",
            decision="defer",
            stop_reason="bounded detail evidence probe was not executed",
            evidence=evidence,
            apply_allowed=False,
            manual_review_required=False,
            recommended_next_safe_action="run_detail_evidence_discovery_plan",
            recommendation_reason="Run DETAIL-001 with bounded probing before applying gate state.",
            applied=applied,
            gate_review_id=gate_review_id,
            written_detail_evidence_count=written_detail_evidence_count,
        )

    supported = [probe for probe in probes if probe.supported]
    if supported:
        evidence |= {
            "decision_taxonomy": "accepted",
            "confidence_score": 0.96,
            "confidence_reason": "validated detail page contains profile and target-location/remote evidence",
        }
        return _plan(
            candidate,
            gate_status="passed",
            decision="passed",
            stop_reason=None,
            evidence=evidence,
            apply_allowed=True,
            manual_review_required=False,
            recommended_next_safe_action="run_connector_candidate_chain_plan",
            recommendation_reason="Detail evidence is available; connector-candidate evaluation can continue in plan/apply-controlled mode.",
            applied=applied,
            gate_review_id=gate_review_id,
            written_detail_evidence_count=written_detail_evidence_count,
        )

    if candidate_count > 0:
        taxonomy = "implementation_gap"
        confidence_score = 0.82
        confidence_reason = "concrete job-detail candidates were found, but none validated both profile and target-location/remote evidence"
        stop_reason = "bounded detail discovery found candidate detail pages but no validated profile plus target-location/remote evidence"
    else:
        taxonomy = "manual_review_required"
        confidence_score = 0.58
        confidence_reason = "no concrete job-detail candidates found within the bounded discovery budget"
        stop_reason = "bounded detail discovery found no concrete detail pages with profile and target-location/remote evidence"

    evidence |= {
        "decision_taxonomy": taxonomy,
        "confidence_score": confidence_score,
        "confidence_reason": confidence_reason,
    }
    return _plan(
        candidate,
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason=stop_reason,
        evidence=evidence,
        apply_allowed=True,
        manual_review_required=True,
        recommended_next_safe_action="manual_review_detail_evidence_discovery",
        recommendation_reason="The gate stop is now explicit and auditable; do not weaken promotion/gate thresholds without reviewing the evidence.",
        applied=applied,
        gate_review_id=gate_review_id,
        written_detail_evidence_count=written_detail_evidence_count,
    )


def summarize_plans(plans: Sequence[DetailEvidencePlan]) -> DetailEvidenceSummary:
    return DetailEvidenceSummary(
        candidate_count=len(plans),
        applied_count=sum(1 for plan in plans if plan.applied),
        write_recommended_count=sum(1 for plan in plans if plan.apply_allowed),
        passed_count=sum(1 for plan in plans if plan.gate_status == "passed"),
        manual_review_required_count=sum(1 for plan in plans if plan.manual_review_required),
        deferred_count=sum(1 for plan in plans if plan.gate_status == "deferred"),
        supported_detail_evidence_count=sum(int(plan.evidence.get("supported_detail_candidates", 0)) for plan in plans),
        detail_candidate_count=sum(int(plan.evidence.get("detail_candidates_considered", 0)) for plan in plans),
        requested_url_count=sum(len(plan.evidence.get("requested_urls", [])) for plan in plans),
        decision_counts=dict(sorted(Counter(plan.decision for plan in plans).items())),
        gate_status_counts=dict(sorted(Counter(plan.gate_status for plan in plans).items())),
        recommendation_counts=dict(sorted(Counter(plan.recommended_next_safe_action for plan in plans).items())),
        boundary=dict(BOUNDARY),
    )


def plan_to_dict(plan: DetailEvidencePlan) -> dict[str, Any]:
    return asdict(plan)


def report_payload(*, benchmark_label: str, plans: Sequence[DetailEvidencePlan]) -> dict[str, Any]:
    summary = summarize_plans(plans)
    return {
        "benchmark_label": benchmark_label,
        "campaign": CAMPAIGN,
        "summary": asdict(summary),
        "plans": [plan_to_dict(plan) for plan in plans],
        "decision_questions": [
            "Which persisted origin URLs have concrete job/detail evidence with profile and target-location/remote signals?",
            "Which candidates can move from detail_evidence_gate to connector-candidate evaluation?",
            "Which candidates need manual review because discovery found no detail pages or only weak/unvalidated detail candidates?",
        ],
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# DETAIL-001 Detail Evidence Discovery Foundation",
        "",
        f"Benchmark label: `{payload['benchmark_label']}`",
        "",
        "## Boundary",
        "",
        "This report is an SZ2 evidence/gate transition plan. It may write detail evidence and `detail_evidence_gate` only in explicit apply mode. It does not write candidate URLs, connectors, sources, Bronze/Silver data or scheduler state, and it never persists raw HTML.",
        "",
        "## Summary",
        "",
        f"- Candidates: {summary['candidate_count']}",
        f"- Write recommended: {summary['write_recommended_count']}",
        f"- Applied: {summary['applied_count']}",
        f"- Passed: {summary['passed_count']}",
        f"- Manual review required: {summary['manual_review_required_count']}",
        f"- Deferred: {summary['deferred_count']}",
        f"- Detail candidates considered: {summary['detail_candidate_count']}",
        f"- Supported detail evidence: {summary['supported_detail_evidence_count']}",
        f"- Requested URLs: {summary['requested_url_count']}",
        "",
        "## Candidate Plans",
        "",
        "| Company | Candidate URL | Gate Status | Decision | Detail Candidates | Supported | Next Safe Action | Apply |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for plan in payload["plans"]:
        evidence = plan.get("evidence") or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    str(plan["company_key"]),
                    str(plan.get("candidate_url") or "<none>"),
                    str(plan["gate_status"]),
                    str(plan["decision"]),
                    str(evidence.get("detail_candidates_considered", 0)),
                    str(evidence.get("supported_detail_candidates", 0)),
                    str(plan["recommended_next_safe_action"]),
                    "yes" if plan.get("apply_allowed") else "no",
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
    lines.extend([
        "",
        "## Notes",
        "",
        "- Run dry-run first; use `--apply` only after reviewing requested URLs, rejected URLs and detail evidence.",
        "- A passed gate means at least one bounded detail page contained profile evidence and target-location or remote/Germany evidence.",
        "- Manual-review outcomes are still useful: they make the exact detail-evidence blocker visible instead of silently re-running earlier gates.",
    ])
    return "\n".join(lines).rstrip() + "\n"
