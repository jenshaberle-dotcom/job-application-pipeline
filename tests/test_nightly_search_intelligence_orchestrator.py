from src.search_intelligence.nightly_orchestrator import (
    ApprovalQueueItem,
    CandidateLifecycleItem,
    MarketCoverageSummary,
    OrchestratorInput,
    OriginDiscoveryItem,
    build_orchestrator_plan,
)


def test_orchestrator_plan_surfaces_approval_and_open_candidate_pressure() -> None:
    plan = build_orchestrator_plan(
        OrchestratorInput(
            summary=MarketCoverageSummary(
                employer_origin_candidate_count=2,
                active_origin_connector_count=1,
                open_candidate_count=1,
                build_approval_required_count=1,
                critical_fn_pressure_candidate_count=1,
            ),
            lifecycle_items=(
                CandidateLifecycleItem(
                    company_key="hdi",
                    display_company_name="HDI Group",
                    current_stage="build_approval_required",
                    fn_pressure_level="critical",
                    blocking_gate="detail_evidence_gate",
                    recommended_next_action="Review and approve connector build request",
                ),
            ),
            approval_items=(
                ApprovalQueueItem(
                    approval_type="connector_build",
                    company_key="hdi",
                    display_company_name="HDI Group",
                    current_stage="build_approval_required",
                    recommendation="request_explicit_build_approval",
                ),
            ),
            origin_discovery_items=(
                OriginDiscoveryItem(
                    company_key="hdi",
                    company_name="HDI Group",
                    discovery_status="selected",
                    decision="continue_to_connector_feasibility",
                    selected_origin_url="https://careers.hdi.group/en/your_career_opportunities/job_board",
                ),
            ),
        )
    )

    assert plan.status == "completed_with_actions"
    assert plan.guardrails["source_activation_allowed"] is False
    assert plan.guardrails["bronze_persistence_allowed"] is False

    approval_step = next(step for step in plan.steps if step.step_name == "approval_queue_review")
    assert approval_step.step_status == "attention_required"
    assert approval_step.action_mode == "manual_approval_required"
    assert approval_step.metrics["approval_queue_count"] == 1


def test_orchestrator_plan_flags_missing_origin_discovery_review() -> None:
    plan = build_orchestrator_plan(
        OrchestratorInput(
            summary=MarketCoverageSummary(employer_origin_candidate_count=1, open_candidate_count=1),
            lifecycle_items=(),
            approval_items=(),
            origin_discovery_items=(
                OriginDiscoveryItem(
                    company_key="example",
                    company_name="Example AG",
                    discovery_status="manual_review_required",
                    decision="manual_review_required",
                    selected_origin_url=None,
                    blocker_code="insufficient_origin_evidence",
                ),
            ),
        )
    )

    origin_step = next(step for step in plan.steps if step.step_name == "origin_source_discovery_gate_review")
    assert origin_step.step_status == "attention_required"
    assert origin_step.action_mode == "queue_review"
    assert origin_step.metrics["origin_discovery_missing_or_unselected_count"] == 1


def test_orchestrator_plan_is_completed_when_no_attention_items_exist() -> None:
    plan = build_orchestrator_plan(
        OrchestratorInput(
            summary=MarketCoverageSummary(
                employer_origin_candidate_count=1,
                active_origin_connector_count=1,
            ),
            lifecycle_items=(),
            approval_items=(),
            origin_discovery_items=(
                OriginDiscoveryItem(
                    company_key="finanz_informatik",
                    company_name="Finanz Informatik GmbH & Co. KG",
                    discovery_status="selected",
                    decision="continue_to_connector_feasibility",
                    selected_origin_url="https://www.f-i.de/karriere",
                ),
            ),
        )
    )

    assert plan.status == "completed"
    assert all(step.step_status != "blocked" for step in plan.steps)
