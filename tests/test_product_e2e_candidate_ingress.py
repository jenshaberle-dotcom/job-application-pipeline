from __future__ import annotations

import pytest

from src.search_intelligence.product_e2e_candidate_ingress import (
    APPROVAL_TOKEN,
    PROVENANCE_BACKFILL_APPROVAL_TOKEN,
    ExistingCandidate,
    ExistingCandidateProvenance,
    build_candidate_ingress_plan,
    build_candidate_provenance_backfill_plan,
    select_apply_plans,
    select_provenance_backfill_plans,
)
from src.search_intelligence.product_e2e_golden_path import DiscoveryCase


def case(
    source_class: str,
    *,
    company_key: str = "accompio",
    company_name: str = "accompio GmbH",
    seed_type: str = "job_text_signal_seed",
) -> DiscoveryCase:
    return DiscoveryCase(
        case_id=f"{source_class}|{company_key}",
        discovery_source_class=source_class,
        seed_type=seed_type,
        seed_source_table="market_evidence",
        company_key=company_key,
        company_name=company_name,
        source_name="bundesagentur_fuer_arbeit",
        seed_url="https://example.invalid/job/1",
        priority_score=0.8,
        prior_reason="test",
    )


def provenance_candidate(
    *,
    candidate_id: int = 42,
    company_key: str = "accompio",
    company_name: str = "accompio GmbH",
    status: str = "discovery",
    candidate_url: str | None = None,
    discovery_source_class: str | None = None,
) -> ExistingCandidateProvenance:
    return ExistingCandidateProvenance(
        candidate_id=candidate_id,
        company_key=company_key,
        company_name=company_name,
        status=status,
        candidate_url=candidate_url,
        discovery_source_class=discovery_source_class,
    )


def test_public_job_api_signal_can_only_create_discovery_candidate() -> None:
    plan = build_candidate_ingress_plan(
        case("public_job_api_discovery"),
        existing_candidate=None,
    )

    assert plan.action == "create_discovery_candidate"
    assert plan.plan_status == "ready_for_explicit_apply"
    assert plan.create_allowed_after_explicit_approval is True
    assert plan.source_name_candidate == "accompio:discovery"
    assert plan.source_family_candidate == "accompio"
    assert plan.source_type_candidate == "employer_origin_career_site"
    assert plan.risk_level == "unknown"
    assert plan.seed_url == "https://example.invalid/job/1"


def test_aggregator_signal_uses_same_candidate_contract() -> None:
    plan = build_candidate_ingress_plan(
        case(
            "aggregator_company_discovery",
            company_key="one_and_one",
            company_name="1&1",
            seed_type="aggregator_company_seed",
        ),
        existing_candidate=None,
    )

    assert plan.action == "create_discovery_candidate"
    assert plan.source_type_candidate == "employer_origin_career_site"
    assert plan.company_name == "1&1"
    assert "aggregator" in plan.reason


def test_manual_observation_requires_separate_operator_opt_in() -> None:
    plan = build_candidate_ingress_plan(
        case(
            "manual_observation",
            company_key="example_employer",
            company_name="Example Employer GmbH",
            seed_type="company_name_only_seed",
        ),
        existing_candidate=None,
    )

    assert plan.action == "create_discovery_candidate_after_manual_opt_in"
    assert plan.plan_status == "operator_decision_required"
    assert plan.create_allowed_after_explicit_approval is True
    assert plan.manual_observation_opt_in_required is True
    assert plan.risk_level == "medium"


def test_existing_candidate_is_never_duplicated() -> None:
    existing = ExistingCandidate(
        candidate_id=42,
        company_key="accompio",
        company_name="accompio GmbH",
        status="discovery",
    )

    plan = build_candidate_ingress_plan(
        case("public_job_api_discovery"),
        existing_candidate=existing,
    )

    assert plan.action == "skip_existing_candidate"
    assert plan.create_allowed_after_explicit_approval is False
    assert plan.existing_candidate_id == 42


def test_missing_identity_fails_closed() -> None:
    missing = case(
        "public_job_api_discovery",
        company_key="",
        company_name="",
    )

    plan = build_candidate_ingress_plan(missing, existing_candidate=None)

    assert plan.action == "block_missing_employer_identity"
    assert plan.plan_status == "capability_gap"
    assert plan.create_allowed_after_explicit_approval is False


def test_existing_origin_evidence_does_not_reenter_discovery_creation() -> None:
    plan = build_candidate_ingress_plan(
        case("existing_origin_evidence", seed_type="origin_url_seed"),
        existing_candidate=None,
    )

    assert plan.action == "not_primary_discovery_ingress"
    assert plan.plan_status == "valid_stop"
    assert plan.create_allowed_after_explicit_approval is False


def test_apply_selection_requires_manual_opt_in() -> None:
    manual_plan = build_candidate_ingress_plan(
        case(
            "manual_observation",
            company_key="example_employer",
            company_name="Example Employer GmbH",
        ),
        existing_candidate=None,
    )

    with pytest.raises(ValueError, match="requires explicit manual opt-in"):
        select_apply_plans(
            [manual_plan],
            requested_company_keys=["example_employer"],
            include_manual_observations=False,
        )

    selected = select_apply_plans(
        [manual_plan],
        requested_company_keys=["example_employer"],
        include_manual_observations=True,
    )
    assert selected == (manual_plan,)


def test_apply_selection_is_exact_and_rejects_unknown_key() -> None:
    plan = build_candidate_ingress_plan(
        case("public_job_api_discovery"),
        existing_candidate=None,
    )

    with pytest.raises(ValueError, match="not present in the current plan"):
        select_apply_plans(
            [plan],
            requested_company_keys=["another_company"],
            include_manual_observations=False,
        )

    assert APPROVAL_TOKEN == "approve_product_e2e_discovery_candidate_creation"


def test_legacy_unresolved_candidate_is_ready_for_provenance_backfill() -> None:
    plan = build_candidate_provenance_backfill_plan(
        case(
            "aggregator_company_discovery",
            company_key="one_and_one",
            company_name="1&1",
            seed_type="aggregator_company_seed",
        ),
        provenance_candidate(
            candidate_id=46,
            company_key="one_and_one",
            company_name="1&1",
        ),
    )

    assert plan.action == "backfill_missing_discovery_provenance"
    assert plan.plan_status == "ready_for_provenance_backfill"
    assert plan.backfill_allowed_after_explicit_approval is True
    assert plan.candidate_id == 46


def test_matching_existing_provenance_is_idempotent() -> None:
    plan = build_candidate_provenance_backfill_plan(
        case("public_job_api_discovery"),
        provenance_candidate(
            discovery_source_class="public_job_api_discovery",
        ),
    )

    assert plan.action == "skip_existing_candidate_provenance_complete"
    assert plan.plan_status == "passed"
    assert plan.backfill_allowed_after_explicit_approval is False


def test_conflicting_existing_provenance_fails_closed() -> None:
    plan = build_candidate_provenance_backfill_plan(
        case("public_job_api_discovery"),
        provenance_candidate(
            discovery_source_class="aggregator_company_discovery",
        ),
    )

    assert plan.action == "block_conflicting_discovery_provenance"
    assert plan.plan_status == "capability_gap"
    assert plan.backfill_allowed_after_explicit_approval is False


def test_resolved_or_later_state_candidate_is_not_backfilled() -> None:
    resolved = build_candidate_provenance_backfill_plan(
        case("public_job_api_discovery"),
        provenance_candidate(candidate_url="https://example.invalid/careers"),
    )
    later_state = build_candidate_provenance_backfill_plan(
        case("public_job_api_discovery"),
        provenance_candidate(status="validated"),
    )

    assert resolved.action == "valid_stop_existing_candidate_origin_url_present"
    assert resolved.backfill_allowed_after_explicit_approval is False
    assert later_state.action == "valid_stop_existing_candidate_not_discovery"
    assert later_state.backfill_allowed_after_explicit_approval is False


def test_provenance_backfill_selection_requires_exact_target_and_ready_plan() -> None:
    ready = build_candidate_provenance_backfill_plan(
        case("public_job_api_discovery"),
        provenance_candidate(candidate_id=42),
    )
    complete = build_candidate_provenance_backfill_plan(
        case(
            "aggregator_company_discovery",
            company_key="one_and_one",
            company_name="1&1",
        ),
        provenance_candidate(
            candidate_id=46,
            company_key="one_and_one",
            company_name="1&1",
            discovery_source_class="aggregator_company_discovery",
        ),
    )

    selected = select_provenance_backfill_plans(
        [ready, complete],
        requested_targets=["42:accompio"],
    )
    assert selected == (ready,)

    with pytest.raises(ValueError, match="not allowed"):
        select_provenance_backfill_plans(
            [ready, complete],
            requested_targets=["46:one_and_one"],
        )

    with pytest.raises(ValueError, match="not 'another_company'"):
        select_provenance_backfill_plans(
            [ready],
            requested_targets=["42:another_company"],
        )

    assert PROVENANCE_BACKFILL_APPROVAL_TOKEN == (
        "approve_product_e2e_discovery_candidate_provenance_backfill"
    )
