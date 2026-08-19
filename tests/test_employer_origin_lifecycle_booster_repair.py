from __future__ import annotations

from scripts.run_employer_origin_lifecycle_booster_repair import (
    LISTING_GAP_REASON,
    detail_gap_eligible,
    detail_outcome_from_booster,
    listing_gap_eligible,
)


def early_gates() -> dict[str, dict[str, object]]:
    return {
        name: {"gate_status": "passed", "decision": "passed", "evidence": {}}
        for name in (
            "company_candidate",
            "source_discovery",
            "risk_gate",
            "technical_reachability_gate",
            "scope_gate",
            "defensive_preview_gate",
            "relevance_gate",
        )
    }


def test_listing_booster_is_only_eligible_for_exact_preview_gap_after_safety() -> None:
    gates = early_gates()
    gates["defensive_preview_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "stop_reason": LISTING_GAP_REASON,
        "evidence": {},
    }

    assert listing_gap_eligible(gates) is True

    gates["risk_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "evidence": {},
    }
    assert listing_gap_eligible(gates) is False


def test_listing_booster_does_not_reclassify_other_manual_preview_reasons() -> None:
    gates = early_gates()
    gates["defensive_preview_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "stop_reason": "operator identity review required",
        "evidence": {},
    }

    assert listing_gap_eligible(gates) is False


def test_detail_booster_requires_all_early_gates_and_never_overrides_failed_detail() -> None:
    gates = early_gates()
    gates["detail_evidence_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "evidence": {},
    }
    assert detail_gap_eligible(gates) is True

    gates["relevance_gate"] = {
        "gate_status": "manual_review_required",
        "decision": "manual_review_required",
        "evidence": {},
    }
    assert detail_gap_eligible(gates) is False

    gates = early_gates()
    gates["detail_evidence_gate"] = {
        "gate_status": "failed",
        "decision": "abort_documented",
        "evidence": {},
    }
    assert detail_gap_eligible(gates) is False


def test_deterministically_validated_booster_detail_can_form_canonical_pass() -> None:
    payload = {
        "execution": {
            "gap_fingerprint": "a" * 64,
            "resolved_url": "https://example.test/jobs/data-engineer-hannover",
            "resolved_validation": {
                "candidate_url": "https://example.test/jobs/data-engineer-hannover",
                "accepted": True,
                "final_url": "https://example.test/jobs/data-engineer-hannover",
                "classification": "accepted_concrete_detail",
                "evidence": {
                    "status_code": 200,
                    "title": "Data Engineer Hannover",
                    "profile_terms": ["data", "engineer"],
                    "location_terms": ["hannover"],
                },
            },
            "provider_requests": 1,
            "llm_requests": 1,
            "estimated_model_cost_usd": 0.01,
            "stages": [
                {
                    "stage": "luna_medium",
                    "resolved_url": "https://example.test/jobs/data-engineer-hannover",
                }
            ],
        }
    }

    outcome = detail_outcome_from_booster(payload)

    assert outcome is not None
    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert len(outcome.details) == 1
    assert outcome.details[0].location_terms == ("hannover",)
    assert outcome.evidence["provider_output_authority"] is False
    assert outcome.evidence["canonical_detail_validation"] is True
    assert outcome.evidence["supported_detail_evidence"][0]["final_url"].endswith(
        "/jobs/data-engineer-hannover"
    )


def test_unvalidated_or_targetless_model_output_cannot_form_detail_pass() -> None:
    base = {
        "execution": {
            "resolved_url": "https://example.test/jobs/data-engineer",
            "resolved_validation": {
                "candidate_url": "https://example.test/jobs/data-engineer",
                "accepted": False,
                "evidence": {
                    "profile_terms": ["data"],
                    "location_terms": ["hannover"],
                },
            },
        }
    }
    assert detail_outcome_from_booster(base) is None

    base["execution"]["resolved_validation"]["accepted"] = True
    base["execution"]["resolved_validation"]["evidence"]["location_terms"] = []
    assert detail_outcome_from_booster(base) is None
