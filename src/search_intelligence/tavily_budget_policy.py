"""Pure Tavily budget policy for LLM-BOOST-001.

Runtime/provider code may supply current credit telemetry. This module only
classifies whether the next bounded search is fundable; it performs no provider
request and owns no product authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.search_intelligence.llm_booster_policy import TavilyState


@dataclass(frozen=True)
class TavilyBudgetDecision:
    state: TavilyState
    next_request_credits: int
    remaining_credits: int | None
    reason: str
    product_authority: bool = False

    @property
    def search_allowed(self) -> bool:
        return self.state == TavilyState.AVAILABLE

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["search_allowed"] = self.search_allowed
        return payload


def search_credit_cost(search_depth: str) -> int:
    """Return the bounded credit cost used by the current Tavily search path."""

    return 1 if str(search_depth or "").strip().lower() == "basic" else 2


def classify_tavily_budget(
    *,
    search_depth: str,
    remaining_credits: int | None,
    explicitly_disabled: bool = False,
    key_available: bool = True,
    provider_available: bool = True,
) -> TavilyBudgetDecision:
    credits = search_credit_cost(search_depth)
    if explicitly_disabled:
        return TavilyBudgetDecision(
            state=TavilyState.DISABLED,
            next_request_credits=credits,
            remaining_credits=remaining_credits,
            reason="Tavily disabled by explicit runtime policy.",
        )
    if not key_available:
        return TavilyBudgetDecision(
            state=TavilyState.MISSING_KEY,
            next_request_credits=credits,
            remaining_credits=remaining_credits,
            reason="Tavily key unavailable at runtime boundary.",
        )
    if not provider_available:
        return TavilyBudgetDecision(
            state=TavilyState.PROVIDER_UNAVAILABLE,
            next_request_credits=credits,
            remaining_credits=remaining_credits,
            reason="Tavily provider unavailable at runtime boundary.",
        )
    if remaining_credits is None:
        return TavilyBudgetDecision(
            state=TavilyState.UNKNOWN,
            next_request_credits=credits,
            remaining_credits=None,
            reason="Current Tavily credit telemetry is unknown.",
        )

    remaining = max(0, int(remaining_credits))
    if remaining == 0:
        state = TavilyState.BUDGET_EXHAUSTED
        reason = "Tavily credit budget is exhausted."
    elif remaining < credits:
        state = TavilyState.INSUFFICIENT_BUDGET
        reason = (
            f"Tavily has {remaining} credit(s) remaining but the next "
            f"{search_depth} search requires {credits}."
        )
    else:
        state = TavilyState.AVAILABLE
        reason = (
            f"Tavily has {remaining} credit(s) remaining and the next "
            f"search requires {credits}."
        )
    return TavilyBudgetDecision(
        state=state,
        next_request_credits=credits,
        remaining_credits=remaining,
        reason=reason,
    )
