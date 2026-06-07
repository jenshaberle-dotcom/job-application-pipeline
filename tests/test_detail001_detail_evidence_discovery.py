from __future__ import annotations

from src.search_intelligence.detail001_detail_evidence_discovery import (
    CandidateDetailEvidenceSnapshot,
    DetailProbeEvidence,
    GateSnapshot,
    build_detail_evidence_plan,
    early_gates_ready,
    report_payload,
    render_markdown,
)


def candidate(url: str | None = "https://jobs.example.com/") -> CandidateDetailEvidenceSnapshot:
    return CandidateDetailEvidenceSnapshot(
        candidate_id=42,
        company_key="example_ag",
        company_name="Example AG",
        status="origin_url_validated",
        candidate_url=url,
    )


def passed_initial_gates() -> tuple[GateSnapshot, ...]:
    return (
        GateSnapshot("source_discovery", "passed", "passed"),
        GateSnapshot("technical_reachability_gate", "passed", "passed"),
        GateSnapshot("risk_gate", "passed", "passed"),
    )


def test_early_gates_ready_requires_all_three_initial_gates() -> None:
    assert early_gates_ready(passed_initial_gates()) is True
    assert early_gates_ready((GateSnapshot("source_discovery", "passed", "passed"),)) is False


def test_passes_when_supported_detail_page_has_profile_and_location_evidence() -> None:
    plan = build_detail_evidence_plan(
        candidate(),
        passed_initial_gates(),
        (
            DetailProbeEvidence(
                url="https://jobs.example.com/job/data-engineer-hannover",
                final_url="https://jobs.example.com/job/data-engineer-hannover",
                status_code=200,
                title="Data Engineer Hannover",
                response_bytes=2048,
                profile_hits=("data", "sql"),
                location_hits=("hannover",),
                remote_hits=(),
                reason="unit test",
            ),
        ),
        reviewed_by="pytest",
        requested_urls=("https://jobs.example.com/job/data-engineer-hannover",),
        detail_candidate_count=1,
    )

    assert plan.gate_status == "passed"
    assert plan.decision == "passed"
    assert plan.apply_allowed is True
    assert plan.manual_review_required is False
    assert plan.recommended_next_safe_action == "run_connector_candidate_chain_plan"
    assert plan.evidence["decision_taxonomy"] == "accepted"
    assert plan.evidence["supported_detail_candidates"] == 1
    assert plan.evidence["supported_details"][0]["raw_html_persisted"] is False


def test_missing_candidate_url_defers_to_url_finder_without_apply() -> None:
    plan = build_detail_evidence_plan(
        candidate(url=None),
        passed_initial_gates(),
        (),
        reviewed_by="pytest",
    )

    assert plan.gate_status == "deferred"
    assert plan.decision == "defer"
    assert plan.apply_allowed is False
    assert plan.recommended_next_safe_action == "run_origin_url_finder_validation"


def test_missing_initial_gate_blocks_detail_probe_transition() -> None:
    plan = build_detail_evidence_plan(
        candidate(),
        (GateSnapshot("source_discovery", "passed", "passed"),),
        (),
        reviewed_by="pytest",
    )

    assert plan.gate_status == "deferred"
    assert plan.apply_allowed is False
    assert plan.evidence["decision_taxonomy"] == "initial_gate_not_ready"
    assert plan.recommended_next_safe_action == "run_initial_gate_review_plan"


def test_detail_candidate_without_required_signals_becomes_auditable_manual_review() -> None:
    plan = build_detail_evidence_plan(
        candidate(),
        passed_initial_gates(),
        (
            DetailProbeEvidence(
                url="https://jobs.example.com/job/data-engineer",
                final_url="https://jobs.example.com/job/data-engineer",
                status_code=200,
                title="Data Engineer",
                response_bytes=1200,
                profile_hits=("data",),
                location_hits=(),
                remote_hits=(),
            ),
        ),
        reviewed_by="pytest",
        detail_candidate_count=1,
    )

    assert plan.gate_status == "manual_review_required"
    assert plan.decision == "manual_review_required"
    assert plan.apply_allowed is True
    assert plan.manual_review_required is True
    assert plan.evidence["decision_taxonomy"] == "implementation_gap"



def test_executed_discovery_without_detail_candidates_becomes_auditable_manual_review() -> None:
    plan = build_detail_evidence_plan(
        candidate(),
        passed_initial_gates(),
        (),
        reviewed_by="pytest",
        requested_urls=("https://jobs.example.com/",),
        rejected_urls=("https://jobs.example.com/ :: job_list_found_but_no_detail_links",),
        discovery_evidence={"repair_agent_evidence": {"repair_attempted": True}},
        detail_candidate_count=0,
    )

    assert plan.gate_status == "manual_review_required"
    assert plan.decision == "manual_review_required"
    assert plan.apply_allowed is True
    assert plan.manual_review_required is True
    assert plan.recommended_next_safe_action == "manual_review_detail_evidence_discovery"
    assert plan.evidence["decision_taxonomy"] == "manual_review_required"
    assert plan.evidence["bounded_discovery_attempted"] is True


def test_unprobed_detail_plan_stays_deferred_without_apply() -> None:
    plan = build_detail_evidence_plan(
        candidate(),
        passed_initial_gates(),
        (),
        reviewed_by="pytest",
        detail_candidate_count=0,
    )

    assert plan.gate_status == "deferred"
    assert plan.decision == "defer"
    assert plan.apply_allowed is False
    assert plan.manual_review_required is False
    assert plan.evidence["decision_taxonomy"] == "not_executed"
    assert plan.evidence["bounded_discovery_attempted"] is False

def test_report_payload_and_markdown_surface_counts() -> None:
    plan = build_detail_evidence_plan(
        candidate(),
        passed_initial_gates(),
        (),
        reviewed_by="pytest",
        detail_candidate_count=0,
    )
    payload = report_payload(benchmark_label="detail001_test", plans=[plan])
    text = render_markdown(payload)

    assert payload["campaign"] == "DETAIL-001 Detail Evidence Discovery Foundation"
    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["deferred_count"] == 1
    assert "DETAIL-001 Detail Evidence Discovery Foundation" in text
    assert "detail001_test" in text
