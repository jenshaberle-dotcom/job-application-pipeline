from __future__ import annotations

from types import SimpleNamespace

from scripts import run_origin_url_budgeted_audit as budgeted


def test_zero_llm_budget_does_not_exhaust_tavily_phase() -> None:
    args = SimpleNamespace(
        disable_llm=True,
        max_llm_requests=0,
        max_provider_requests=40,
    )

    assert (
        budgeted._phase_b_budget_exhausted(
            args,
            provider_total=0,
            llm_total=0,
        )
        is False
    )
    assert (
        budgeted._phase_b_budget_exhausted(
            args,
            provider_total=40,
            llm_total=0,
        )
        is True
    )


def test_zero_llm_ceiling_disables_llm_in_provider_phase(monkeypatch) -> None:
    monkeypatch.setattr(
        budgeted.legacy,
        "repair_args",
        lambda args: SimpleNamespace(disable_tavily=False, disable_llm=False),
    )
    args = SimpleNamespace(disable_llm=False, max_llm_requests=0)

    repair = budgeted._repair_args(
        args,
        operator_urls=(),
        deterministic_only=False,
    )

    assert repair.disable_tavily is False
    assert repair.disable_llm is True


def test_positive_active_llm_ceiling_keeps_conservative_guard() -> None:
    args = SimpleNamespace(
        disable_llm=False,
        max_llm_requests=2,
        max_provider_requests=40,
    )

    assert (
        budgeted._phase_b_budget_exhausted(
            args,
            provider_total=5,
            llm_total=1,
        )
        is False
    )
    assert (
        budgeted._phase_b_budget_exhausted(
            args,
            provider_total=5,
            llm_total=2,
        )
        is True
    )
