from __future__ import annotations

from dataclasses import replace

import pytest

from src.search_intelligence.origin_seed_pool import ObservationSeed
from src.search_intelligence.product_e2e_golden_path import (
    AUDIT_BOUNDARY,
    DiscoveryCase,
    GateState,
    LifecycleSnapshot,
    case_from_seed,
    discovery_source_class,
    select_representative_cases,
    summarize_gaps,
    trace_case,
)


def seed(
    *,
    key: str,
    seed_type: str,
    table: str,
    source_name: str | None,
    company_key: str | None,
    company_name: str | None,
    priority: float,
    url: str | None = None,
) -> ObservationSeed:
    return ObservationSeed(
        seed_key=key,
        seed_type=seed_type,
        seed_source_table=table,
        observation_role="test",
        priority_score=priority,
        prior_reason="test",
        company_key=company_key,
        company_name=company_name,
        source_name=source_name,
        seed_url=url,
    )


def case(name: str, source_class: str) -> DiscoveryCase:
    key = name.lower().replace(" ", "_")
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


def test_discovery_source_class_covers_three_requested_ingress_types() -> None:
    stepstone = seed(
        key="stepstone:a",
        seed_type="aggregator_company_seed",
        table="aggregator_novelty_items",
        source_name="stepstone",
        company_key="a",
        company_name="A",
        priority=0.5,
    )
    ba = seed(
        key="ba:b",
        seed_type="job_text_signal_seed",
        table="silver_jobs",
        source_name="bundesagentur_fuer_arbeit",
        company_key="b",
        company_name="B",
        priority=0.6,
    )
    manual = seed(
        key="manual:c",
        seed_type="company_name_only_seed",
        table="market_evidence",
        source_name="manual_market_observation",
        company_key="c",
        company_name="C",
        priority=0.7,
    )

    assert discovery_source_class(stepstone) == "aggregator_company_discovery"
    assert discovery_source_class(ba) == "public_job_api_discovery"
    assert discovery_source_class(manual) == "manual_observation"


def test_non_manual_market_evidence_keeps_origin_evidence_role() -> None:
    origin = seed(
        key="origin:a",
        seed_type="origin_url_seed",
        table="market_evidence",
        source_name="company_career_site",
        company_key="a",
        company_name="A",
        priority=0.8,
        url="https://jobs.example.test/",
    )

    assert discovery_source_class(origin) == "existing_origin_evidence"


def test_portfolio_selection_is_source_diverse_bounded_and_deduplicated() -> None:
    cases = [
        case_from_seed(
            seed(
                key="s:a",
                seed_type="aggregator_company_seed",
                table="aggregator_novelty_items",
                source_name="stepstone",
                company_key="a",
                company_name="A",
                priority=0.7,
            )
        ),
        case_from_seed(
            seed(
                key="s:a:duplicate",
                seed_type="aggregator_company_seed",
                table="market_evidence",
                source_name="stepstone",
                company_key="a",
                company_name="A",
                priority=0.6,
            )
        ),
        case_from_seed(
            seed(
                key="ba:b",
                seed_type="job_text_signal_seed",
                table="silver_jobs",
                source_name="bundesagentur_fuer_arbeit",
                company_key="b",
                company_name="B",
                priority=0.5,
            )
        ),
        case_from_seed(
            seed(
                key="m:c",
                seed_type="company_name_only_seed",
                table="market_evidence",
                source_name="manual_market_observation",
                company_key="c",
                company_name="C",
                priority=0.4,
            )
        ),
        case("D", "existing_origin_evidence"),
        case("E", "other_discovery"),
        case("F", "other_discovery"),
    ]

    selected = select_representative_cases(cases, limit=5)

    assert len(selected) == 5
    assert len({item.company_key for item in selected}) == 5
    assert {
        "aggregator_company_discovery",
        "public_job_api_discovery",
        "manual_observation",
    }.issubset({item.discovery_source_class for item in selected})


def test_origin_seed_does_not_erase_stepstone_discovery_provenance() -> None:
    cases = [
        case_from_seed(
            seed(
                key="origin:a",
                seed_type="origin_url_seed",
                table="employer_origin_source_candidates",
                source_name="a_origin",
                company_key="a",
                company_name="A",
                priority=0.95,
                url="https://jobs.a.test/",
            )
        ),
        case_from_seed(
            seed(
                key="stepstone:a",
                seed_type="aggregator_company_seed",
                table="aggregator_novelty_items",
                source_name="stepstone",
                company_key="a",
                company_name="A",
                priority=0.48,
            )
        ),
        case_from_seed(
            seed(
                key="ba:b",
                seed_type="job_text_signal_seed",
                table="silver_jobs",
                source_name="bundesagentur_fuer_arbeit",
                company_key="b",
                company_name="B",
                priority=0.55,
            )
        ),
        case_from_seed(
            seed(
                key="manual:c",
                seed_type="company_name_only_seed",
                table="market_evidence",
                source_name="manual_market_observation",
                company_key="c",
                company_name="C",
                priority=0.68,
            )
        ),
    ]

    selected = select_representative_cases(cases, limit=3)

    assert [item.discovery_source_class for item in selected] == [
        "aggregator_company_discovery",
        "public_job_api_discovery",
        "manual_observation",
    ]
    assert [item.company_key for item in selected] == ["a", "b", "c"]


def test_identified_ba_case_is_preferred_over_unlinked_raw_seed() -> None:
    cases = [
        DiscoveryCase(
            case_id="ba:unlinked",
            discovery_source_class="public_job_api_discovery",
            seed_type="job_text_signal_seed",
            seed_source_table="raw_jobs",
            company_key=None,
            company_name=None,
            source_name="bundesagentur_fuer_arbeit",
            seed_url="https://ba.example.test/job/1",
            priority_score=0.9,
            prior_reason="test",
        ),
        case_from_seed(
            seed(
                key="ba:linked",
                seed_type="job_text_signal_seed",
                table="silver_jobs",
                source_name="bundesagentur_fuer_arbeit",
                company_key="linked",
                company_name="Linked Employer",
                priority=0.55,
            )
        ),
    ]

    selected = select_representative_cases(cases, limit=1)

    assert selected[0].company_key == "linked"


def test_selection_rejects_more_than_five_cases() -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        select_representative_cases([case("A", "other_discovery")], limit=6)


def complete_snapshot() -> LifecycleSnapshot:
    return LifecycleSnapshot(
        candidate_id=1,
        canonical_company_name="Canonical Employer GmbH",
        source_name_candidate="canonical_employer",
        candidate_status="active_controlled",
        candidate_url="https://jobs.example.test/",
        current_stage="active_controlled",
        gate_states={
            "detail_evidence_gate": GateState(
                gate_name="detail_evidence_gate",
                gate_status="passed",
                decision="continue",
            )
        },
        source_raw_job_count=2,
        silver_job_count=2,
        product_readiness_counts={"rankable": 1, "blocked_hard_filter": 1},
        top5_job_count=1,
    )


def test_downstream_trace_is_identical_for_different_company_names() -> None:
    first = trace_case(
        case("Company One", "aggregator_company_discovery"),
        complete_snapshot(),
    )
    second = trace_case(
        case("Totally Different GmbH", "manual_observation"),
        complete_snapshot(),
    )

    assert [(item.stage, item.status, item.reason_code) for item in first.stages] == [
        (item.stage, item.status, item.reason_code) for item in second.stages
    ]
    assert first.overall_status == second.overall_status == "completed"


def test_missing_origin_candidate_is_cross_source_capability_gap() -> None:
    traces = [
        trace_case(case("A", "aggregator_company_discovery"), LifecycleSnapshot()),
        trace_case(case("B", "public_job_api_discovery"), LifecycleSnapshot()),
    ]

    assert traces[0].next_blocker_stage == "origin_candidate"
    assert traces[1].next_blocker_stage == "origin_candidate"
    matching = next(
        item
        for item in summarize_gaps(traces)
        if item.reason_code == "origin_candidate_missing"
    )
    assert matching.scope == "generic_cross_source_gap"
    assert matching.occurrence_count == 2


def test_build_approval_is_explicit_operator_decision() -> None:
    snapshot = replace(
        complete_snapshot(),
        candidate_status="connector_candidate",
        build_status="build_approval_required",
        queue_reason="build review required",
        source_raw_job_count=None,
        silver_job_count=0,
        product_readiness_counts={},
        top5_job_count=0,
    )

    trace = trace_case(case("A", "aggregator_company_discovery"), snapshot)
    build = next(item for item in trace.stages if item.stage == "connector_build")

    assert build.status == "operator_decision_required"
    assert build.operator_decision == "Approve bounded connector artifact generation."
    assert trace.overall_status == "operator_decision_required"


def test_connector_artifacts_do_not_imply_source_activation() -> None:
    snapshot = replace(
        complete_snapshot(),
        candidate_status="connector_artifact_generated",
        build_status="artifacts_present",
        source_raw_job_count=None,
        silver_job_count=0,
        product_readiness_counts={},
        top5_job_count=0,
    )

    trace = trace_case(case("A", "manual_observation"), snapshot)
    activation = next(item for item in trace.stages if item.stage == "source_activation")

    assert activation.status == "operator_decision_required"
    assert activation.reason_code == "source_activation_approval_required"


def test_rankable_job_outside_top5_is_valid_stop_not_failure() -> None:
    snapshot = replace(complete_snapshot(), top5_job_count=0)
    trace = trace_case(case("A", "public_job_api_discovery"), snapshot)
    final = trace.stages[-1]

    assert final.stage == "top5_serving"
    assert final.status == "valid_stop"
    assert final.reason_code == "rankable_but_not_in_top5"
    assert trace.overall_status == "completed"


def test_audit_boundary_forbids_mutation_and_company_specific_branching() -> None:
    assert AUDIT_BOUNDARY["read_only_database"] is True
    assert AUDIT_BOUNDARY["no_external_requests"] is True
    assert AUDIT_BOUNDARY["no_candidate_creation"] is True
    assert AUDIT_BOUNDARY["no_connector_artifact_generation"] is True
    assert AUDIT_BOUNDARY["no_source_activation"] is True
    assert AUDIT_BOUNDARY["no_bronze_or_silver_write"] is True
    assert AUDIT_BOUNDARY["company_specific_branching_forbidden"] is True
