from __future__ import annotations

from scripts.run_employer_origin_next_safe_action_agent import (
    DETAIL_EVIDENCE_GATE,
    PersistedCandidate,
    PersistedGateReview,
    determine_next_safe_command,
)
from src.search_intelligence.employer_origin_gate_registry import OFFICIAL_EMPLOYER_ORIGIN_GATES


def persisted_candidate(**overrides: object) -> PersistedCandidate:
    data = dict(
        candidate_id=6,
        company_key="adesso",
        company_name="adesso SE",
        candidate_url="https://www.adesso.de/de/karriere/jobs/index.html",
        source_name_candidate="adesso:discovery",
        source_family_candidate="adesso",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
    )
    data.update(overrides)
    return PersistedCandidate(**data)


def gate(
    gate_name: str,
    *,
    gate_status: str = "passed",
    decision: str = "passed",
    stop_reason: str | None = None,
) -> PersistedGateReview:
    return PersistedGateReview(
        gate_name=gate_name,
        gate_status=gate_status,
        decision=decision,
        stop_reason=stop_reason,
    )


def early_passed_gates() -> dict[str, PersistedGateReview]:
    return {
        item.gate_name: gate(item.gate_name)
        for item in OFFICIAL_EMPLOYER_ORIGIN_GATES
        if item.gate_order <= 7
    }


def test_next_safe_command_stops_on_terminal_early_gate_for_disallowed_auth_url() -> None:
    gates = {
        "company_candidate": gate("company_candidate"),
        "source_discovery": gate(
            "source_discovery",
            gate_status="failed",
            decision="abort_documented",
            stop_reason="candidate URL appears to require authentication",
        ),
    }

    command = determine_next_safe_command(
        persisted_candidate(
            status="abort_documented",
            candidate_url="https://example.com/login/jobs",
        ),
        gates,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert command.action == "no_safe_automated_action"
    assert command.module is None
    assert "source_discovery stopped with abort_documented" in command.reason
    assert "rerunning the same automated step" in command.reason


def test_next_safe_command_runs_initial_gate_before_premature_detail_repair() -> None:
    gates = {
        DETAIL_EVIDENCE_GATE: gate(
            DETAIL_EVIDENCE_GATE,
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="premature repair",
        )
    }

    command = determine_next_safe_command(
        persisted_candidate(),
        gates,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert command.action == "run_initial_gate_review"
    assert command.module == "scripts.run_employer_origin_gate_agent"


def test_next_safe_command_stops_terminal_detail_gate_after_early_gates_passed() -> None:
    gates = early_passed_gates()
    gates[DETAIL_EVIDENCE_GATE] = gate(
        DETAIL_EVIDENCE_GATE,
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="bounded repair found no concrete detail pages",
    )

    command = determine_next_safe_command(
        persisted_candidate(),
        gates,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert command.action == "no_safe_automated_action"
    assert command.module is None
    assert "detail_evidence_gate stopped with manual_review_required" in command.reason


def test_recoverable_source_discovery_abort_reruns_initial_gate_review() -> None:
    from scripts.run_employer_origin_next_safe_action_agent import (
        PersistedCandidate,
        PersistedGateReview,
        determine_next_safe_command,
    )

    candidate = PersistedCandidate(
        candidate_id=6,
        company_key="adesso",
        company_name="adesso SE",
        candidate_url="https://www.adesso.de/de/karriere/jobs/index.html",
        source_name_candidate="adesso:discovery",
        source_family_candidate="adesso",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="abort_documented",
    )
    gates = {
        "company_candidate": PersistedGateReview("company_candidate", "passed", "passed", None),
        "source_discovery": PersistedGateReview(
            "source_discovery",
            "failed",
            "abort_documented",
            "candidate URL appears to require authentication",
        ),
    }

    command = determine_next_safe_command(
        candidate,
        gates,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert command.action == "run_initial_gate_review"
    assert command.module == "scripts.run_employer_origin_gate_agent"
    assert "now passes" in command.reason


def test_technical_reachability_404_runs_source_url_recovery() -> None:
    gates = {
        "company_candidate": gate("company_candidate"),
        "source_discovery": gate("source_discovery"),
        "risk_gate": gate("risk_gate"),
        "technical_reachability_gate": gate(
            "technical_reachability_gate",
            gate_status="failed",
            decision="abort_documented",
            stop_reason="source returned HTTP 404",
        ),
    }

    command = determine_next_safe_command(
        persisted_candidate(status="abort_documented"),
        gates,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert command.action == "run_source_url_recovery"
    assert command.module == "scripts.run_employer_origin_source_url_recovery_agent"
    assert "--run-gate-review-after-recovery" in command.args


def test_relevance_gate_preview_stop_runs_relevance_evidence_probe() -> None:
    gates = {
        "company_candidate": gate("company_candidate"),
        "source_discovery": gate("source_discovery"),
        "risk_gate": gate("risk_gate"),
        "technical_reachability_gate": gate("technical_reachability_gate"),
        "scope_gate": gate("scope_gate"),
        "defensive_preview_gate": gate("defensive_preview_gate"),
        "relevance_gate": gate(
            "relevance_gate",
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="bounded preview did not expose target-location or remote evidence",
        ),
    }

    command = determine_next_safe_command(
        persisted_candidate(candidate_url="https://jobs.adesso-group.com/", status="manual_review_required"),
        gates,
        target_location="hannover",
        reviewed_by="jens",
    )

    assert command.action == "run_autonomous_relevance_discovery"
    assert command.module == "scripts.run_employer_origin_autonomous_relevance_discovery_agent"
