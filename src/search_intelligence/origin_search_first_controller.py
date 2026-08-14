"""Pure origin search-first controller policy for LLM-BOOST-001.

The module turns current runtime-supplied Tavily telemetry into an exact,
bounded origin escalation plan. It performs no provider request and owns no
product authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.search_intelligence.llm_booster_policy import (
    BOOSTER_CONTRACT_VERSION,
    BoosterPlan,
    BoosterSurface,
    build_booster_plan,
)
from src.search_intelligence.tavily_budget_policy import (
    TavilyBudgetDecision,
    classify_tavily_budget,
)


@dataclass(frozen=True)
class OriginSearchFirstPlan:
    contract_version: str
    tavily_budget: TavilyBudgetDecision
    booster_plan: BoosterPlan
    configured_max_requests: int
    affordable_max_requests: int
    product_authority: bool = False

    @property
    def tavily_search_allowed(self) -> bool:
        return self.tavily_budget.search_allowed and self.affordable_max_requests > 0

    def remaining_request_slots(self, requests_made: int) -> int:
        return max(0, self.affordable_max_requests - max(0, int(requests_made)))

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "tavily_budget": self.tavily_budget.to_json(),
            "stage_order": [
                stage.stage.value for stage in self.booster_plan.stages
            ],
            "configured_max_requests": self.configured_max_requests,
            "affordable_max_requests": self.affordable_max_requests,
            "tavily_search_allowed": self.tavily_search_allowed,
            "product_authority": self.product_authority,
        }


def build_origin_search_first_plan(
    *,
    search_depth: str,
    remaining_credits: int | None,
    explicitly_disabled: bool,
    key_available: bool,
    provider_available: bool,
    initial_query_limit: int,
    followup_query_limit: int,
) -> OriginSearchFirstPlan:
    """Build the bounded Tavily-first origin plan from sanitized telemetry."""

    decision = classify_tavily_budget(
        search_depth=search_depth,
        remaining_credits=remaining_credits,
        explicitly_disabled=explicitly_disabled,
        key_available=key_available,
        provider_available=provider_available,
    )
    booster_plan = build_booster_plan(
        surface=BoosterSurface.ORIGIN_DISCOVERY,
        tavily_state=decision.state,
    )
    configured = max(0, int(initial_query_limit)) + max(0, int(followup_query_limit))
    affordable = 0
    if decision.search_allowed and decision.remaining_credits is not None:
        affordable = min(
            configured,
            decision.remaining_credits // decision.next_request_credits,
        )
    return OriginSearchFirstPlan(
        contract_version=BOOSTER_CONTRACT_VERSION,
        tavily_budget=decision,
        booster_plan=booster_plan,
        configured_max_requests=configured,
        affordable_max_requests=affordable,
    )


__all__ = [
    "OriginSearchFirstPlan",
    "build_origin_search_first_plan",
]
