from __future__ import annotations

from scripts.run_employer_origin_agent_chain import (
    CONNECTOR_CANDIDATE_GATE,
    DETAIL_EVIDENCE_GATE,
    EARLY_CONNECTOR_PRECONDITION_GATES,
    INCREMENTAL_UNIQUENESS_GATE,
    GateReview,
    connector_candidate_ready,
    next_decision,
)
from scripts.run_employer_origin_preconnector_precondition_agent import (
    supported_detail_candidates_from_evidence,
)


def gate(name: str, status: str, decision: str, evidence: dict | None = None) -> GateReview:
    return GateReview(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=None,
        evidence=evidence or {},
    )


def canonical_preconditions(*, uniqueness_status: str = "passed") -> dict[str, GateReview]:
    gates = {
        name: gate(name, "passed", "passed")
        for name in EARLY_CONNECTOR_PRECONDITION_GATES
    }
    gates[DETAIL_EVIDENCE_GATE] = gate(DETAIL_EVIDENCE_GATE, "passed", "passed")
    gates[INCREMENTAL_UNIQUENESS_GATE] = gate(
        INCREMENTAL_UNIQUENESS_GATE,
        uniqueness_status,
        "passed" if uniqueness_status == "passed" else "defer",
    )
    return gates


def next_action(gates: dict[str, GateReview]) -> str:
    return next_decision(
        gates,
        company_key="example_employer",
        target_location="hannover",
        reviewed_by="test",
        attempt_repair=True,
        write_connector=False,
    ).action


def test_chain_recovers_present_neutral_early_gate_before_detail_or_connector() -> None:
    gates = canonical_preconditions()
    gates["technical_reachability_gate"] = gate(
        "technical_reachability_gate", "not_started", "defer"
    )

    assert next_action(gates) == "run_preconnector_precondition_recovery"


def test_chain_recovers_uniqueness_after_passed_detail_before_connector() -> None:
    gates = canonical_preconditions(uniqueness_status="not_started")

    assert next_action(gates) == "run_preconnector_precondition_recovery"


def test_chain_routes_connector_only_when_canonical_preconditions_are_passed() -> None:
    gates = canonical_preconditions()

    assert next_action(gates) == "run_connector_candidate_gate"


def test_connector_candidate_ready_accepts_canonical_passed_decision() -> None:
    assert connector_candidate_ready(
        {CONNECTOR_CANDIDATE_GATE: gate(CONNECTOR_CANDIDATE_GATE, "passed", "passed")}
    )
    # Historical action-like evidence remains readable during migration.
    assert connector_candidate_ready(
        {
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            )
        }
    )


def test_supported_detail_candidates_reuse_only_authoritative_passed_evidence() -> None:
    candidates = supported_detail_candidates_from_evidence(
        {
            "gate_status": "passed",
            "evidence": {
                "preliminary_detail_candidates": [
                    {"url": "https://jobs.example.com/jobs/overview"}
                ],
                "supported_detail_evidence": [
                    {
                        "url": "https://jobs.example.com/jobs/data-engineer-123",
                        "final_url": "https://jobs.example.com/jobs/data-engineer-123",
                        "status_code": 200,
                        "title": "Data Engineer",
                        "profile_terms": ["data", "python"],
                        "location_terms": ["hannover"],
                        "html_bytes": 1234,
                    }
                ],
            },
        }
    )

    assert [item.url for item in candidates] == [
        "https://jobs.example.com/jobs/data-engineer-123"
    ]
    assert candidates[0].profile_hits == ("data", "python")
    assert candidates[0].location_hits == ("hannover",)


def test_supported_detail_candidates_refuse_nonpassed_detail_gate() -> None:
    assert supported_detail_candidates_from_evidence(
        {
            "gate_status": "manual_review_required",
            "evidence": {
                "supported_detail_evidence": [
                    {
                        "url": "https://jobs.example.com/jobs/data-engineer-123",
                        "profile_terms": ["data"],
                        "location_terms": ["hannover"],
                    }
                ]
            },
        }
    ) == []
