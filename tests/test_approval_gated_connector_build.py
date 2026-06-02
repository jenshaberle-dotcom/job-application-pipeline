from __future__ import annotations

from src.search_intelligence.approval_gated_connector_build import (
    BuildQueueEvidence,
    EARLY_BUILD_GATE_NAMES,
    GateReview,
    GenerationPlanState,
    LearningPressure,
    SourceCandidate,
    evaluate_connector_build_request,
)


def make_candidate(status: str = "manual_review_required") -> SourceCandidate:
    return SourceCandidate(
        candidate_id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/en/your_career_opportunities/job_board",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status=status,
        operational_risk_level="low",
    )


def passed_gate(name: str, decision: str = "continue") -> GateReview:
    return GateReview(gate_name=name, gate_status="passed", decision=decision)


def early_gates() -> dict[str, GateReview]:
    return {name: passed_gate(name) for name in EARLY_BUILD_GATE_NAMES}


def high_pressure() -> LearningPressure:
    return LearningPressure(
        status="open",
        false_negative_risk_level="critical",
        priority=120,
        trigger_reason="unresolved employer-origin candidate has repeated aggregator sightings",
        suggested_search_terms=("data platform", "analytics"),
        updated_at="2026-06-01T10:00:00+00:00",
    )


def test_high_pressure_with_early_gates_requires_explicit_build_approval() -> None:
    gates = early_gates()
    gates["detail_evidence_gate"] = GateReview(
        gate_name="detail_evidence_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="no concrete detail pages found",
    )

    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates=gates,
        generation_plan=GenerationPlanState(
            generation_status="manual_review_required",
            recommendation="stop_before_connector_generation",
        ),
        learning_pressure=high_pressure(),
        artifact_files_exist=False,
        approval_provided=False,
        reviewed_by="jens",
    )

    assert request.build_status == "build_approval_required"
    assert request.recommendation == "request_explicit_build_approval"
    assert request.build_mode == "bounded_investigation_connector"
    assert request.approval_required is True
    assert request.artifact_generation_allowed is False
    assert "--approve-build" in (request.next_command or "")
    assert request.boundary["connector_registration_allowed"] is False
    assert request.boundary["bronze_persistence_allowed"] is False


def test_explicit_build_approval_allows_artifact_generation_only() -> None:
    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates=early_gates(),
        generation_plan=None,
        learning_pressure=high_pressure(),
        artifact_files_exist=False,
        approval_provided=True,
        reviewed_by="jens",
    )

    assert request.build_status == "artifact_generation_allowed"
    assert request.recommendation == "generate_connector_artifacts"
    assert request.artifact_generation_allowed is True
    assert request.boundary["connector_artifact_generation_allowed_after_explicit_approval"] is True
    assert request.boundary["connector_registration_allowed"] is False
    assert request.boundary["source_activation_allowed"] is False


def test_generation_plan_reassessment_blocks_build_until_gate_chain_reruns() -> None:
    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates=early_gates(),
        generation_plan=GenerationPlanState(
            generation_status="gate_reassessment_required",
            recommendation="rerun_employer_origin_gate_reassessment",
        ),
        learning_pressure=high_pressure(),
        artifact_files_exist=False,
        approval_provided=True,
        reviewed_by="jens",
    )

    assert request.build_status == "gate_reassessment_required"
    assert request.recommendation == "rerun_employer_origin_gate_reassessment"
    assert request.artifact_generation_allowed is False
    assert "run_employer_origin_agent_chain" in (request.next_command or "")



def test_gate_reassessment_with_exhausted_detail_repair_can_request_investigation_build() -> None:
    gates = early_gates()
    gates["detail_evidence_gate"] = GateReview(
        gate_name="detail_evidence_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="bounded repair found no concrete detail pages with profile and target/remote signals",
    )

    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates=gates,
        generation_plan=GenerationPlanState(
            generation_status="gate_reassessment_required",
            recommendation="rerun_employer_origin_gate_reassessment",
        ),
        learning_pressure=high_pressure(),
        artifact_files_exist=False,
        approval_provided=False,
        reviewed_by="jens",
    )

    assert request.build_status == "build_approval_required"
    assert request.recommendation == "request_explicit_build_approval"
    assert request.build_mode == "bounded_investigation_connector"
    assert request.artifact_generation_allowed is False
    assert "--approve-build" in (request.next_command or "")
    assert request.evidence["detail_evidence_repair_exhausted"] is True

def test_existing_artifacts_move_to_validation_not_rebuild() -> None:
    gates = early_gates()
    gates["connector_candidate_gate"] = passed_gate("connector_candidate_gate", decision="build_connector_candidate")

    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates=gates,
        generation_plan=None,
        learning_pressure=None,
        artifact_files_exist=True,
        approval_provided=False,
        reviewed_by="jens",
    )

    assert request.build_status == "artifacts_present"
    assert request.recommendation == "run_connector_validation"
    assert request.artifact_generation_allowed is False
    assert "run_employer_origin_connector_validation_agent" in (request.next_command or "")
    assert "--run-pytest" not in (request.next_command or "")


def test_low_pressure_without_connector_gate_stops_before_build() -> None:
    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates=early_gates(),
        generation_plan=None,
        learning_pressure=LearningPressure(
            status="open",
            false_negative_risk_level="low",
            priority=10,
            trigger_reason="monitoring evidence only",
            suggested_search_terms=(),
        ),
        artifact_files_exist=False,
        approval_provided=False,
        reviewed_by="jens",
    )

    assert request.build_status == "manual_review_required"
    assert request.recommendation == "stop_before_build"
    assert request.artifact_generation_allowed is False


def test_active_candidate_is_not_applicable() -> None:
    request = evaluate_connector_build_request(
        candidate=make_candidate(status="active_controlled"),
        gates={},
        generation_plan=None,
        learning_pressure=None,
        artifact_files_exist=False,
        approval_provided=False,
        reviewed_by="jens",
    )

    assert request.build_status == "not_applicable"
    assert request.recommendation == "monitor_existing_source"


def s7o_build_queue_evidence() -> BuildQueueEvidence:
    return BuildQueueEvidence(
        candidate_id=2,
        queue_action="build_candidate_recommended",
        queue_reason="reachable origin source and concrete job-detail evidence",
        recommended_command_or_review=(
            "python -m scripts.run_approval_gated_connector_build_agent "
            "--company-key hdi --reviewed-by jens --write"
        ),
        feasibility_status="likely_feasible",
        feasibility_decision="continue_to_connector_build_planning",
        url_quality_status="valid_probe_ready",
        job_detail_candidate_evidence_count=2,
        structural_job_evidence_count=5,
        review_created_at="2026-06-02T19:00:00+00:00",
        candidate_url="https://www.enercity.de/karriere/jobs",
        page_type="job_search_page",
        sample_job_count=2,
        sample_job_urls=(
            "https://www.enercity.de/karriere/jobs/job-a",
            "https://www.enercity.de/karriere/jobs/job-b",
        ),
    )


def test_s7o_build_queue_recommendation_requires_explicit_approval() -> None:
    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates={},
        generation_plan=None,
        learning_pressure=None,
        artifact_files_exist=False,
        approval_provided=False,
        reviewed_by="jens",
        build_queue_evidence=s7o_build_queue_evidence(),
    )

    assert request.build_status == "build_approval_required"
    assert request.recommendation == "request_explicit_build_approval"
    assert request.build_mode == "connector_candidate_from_build_queue_evidence"
    assert request.approval_required is True
    assert request.artifact_generation_allowed is False
    assert "--approve-build" in (request.next_command or "")
    assert request.evidence["build_queue_evidence"]["queue_action"] == "build_candidate_recommended"
    assert request.evidence["build_queue_evidence"]["sample_job_urls"] == [
        "https://www.enercity.de/karriere/jobs/job-a",
        "https://www.enercity.de/karriere/jobs/job-b",
    ]
    assert request.boundary["connector_registration_allowed"] is False
    assert request.boundary["source_activation_allowed"] is False
    assert request.boundary["bronze_persistence_allowed"] is False


def test_s7o_build_queue_with_explicit_approval_allows_artifacts_only() -> None:
    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates={},
        generation_plan=None,
        learning_pressure=None,
        artifact_files_exist=False,
        approval_provided=True,
        reviewed_by="jens",
        build_queue_evidence=s7o_build_queue_evidence(),
    )

    assert request.build_status == "artifact_generation_allowed"
    assert request.recommendation == "generate_connector_artifacts"
    assert request.build_mode == "connector_candidate_from_build_queue_evidence"
    assert request.artifact_generation_allowed is True
    assert request.boundary["connector_artifact_generation_allowed_after_explicit_approval"] is True
    assert request.boundary["connector_registration_allowed"] is False
    assert request.boundary["source_activation_allowed"] is False
    assert request.boundary["bronze_persistence_allowed"] is False


def test_s7o_continue_existing_build_flow_keeps_approval_required() -> None:
    queue = s7o_build_queue_evidence()
    queue = BuildQueueEvidence(
        candidate_id=queue.candidate_id,
        queue_action="continue_existing_build_flow",
        queue_reason="A connector build flow already exists; continue the existing approval path.",
        recommended_command_or_review=queue.recommended_command_or_review,
        feasibility_status=queue.feasibility_status,
        feasibility_decision=queue.feasibility_decision,
        url_quality_status=queue.url_quality_status,
        job_detail_candidate_evidence_count=queue.job_detail_candidate_evidence_count,
        structural_job_evidence_count=queue.structural_job_evidence_count,
        review_created_at=queue.review_created_at,
        candidate_url=queue.candidate_url,
        page_type=queue.page_type,
        sample_job_count=queue.sample_job_count,
        sample_job_urls=queue.sample_job_urls,
    )

    request = evaluate_connector_build_request(
        candidate=make_candidate(),
        gates={},
        generation_plan=None,
        learning_pressure=None,
        artifact_files_exist=False,
        approval_provided=False,
        reviewed_by="jens",
        build_queue_evidence=queue,
    )

    assert request.build_status == "build_approval_required"
    assert request.recommendation == "request_explicit_build_approval"
    assert request.build_mode == "connector_candidate_from_build_queue_evidence"
    assert request.artifact_generation_allowed is False
    assert request.evidence["build_queue_evidence"]["queue_action"] == "continue_existing_build_flow"
