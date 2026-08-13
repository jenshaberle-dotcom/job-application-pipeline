from __future__ import annotations

import pytest

from src.search_intelligence.llm_booster_policy import (
    CANONICAL_STAGE_ORDER,
    EMPIRICAL_EXPECTED_COST_USD,
    HARD_COST_CEILING_USD,
    BoosterStage,
    BoosterSurface,
    TavilyState,
    build_booster_plan,
    eligible_stage_names,
    origin_empirical_expected_model_cost_usd,
    recurring_evidence_fingerprint,
    stage_names,
)


def test_search_precedes_models() -> None:
    assert CANONICAL_STAGE_ORDER == (
        BoosterStage.DETERMINISTIC,
        BoosterStage.TAVILY,
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    )
    assert "pro" not in " ".join(stage.value for stage in CANONICAL_STAGE_ORDER)


@pytest.mark.parametrize(
    "state",
    [
        TavilyState.DISABLED,
        TavilyState.MISSING_KEY,
        TavilyState.BUDGET_EXHAUSTED,
        TavilyState.INSUFFICIENT_BUDGET,
        TavilyState.PROVIDER_UNAVAILABLE,
        TavilyState.UNKNOWN,
    ],
)
def test_unavailable_search_never_blocks_luna(state: TavilyState) -> None:
    plan = build_booster_plan(
        surface=BoosterSurface.ORIGIN_DISCOVERY,
        tavily_state=state,
    )
    stages = {item.stage: item for item in plan.stages}
    assert stages[BoosterStage.TAVILY].eligible is False
    assert stages[BoosterStage.LUNA_MEDIUM].eligible is True
    assert stages[BoosterStage.TERRA_MEDIUM].eligible is True
    assert stages[BoosterStage.SOL_MEDIUM].eligible is True
    assert stages[BoosterStage.LUNA_MAX].eligible is True


def test_available_search_is_first_provider_stage() -> None:
    plan = build_booster_plan(
        surface=BoosterSurface.ORIGIN_DISCOVERY,
        tavily_state=TavilyState.AVAILABLE,
    )
    assert stage_names(plan) == tuple(item.value for item in CANONICAL_STAGE_ORDER)
    assert eligible_stage_names(plan)[:3] == (
        BoosterStage.DETERMINISTIC.value,
        BoosterStage.TAVILY.value,
        BoosterStage.LUNA_MEDIUM.value,
    )


def test_known_surfaces_search_only_on_external_information_gap() -> None:
    ordinary = build_booster_plan(
        surface=BoosterSurface.DETAIL_SEMANTICS,
        tavily_state=TavilyState.AVAILABLE,
    )
    with_gap = build_booster_plan(
        surface=BoosterSurface.DETAIL_SEMANTICS,
        tavily_state=TavilyState.AVAILABLE,
        external_information_gap=True,
    )
    ordinary_search = ordinary.stages[1]
    gap_search = with_gap.stages[1]
    assert ordinary_search.stage == BoosterStage.TAVILY
    assert ordinary_search.eligible is False
    assert ordinary_search.reason_code == "external_search_not_indicated"
    assert gap_search.eligible is True


def test_deterministic_success_skips_all_boosters() -> None:
    plan = build_booster_plan(
        surface=BoosterSurface.ATS_DELEGATION,
        tavily_state=TavilyState.AVAILABLE,
        deterministic_resolved=True,
        external_information_gap=True,
    )
    assert plan.stages[0].eligible is True
    assert all(item.eligible is False for item in plan.stages[1:])


def test_unchanged_recurring_evidence_has_zero_provider_plan() -> None:
    plan = build_booster_plan(
        surface=BoosterSurface.RECURRING_CONNECTOR,
        tavily_state=TavilyState.AVAILABLE,
        external_information_gap=True,
        recurring_unchanged_fingerprint=True,
    )
    assert eligible_stage_names(plan) == (BoosterStage.DETERMINISTIC.value,)
    payload = plan.to_json()
    assert payload["provider_network_requests"] == 0
    assert payload["llm_requests"] == 0
    assert payload["database_requests"] == 0
    assert payload["product_writes"] == 0
    assert payload["product_authority"] is False


def test_empirical_means_remain_below_hard_caps() -> None:
    assert EMPIRICAL_EXPECTED_COST_USD[BoosterStage.LUNA_MEDIUM] == 0.00494
    assert EMPIRICAL_EXPECTED_COST_USD[BoosterStage.TERRA_MEDIUM] == 0.01124
    assert EMPIRICAL_EXPECTED_COST_USD[BoosterStage.SOL_MEDIUM] == 0.02650
    assert EMPIRICAL_EXPECTED_COST_USD[BoosterStage.LUNA_MAX] == 0.01538
    for stage, mean in EMPIRICAL_EXPECTED_COST_USD.items():
        assert mean < HARD_COST_CEILING_USD[stage]


def test_origin_expected_model_cost_uses_measured_reach_rates() -> None:
    expected = 0.00494 + (7 / 17) * 0.01124 + (5 / 17) * 0.02650 + (4 / 17) * 0.01538
    assert origin_empirical_expected_model_cost_usd() == pytest.approx(expected)


def test_recurring_fingerprint_is_stable_and_changes_with_evidence() -> None:
    first = recurring_evidence_fingerprint(
        connector_id="connector-a",
        source_job_identity="job-123",
        normalized_evidence_hash="abc123",
    )
    same = recurring_evidence_fingerprint(
        connector_id="connector-a",
        source_job_identity="job-123",
        normalized_evidence_hash="abc123",
    )
    changed = recurring_evidence_fingerprint(
        connector_id="connector-a",
        source_job_identity="job-123",
        normalized_evidence_hash="def456",
    )
    assert first == same
    assert first != changed
    assert len(first) == 64


def test_models_never_have_product_authority() -> None:
    for surface in BoosterSurface:
        plan = build_booster_plan(
            surface=surface,
            tavily_state=TavilyState.AVAILABLE,
            external_information_gap=True,
        )
        assert all(item.product_authority is False for item in plan.stages)
