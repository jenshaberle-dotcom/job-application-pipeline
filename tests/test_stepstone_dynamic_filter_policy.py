from datetime import UTC, datetime, timedelta

import pytest

from src.search_intelligence.stepstone_dynamic_filter_policy import (
    CompanyReselectionState,
    DynamicFilterPolicy,
    PreviousRunCompanyObservation,
    build_filter_capacity_experiment_plan,
    select_next_run_filters,
)


NOW = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
POLICY = DynamicFilterPolicy(
    requested_filter_count=5,
    dominance_override_min_cards=5,
    dominance_override_min_share=0.40,
    policy_version="test-v1",
)


def _observation(
    key: str,
    count: int,
    position: int,
    name: str | None = None,
) -> PreviousRunCompanyObservation:
    return PreviousRunCompanyObservation(
        company_key=key,
        company_name=name or key,
        card_count=count,
        first_position=position,
    )


def test_selection_uses_only_immediately_previous_run() -> None:
    observations = [
        _observation("current_a", 4, 1),
        _observation("current_b", 3, 2),
    ]
    historical_only = CompanyReselectionState(
        company_key="historical_company",
        cooldown_until=NOW - timedelta(days=1),
    )

    selection = select_next_run_filters(
        observations=observations,
        reselection_states=[historical_only],
        policy=POLICY,
        now=NOW,
    )

    assert selection.selected_company_keys == ("current_a", "current_b")
    assert "historical_company" not in selection.selected_company_keys


def test_active_reselection_cooldown_rotates_ordinary_company_out() -> None:
    observations = [
        _observation("alpha", 3, 1),
        _observation("beta", 2, 2),
        _observation("gamma", 1, 3),
    ]
    cooldown = CompanyReselectionState(
        company_key="alpha",
        cooldown_until=NOW + timedelta(days=2),
        last_filtered_at=NOW - timedelta(days=1),
    )

    selection = select_next_run_filters(
        observations=observations,
        reselection_states=[cooldown],
        policy=POLICY,
        now=NOW,
    )

    alpha = next(item for item in selection.items if item.company_key == "alpha")
    assert not alpha.selected_for_next_run
    assert alpha.cooldown_active
    assert not alpha.dominance_override_applied
    assert alpha.selection_reason == "rotated_out_by_reselection_cooldown"
    assert selection.selected_company_keys == ("beta", "gamma")


def test_extreme_nminus1_dominance_overrides_active_cooldown() -> None:
    observations = [_observation("hdi", 25, 1, "HDI AG")]
    cooldown = CompanyReselectionState(
        company_key="hdi",
        cooldown_until=NOW + timedelta(days=6),
        last_filtered_at=NOW - timedelta(hours=12),
    )

    selection = select_next_run_filters(
        observations=observations,
        reselection_states=[cooldown],
        policy=POLICY,
        now=NOW,
    )

    item = selection.selected_items[0]
    assert item.company_key == "hdi"
    assert item.filter_alias == "HDI"
    assert item.card_count == 25
    assert item.card_share == 1.0
    assert item.cooldown_active
    assert item.dominance_override_applied
    assert item.selection_reason == "selected_by_nminus1_dominance_override"


def test_selection_is_bounded_but_not_static() -> None:
    first_run = [_observation(f"company_{index}", 10 - index, index) for index in range(1, 8)]
    second_run = [_observation(f"other_{index}", 10 - index, index) for index in range(1, 8)]

    first = select_next_run_filters(
        observations=first_run,
        reselection_states=[],
        policy=POLICY,
        now=NOW,
    )
    second = select_next_run_filters(
        observations=second_run,
        reselection_states=[],
        policy=POLICY,
        now=NOW,
    )

    assert first.selected_filter_count == 5
    assert second.selected_filter_count == 5
    assert first.selected_company_keys != second.selected_company_keys
    assert all(key.startswith("company_") for key in first.selected_company_keys)
    assert all(key.startswith("other_") for key in second.selected_company_keys)


def test_capacity_plan_requires_validated_transport() -> None:
    selection = select_next_run_filters(
        observations=[_observation(f"company_{index}", 10 - index, index) for index in range(1, 6)],
        reselection_states=[],
        policy=POLICY,
        now=NOW,
    )

    with pytest.raises(ValueError, match="validated transport"):
        build_filter_capacity_experiment_plan(
            selection=selection,
            transport_name="encoded_q",
            transport_status="candidate",
            maximum_filter_count=5,
            request_budget=11,
        )


def test_capacity_plan_measures_every_length_with_permutation_control() -> None:
    selection = select_next_run_filters(
        observations=[_observation(f"company_{index}", 10 - index, index) for index in range(1, 6)],
        reselection_states=[],
        policy=POLICY,
        now=NOW,
    )

    plan = build_filter_capacity_experiment_plan(
        selection=selection,
        transport_name="encoded_q",
        transport_status="validated",
        maximum_filter_count=5,
        request_budget=11,
    )

    assert plan.maximum_filter_count == 5
    assert plan.filtered_request_count == 9
    assert plan.required_total_request_count == 11
    assert [trial.filter_count for trial in plan.trials].count(1) == 1
    for filter_count in range(2, 6):
        trials = [trial for trial in plan.trials if trial.filter_count == filter_count]
        assert {trial.permutation_name for trial in trials} == {"forward", "reverse"}
        assert trials[0].company_keys == tuple(reversed(trials[1].company_keys))


def test_capacity_plan_enforces_request_budget() -> None:
    selection = select_next_run_filters(
        observations=[_observation(f"company_{index}", 10 - index, index) for index in range(1, 6)],
        reselection_states=[],
        policy=POLICY,
        now=NOW,
    )

    with pytest.raises(ValueError, match="required_total=11"):
        build_filter_capacity_experiment_plan(
            selection=selection,
            transport_name="encoded_q",
            transport_status="validated",
            maximum_filter_count=5,
            request_budget=10,
        )
