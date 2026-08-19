from __future__ import annotations

from src.search_intelligence.preconnector_relevance_deferral import (
    TARGET_SIGNAL_MISSING_REASON,
    evaluate_relevance_deferral,
)


def base_gates() -> dict[str, dict[str, object]]:
    gates = {
        name: {"gate_status": "passed", "decision": "passed", "evidence": {}}
        for name in (
            "company_candidate",
            "source_discovery",
            "risk_gate",
            "technical_reachability_gate",
            "scope_gate",
        )
    }
    gates["defensive_preview_gate"] = {
        "gate_status": "passed",
        "decision": "passed",
        "evidence": {
            "same_domain_job_link_count": 3,
            "sample_links": ["https://example.test/jobs/data-engineer"],
        },
    }
    gates["relevance_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "stop_reason": TARGET_SIGNAL_MISSING_REASON,
        "evidence": {
            "profile_hits": ["data", "engineer"],
            "location_hits": [],
            "remote_hits": [],
        },
    }
    gates["detail_evidence_gate"] = {
        "gate_status": "pending",
        "decision": "pending",
        "evidence": {},
    }
    return gates


def test_target_signal_can_be_deferred_only_after_safe_listing_relevance() -> None:
    decision = evaluate_relevance_deferral(base_gates())

    assert decision.eligible is True
    assert decision.reason_code == "target_relevance_deferred_to_detail_evidence"
    assert decision.evidence["target_relevance_deferred_to_detail_evidence"] is True
    assert decision.evidence["quality_boundary_lowered"] is False
    assert decision.evidence["provider_requests"] == 0


def test_deferral_does_not_bypass_unpassed_risk_gate() -> None:
    gates = base_gates()
    gates["risk_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "evidence": {},
    }

    decision = evaluate_relevance_deferral(gates)

    assert decision.eligible is False
    assert decision.reason_code == "predecessor_gate_not_passed"
    assert "risk_gate" in decision.evidence["missing_predecessor_gates"]


def test_deferral_requires_job_listing_evidence() -> None:
    gates = base_gates()
    gates["defensive_preview_gate"] = {
        "gate_status": "passed",
        "decision": "passed",
        "evidence": {"same_domain_job_link_count": 0, "sample_links": []},
    }

    decision = evaluate_relevance_deferral(gates)

    assert decision.eligible is False
    assert decision.reason_code == "job_listing_evidence_missing"


def test_profile_gap_is_not_reclassified_as_target_deferral() -> None:
    gates = base_gates()
    gates["relevance_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "stop_reason": "bounded preview did not expose profile-term evidence",
        "evidence": {"profile_hits": [], "location_hits": [], "remote_hits": []},
    }

    decision = evaluate_relevance_deferral(gates)

    assert decision.eligible is False
    assert decision.reason_code == "relevance_stop_reason_not_target_signal_gap"


def test_existing_target_signal_never_needs_deferral() -> None:
    gates = base_gates()
    gates["relevance_gate"]["evidence"] = {
        "profile_hits": ["data"],
        "location_hits": ["hannover"],
        "remote_hits": [],
    }

    decision = evaluate_relevance_deferral(gates)

    assert decision.eligible is False
    assert decision.reason_code == "target_signal_already_present"
