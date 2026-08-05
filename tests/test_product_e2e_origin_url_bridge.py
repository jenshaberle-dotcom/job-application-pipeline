from __future__ import annotations

import pytest

from src.search_intelligence.product_e2e_origin_url_bridge import (
    APPROVAL_TOKEN,
    OriginUrlBridgeCandidate,
    build_origin_url_bridge_plan,
    discovery_source_class_from_notes,
    parse_exact_target,
    select_exact_target_plans,
    select_source_diverse_plans,
)


def candidate(
    candidate_id: int,
    source_class: str | None,
    *,
    company_key: str = "accompio",
    company_name: str = "accompio GmbH",
    status: str = "discovery",
    candidate_url: str | None = None,
) -> OriginUrlBridgeCandidate:
    notes = (
        "Created by PRODUCT-E2E-INGRESS-001; "
        f"discovery_source_class={source_class}; seed_type=test"
        if source_class
        else "Created without explicit ingress provenance."
    )
    return OriginUrlBridgeCandidate(
        candidate_id=candidate_id,
        company_key=company_key,
        company_name=company_name,
        status=status,
        candidate_url=candidate_url,
        notes=notes,
        discovery_source_class=source_class,
    )


def test_provenance_is_read_only_from_explicit_notes_marker() -> None:
    notes = (
        "Created by PRODUCT-E2E-INGRESS-001 from a generic discovery signal; "
        "discovery_source_class=public_job_api_discovery; seed_type=job_text_signal_seed"
    )

    assert discovery_source_class_from_notes(notes) == "public_job_api_discovery"
    assert discovery_source_class_from_notes("company=accompio") is None


def test_supported_source_classes_share_one_bridge_action() -> None:
    aggregator = build_origin_url_bridge_plan(
        candidate(
            10,
            "aggregator_company_discovery",
            company_key="one_and_one",
            company_name="1&1",
        )
    )
    public_api = build_origin_url_bridge_plan(
        candidate(11, "public_job_api_discovery")
    )

    assert aggregator.action == public_api.action
    assert aggregator.action == "run_bounded_origin_discovery_then_cand001"
    assert aggregator.origin_discovery_allowed is True
    assert public_api.origin_discovery_allowed is True


def test_missing_provenance_fails_closed_without_company_inference() -> None:
    plan = build_origin_url_bridge_plan(candidate(12, None))

    assert plan.plan_status == "capability_gap"
    assert plan.action == "block_missing_discovery_provenance"
    assert plan.origin_discovery_allowed is False
    assert plan.apply_target_allowed is False


def test_other_source_class_keeps_existing_lifecycle() -> None:
    plan = build_origin_url_bridge_plan(
        candidate(13, "existing_origin_evidence")
    )

    assert plan.plan_status == "valid_stop"
    assert plan.action == "valid_stop_source_class_outside_bridge"


def test_existing_url_is_an_idempotent_pass() -> None:
    plan = build_origin_url_bridge_plan(
        candidate(
            14,
            "aggregator_company_discovery",
            candidate_url="https://careers.example.org/jobs",
        )
    )

    assert plan.plan_status == "passed"
    assert plan.action == "no_action_origin_url_already_persisted"
    assert plan.origin_discovery_allowed is False
    assert plan.apply_target_allowed is True


def test_source_diverse_selection_prefers_both_ingress_classes() -> None:
    plans = [
        build_origin_url_bridge_plan(candidate(20, "aggregator_company_discovery")),
        build_origin_url_bridge_plan(
            candidate(
                21,
                "aggregator_company_discovery",
                company_key="second",
                company_name="Second GmbH",
            )
        ),
        build_origin_url_bridge_plan(
            candidate(
                22,
                "public_job_api_discovery",
                company_key="third",
                company_name="Third GmbH",
            )
        ),
    ]

    selected = select_source_diverse_plans(plans, limit=2)

    assert [item.discovery_source_class for item in selected] == [
        "aggregator_company_discovery",
        "public_job_api_discovery",
    ]


def test_exact_apply_target_binds_id_and_company_key() -> None:
    plan = build_origin_url_bridge_plan(
        candidate(30, "public_job_api_discovery")
    )

    assert parse_exact_target("30:accompio") == (30, "accompio")
    assert select_exact_target_plans(
        [plan], requested_targets=["30:accompio"]
    ) == (plan,)

    with pytest.raises(ValueError, match="not 'wrong_company'"):
        select_exact_target_plans(
            [plan], requested_targets=["30:wrong_company"]
        )
    with pytest.raises(ValueError, match="exact format"):
        parse_exact_target("accompio")


def test_blocked_plan_cannot_be_selected_for_apply() -> None:
    blocked = build_origin_url_bridge_plan(candidate(31, None))

    with pytest.raises(ValueError, match="is blocked"):
        select_exact_target_plans(
            [blocked], requested_targets=["31:accompio"]
        )


def test_apply_token_is_separate_from_candidate_creation_token() -> None:
    assert APPROVAL_TOKEN == "approve_product_e2e_origin_url_persistence"
