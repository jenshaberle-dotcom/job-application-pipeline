from __future__ import annotations

from src.search_intelligence.employer_origin_connector_generation import (
    GENERATION_BOUNDARY,
    REQUIRED_GENERATION_GATES,
    GateReassessmentSignal,
    GateReview,
    SourceCandidate,
    build_connector_generation_plan,
)


def candidate(status: str = "connector_candidate", source_type: str = "employer_origin_career_site") -> SourceCandidate:
    return SourceCandidate(
        candidate_id=7,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/jobs",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate=source_type,
        status=status,
        risk_level="low",
    )




def reassessment_signal() -> GateReassessmentSignal:
    return GateReassessmentSignal(
        status="open",
        false_negative_risk_level="critical",
        priority=120,
        trigger_reason="unresolved employer-origin candidate has five or more recent aggregator sightings",
        suggested_search_terms=("analytics", "data platform"),
        updated_at="2026-06-01 00:33:13+00",
        latest_gate_reviewed_at="2026-05-29 12:25:38+00",
    )


def gate(name: str, status: str = "passed", decision: str = "continue", evidence: dict | None = None) -> GateReview:
    return GateReview(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=None,
        evidence=evidence or {},
    )


def passed_gates() -> dict[str, GateReview]:
    gates = {name: gate(name) for name in REQUIRED_GENERATION_GATES}
    gates["connector_candidate_gate"] = gate(
        "connector_candidate_gate",
        decision="build_connector_candidate",
        evidence={
            "connector_candidate_spec": {
                "recommended_connector": {
                    "module_path": "src/connectors/hdi.py",
                    "test_path": "tests/test_hdi_connector.py",
                    "docs_path": "docs/source_analysis/hdi_connector_candidate.md",
                },
                "detail_evidence": {
                    "detail_urls": ["https://careers.hdi.group/jobs/product-owner-data-platform"]
                },
            }
        },
    )
    return gates


def test_generation_plan_is_ready_for_bounded_dry_run_when_gate_evidence_is_complete() -> None:
    plan = build_connector_generation_plan(
        candidate=candidate(),
        gates=passed_gates(),
        artifacts_exist=False,
        reviewed_by="jens",
    )

    assert plan.generation_status == "ready"
    assert plan.recommendation == "prepare_connector_artifact_dry_run"
    assert plan.connector_module_path == "src/connectors/hdi.py"
    assert "--dry-run" in (plan.next_command or "")
    assert plan.boundary == GENERATION_BOUNDARY
    assert plan.boundary["source_activation_allowed"] is False
    assert plan.boundary["bronze_persistence_allowed"] is False
    assert plan.boundary["auto_pr_allowed"] is False
    assert plan.evidence["source_role"] == "origin_validation_ground_truth"


def test_generation_plan_stops_when_required_gates_are_missing() -> None:
    gates = passed_gates()
    del gates["incremental_uniqueness_gate"]

    plan = build_connector_generation_plan(candidate=candidate(), gates=gates)

    assert plan.generation_status == "manual_review_required"
    assert plan.recommendation == "stop_before_connector_generation"
    assert plan.reason == "required generation gates are missing"
    assert plan.evidence["missing_required_gates"] == ["incremental_uniqueness_gate"]


def test_generation_plan_stops_when_required_gate_is_not_passed() -> None:
    gates = passed_gates()
    gates["detail_evidence_gate"] = GateReview(
        gate_name="detail_evidence_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="no concrete detail URLs",
        evidence={},
    )

    plan = build_connector_generation_plan(candidate=candidate(), gates=gates)

    assert plan.generation_status == "manual_review_required"
    assert plan.reason == "required generation gates are not all passed"
    assert plan.evidence["unpassed_required_gates"][0]["gate_name"] == "detail_evidence_gate"


def test_generation_plan_routes_existing_artifacts_to_validation_instead_of_regeneration() -> None:
    plan = build_connector_generation_plan(
        candidate=candidate(),
        gates=passed_gates(),
        artifacts_exist=True,
        reviewed_by="jens",
    )

    assert plan.generation_status == "already_generated"
    assert plan.recommendation == "review_existing_connector_artifacts"
    assert "run_employer_origin_connector_validation_agent" in (plan.next_command or "")
    assert "--reviewed-by jens" in (plan.next_command or "")


def test_generation_plan_does_not_apply_to_active_controlled_source() -> None:
    plan = build_connector_generation_plan(candidate=candidate(status="active_controlled"), gates=passed_gates())

    assert plan.generation_status == "not_applicable"
    assert plan.recommendation == "monitor_existing_source"


def test_generation_plan_blocks_non_employer_origin_source_type() -> None:
    plan = build_connector_generation_plan(
        candidate=candidate(source_type="aggregator"),
        gates=passed_gates(),
    )

    assert plan.generation_status == "blocked"
    assert plan.recommendation == "stop_before_connector_generation"


def test_generation_plan_routes_learning_signal_to_gate_reassessment_before_build() -> None:
    gates = passed_gates()
    gates["detail_evidence_gate"] = GateReview(
        gate_name="detail_evidence_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="no concrete detail URLs",
        evidence={},
    )

    plan = build_connector_generation_plan(
        candidate=candidate(),
        gates=gates,
        reassessment_signal=reassessment_signal(),
        reviewed_by="jens",
    )

    assert plan.generation_status == "gate_reassessment_required"
    assert plan.recommendation == "rerun_employer_origin_gate_reassessment"
    assert "new learning evidence" in plan.reason
    assert "run_employer_origin_agent_chain" in (plan.next_command or "")
    assert "--attempt-repair" in (plan.next_command or "")
    assert plan.evidence["learning_reassessment_signal"]["gate_reassessment_required"] is True
    assert plan.evidence["learning_reassessment_signal"]["false_negative_risk_level"] == "critical"
    assert plan.evidence["learning_reassessment_signal"]["latest_gate_reviewed_at"] == "2026-05-29 12:25:38+00"
    assert "detail_evidence_gate" in plan.evidence["learning_reassessment_signal"]["target_gates"]
