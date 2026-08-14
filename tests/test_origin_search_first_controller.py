from __future__ import annotations

from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState
from src.search_intelligence.origin_search_first_controller import (
    build_origin_search_first_plan,
)


def _plan(**overrides: object):  # type: ignore[no-untyped-def]
    values: dict[str, object] = {
        "search_depth": "advanced",
        "remaining_credits": 10,
        "explicitly_disabled": False,
        "key_available": True,
        "provider_available": True,
        "initial_query_limit": 5,
        "followup_query_limit": 3,
    }
    values.update(overrides)
    return build_origin_search_first_plan(**values)  # type: ignore[arg-type]


def test_advanced_search_requires_two_credits() -> None:
    insufficient = _plan(remaining_credits=1)
    assert insufficient.tavily_budget.state == TavilyState.INSUFFICIENT_BUDGET
    assert insufficient.affordable_max_requests == 0
    assert insufficient.tavily_search_allowed is False

    one_request = _plan(remaining_credits=2)
    assert one_request.tavily_budget.state == TavilyState.AVAILABLE
    assert one_request.affordable_max_requests == 1
    assert one_request.tavily_search_allowed is True


def test_basic_search_uses_one_credit_per_request() -> None:
    plan = _plan(search_depth="basic", remaining_credits=3)
    assert plan.tavily_budget.next_request_credits == 1
    assert plan.affordable_max_requests == 3


def test_zero_unknown_and_disabled_budget_states_skip_search() -> None:
    exhausted = _plan(remaining_credits=0)
    unknown = _plan(remaining_credits=None)
    disabled = _plan(explicitly_disabled=True)

    assert exhausted.tavily_budget.state == TavilyState.BUDGET_EXHAUSTED
    assert unknown.tavily_budget.state == TavilyState.UNKNOWN
    assert disabled.tavily_budget.state == TavilyState.DISABLED
    for plan in (exhausted, unknown, disabled):
        assert plan.affordable_max_requests == 0
        assert plan.tavily_search_allowed is False


def test_missing_key_and_provider_unavailable_do_not_remove_model_stages() -> None:
    missing = _plan(key_available=False)
    unavailable = _plan(provider_available=False)

    assert missing.tavily_budget.state == TavilyState.MISSING_KEY
    assert unavailable.tavily_budget.state == TavilyState.PROVIDER_UNAVAILABLE
    for plan in (missing, unavailable):
        stages = tuple(stage.stage for stage in plan.booster_plan.stages)
        assert stages == (
            BoosterStage.DETERMINISTIC,
            BoosterStage.TAVILY,
            BoosterStage.LUNA_MEDIUM,
            BoosterStage.TERRA_MEDIUM,
            BoosterStage.SOL_MEDIUM,
            BoosterStage.LUNA_MAX,
            BoosterStage.DEEP_EVIDENCE,
        )
        eligible = {
            stage.stage: stage.eligible for stage in plan.booster_plan.stages
        }
        assert eligible[BoosterStage.TAVILY] is False
        assert eligible[BoosterStage.LUNA_MEDIUM] is True
        assert eligible[BoosterStage.TERRA_MEDIUM] is True
        assert eligible[BoosterStage.SOL_MEDIUM] is True
        assert eligible[BoosterStage.LUNA_MAX] is True


def test_request_budget_is_bounded_by_configuration_and_credits() -> None:
    credit_bounded = _plan(remaining_credits=6)
    assert credit_bounded.configured_max_requests == 8
    assert credit_bounded.affordable_max_requests == 3
    assert credit_bounded.remaining_request_slots(0) == 3
    assert credit_bounded.remaining_request_slots(2) == 1
    assert credit_bounded.remaining_request_slots(5) == 0

    config_bounded = _plan(
        search_depth="basic",
        remaining_credits=100,
        initial_query_limit=2,
        followup_query_limit=1,
    )
    assert config_bounded.configured_max_requests == 3
    assert config_bounded.affordable_max_requests == 3


def test_plan_is_report_only_and_has_no_product_authority() -> None:
    plan = _plan()
    payload = plan.to_json()
    assert payload["product_authority"] is False
    assert plan.booster_plan.product_authority is False
    assert plan.booster_plan.provider_network_requests == 0
    assert plan.booster_plan.llm_requests == 0
    assert plan.booster_plan.product_writes == 0
