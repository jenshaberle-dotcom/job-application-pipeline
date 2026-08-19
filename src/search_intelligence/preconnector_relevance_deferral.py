from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

REQUIRED_PREDECESSOR_GATES = (
    "company_candidate",
    "source_discovery",
    "risk_gate",
    "technical_reachability_gate",
    "scope_gate",
    "defensive_preview_gate",
)

TARGET_SIGNAL_MISSING_REASON = "bounded preview did not expose target-location or remote evidence"


@dataclass(frozen=True)
class RelevanceDeferralDecision:
    eligible: bool
    reason_code: str
    evidence: dict[str, Any]


def _gate_passed(gates: Mapping[str, Mapping[str, Any]], name: str) -> bool:
    row = gates.get(name)
    return bool(row and row.get("gate_status") == "passed")


def evaluate_relevance_deferral(
    gates: Mapping[str, Mapping[str, Any]],
) -> RelevanceDeferralDecision:
    missing_predecessors = [
        name for name in REQUIRED_PREDECESSOR_GATES if not _gate_passed(gates, name)
    ]
    relevance = gates.get("relevance_gate") or {}
    defensive = gates.get("defensive_preview_gate") or {}
    detail = gates.get("detail_evidence_gate") or {}
    relevance_evidence = relevance.get("evidence")
    if not isinstance(relevance_evidence, Mapping):
        relevance_evidence = {}
    defensive_evidence = defensive.get("evidence")
    if not isinstance(defensive_evidence, Mapping):
        defensive_evidence = {}

    profile_hits = tuple(str(value) for value in (relevance_evidence.get("profile_hits") or ()) if str(value))
    location_hits = tuple(str(value) for value in (relevance_evidence.get("location_hits") or ()) if str(value))
    remote_hits = tuple(str(value) for value in (relevance_evidence.get("remote_hits") or ()) if str(value))
    sample_links = tuple(str(value) for value in (defensive_evidence.get("sample_links") or ()) if str(value))
    job_link_count = int(defensive_evidence.get("same_domain_job_link_count") or len(sample_links) or 0)

    base_evidence = {
        "missing_predecessor_gates": missing_predecessors,
        "profile_hits": list(profile_hits),
        "location_hits": list(location_hits),
        "remote_hits": list(remote_hits),
        "job_like_link_count": job_link_count,
        "detail_gate_status": detail.get("gate_status"),
        "provider_requests": 0,
        "llm_requests": 0,
        "product_authority": False,
    }

    if missing_predecessors:
        return RelevanceDeferralDecision(False, "predecessor_gate_not_passed", base_evidence)
    if relevance.get("gate_status") == "passed":
        return RelevanceDeferralDecision(False, "relevance_already_passed", base_evidence)
    if relevance.get("gate_status") != "manual_review_required":
        return RelevanceDeferralDecision(False, "relevance_not_manual_review", base_evidence)
    if relevance.get("stop_reason") != TARGET_SIGNAL_MISSING_REASON:
        return RelevanceDeferralDecision(False, "relevance_stop_reason_not_target_signal_gap", base_evidence)
    if not profile_hits:
        return RelevanceDeferralDecision(False, "profile_evidence_missing", base_evidence)
    if location_hits or remote_hits:
        return RelevanceDeferralDecision(False, "target_signal_already_present", base_evidence)
    if job_link_count <= 0:
        return RelevanceDeferralDecision(False, "job_listing_evidence_missing", base_evidence)
    if detail.get("gate_status") == "passed":
        return RelevanceDeferralDecision(False, "detail_evidence_already_passed", base_evidence)

    return RelevanceDeferralDecision(
        True,
        "target_relevance_deferred_to_detail_evidence",
        {
            **base_evidence,
            "target_relevance_deferred_to_detail_evidence": True,
            "deferred_requirement": (
                "A concrete job detail must still prove target-location or remote evidence "
                "before connector candidacy can pass."
            ),
            "quality_boundary_lowered": False,
        },
    )


__all__ = [
    "REQUIRED_PREDECESSOR_GATES",
    "RelevanceDeferralDecision",
    "TARGET_SIGNAL_MISSING_REASON",
    "evaluate_relevance_deferral",
]
