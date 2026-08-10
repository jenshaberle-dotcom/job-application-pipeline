from __future__ import annotations

from dataclasses import replace

from src.search_intelligence.product_e2e_golden_path import (
    DiscoveryCase,
    GateState,
    LifecycleSnapshot,
    summarize_gaps,
    trace_case,
)


def _case(name: str, source_class: str) -> DiscoveryCase:
    key = name.casefold().replace(" ", "_")
    return DiscoveryCase(
        case_id=f"case:{key}",
        discovery_source_class=source_class,
        seed_type="company_name_only_seed",
        seed_source_table="test",
        company_key=key,
        company_name=name,
        source_name=source_class,
        seed_url=None,
        priority_score=0.8,
        prior_reason="test",
    )


def _missing_inventory_snapshot() -> LifecycleSnapshot:
    return LifecycleSnapshot(
        candidate_id=1,
        canonical_company_name="Canonical Employer GmbH",
        source_name_candidate="canonical_employer:discovery",
        candidate_status="discovery",
        candidate_url="https://jobs.example.test/",
        current_stage="candidate_review",
        gate_states={},
        source_raw_job_count=None,
        silver_job_count=0,
        product_readiness_counts={},
        top5_job_count=0,
    )


def _origin_inventory_stage(snapshot: LifecycleSnapshot, *, source_class: str = "aggregator_company_discovery"):
    trace = trace_case(_case("Employer", source_class), snapshot)
    return trace, next(stage for stage in trace.stages if stage.stage == "origin_inventory")


def test_upstream_manual_gate_is_preserved_as_operator_decision() -> None:
    snapshot = replace(
        _missing_inventory_snapshot(),
        current_stage="blocked_by_gate",
        blocking_gate="relevance_gate",
        blocking_gate_status="manual_review_required",
        blocker_reason="bounded relevance evidence requires manual review",
    )

    trace, inventory = _origin_inventory_stage(snapshot)

    assert trace.overall_status == "operator_decision_required"
    assert trace.next_blocker_stage == "origin_inventory"
    assert inventory.status == "operator_decision_required"
    assert inventory.reason_code == "relevance_gate_manual_review_required"
    assert inventory.reason == "bounded relevance evidence requires manual review"
    assert inventory.evidence == {
        "blocking_gate": "relevance_gate",
        "blocking_gate_status": "manual_review_required",
        "current_stage": "blocked_by_gate",
    }
    assert inventory.operator_decision is not None


def test_upstream_manual_gate_does_not_merge_with_missing_detail_evidence() -> None:
    missing_trace = trace_case(
        _case("Missing Detail", "aggregator_company_discovery"),
        _missing_inventory_snapshot(),
    )
    manual_trace = trace_case(
        _case("Manual Relevance", "existing_origin_evidence"),
        replace(
            _missing_inventory_snapshot(),
            blocking_gate="relevance_gate",
            blocking_gate_status="manual_review_required",
            blocker_reason="manual relevance review required",
        ),
    )

    gaps = summarize_gaps([missing_trace, manual_trace])
    inventory_gaps = [gap for gap in gaps if gap.stage == "origin_inventory"]

    assert {(gap.reason_code, gap.scope) for gap in inventory_gaps} == {
        ("origin_inventory_unproven", "case_evidence_gap"),
        ("relevance_gate_manual_review_required", "case_evidence_gap"),
    }
    assert not any(gap.scope == "generic_cross_source_gap" for gap in inventory_gaps)


def test_same_upstream_gate_can_still_form_generic_cross_source_gap() -> None:
    snapshot = replace(
        _missing_inventory_snapshot(),
        blocking_gate="relevance_gate",
        blocking_gate_status="manual_review_required",
        blocker_reason="manual relevance review required",
    )
    traces = [
        trace_case(_case("A", "aggregator_company_discovery"), snapshot),
        trace_case(_case("B", "existing_origin_evidence"), snapshot),
    ]

    matching = next(
        gap
        for gap in summarize_gaps(traces)
        if gap.reason_code == "relevance_gate_manual_review_required"
    )

    assert matching.status == "operator_decision_required"
    assert matching.scope == "generic_cross_source_gap"
    assert matching.occurrence_count == 2


def test_detail_evidence_manual_review_keeps_existing_inventory_contract() -> None:
    snapshot = replace(
        _missing_inventory_snapshot(),
        blocking_gate="detail_evidence_gate",
        blocking_gate_status="manual_review_required",
        blocker_reason="detail evidence ambiguous",
        gate_states={
            "detail_evidence_gate": GateState(
                gate_name="detail_evidence_gate",
                gate_status="manual_review_required",
                decision="manual_review_required",
                stop_reason="detail evidence ambiguous",
            )
        },
    )

    trace, inventory = _origin_inventory_stage(snapshot)

    assert trace.overall_status == "operator_decision_required"
    assert inventory.status == "operator_decision_required"
    assert inventory.reason_code == "origin_inventory_unproven"
    assert inventory.reason == "detail evidence ambiguous"
