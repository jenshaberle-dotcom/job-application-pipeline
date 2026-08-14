from __future__ import annotations

import argparse
from typing import Mapping

import pytest

import scripts.run_origin_url_search_first_repair as cascade
from src.search_intelligence.origin_url_default_repair import stage_from_discovery


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "company_key": ["example"],
        "operator_url": [],
        "target_location": "Hannover",
        "target_locale": "de",
        "reviewed_by": "test",
        "timeout_seconds": 1.0,
        "max_url_candidates": 12,
        "market_evidence_limit": 30,
        "search_query_limit": 5,
        "initial_search_query_limit": 5,
        "domain_followup_query_limit": 3,
        "max_brand_host_hypotheses": 6,
        "max_adaptive_candidates": 18,
        "search_max_results": 5,
        "search_timeout_seconds": 1.0,
        "search_depth": "advanced",
        "search_results_json": None,
        "max_evidence_candidates": 4,
        "max_evidence_http_requests": 12,
        "evidence_timeout_seconds": 1.0,
        "max_response_bytes": 100_000,
        "llm_model": "gpt-5.4-mini",
        "llm_reasoning_effort": "low",
        "llm_max_output_tokens": 600,
        "llm_reserved_input_tokens": 5000,
        "llm_timeout_seconds": 1.0,
        "max_estimated_llm_cost_usd_per_company": 0.01,
        "search_llm_model": "gpt-5.6-luna",
        "search_llm_escalation_model": "gpt-5.6-terra",
        "search_llm_sol_model": "gpt-5.6-sol",
        "search_llm_max_model": "gpt-5.6-luna",
        "search_llm_reasoning_effort": "medium",
        "search_llm_max_reasoning_effort": "max",
        "search_llm_max_output_tokens": 500,
        "search_llm_max_reasoning_output_tokens": 6000,
        "search_llm_reserved_input_tokens": 3500,
        "search_llm_timeout_seconds": 1.0,
        "search_llm_max_reasoning_timeout_seconds": 1.0,
        "max_search_llm_cost_usd_per_company": 0.01,
        "max_search_llm_escalation_cost_usd_per_company": 0.02,
        "max_search_llm_sol_cost_usd_per_company": 0.05,
        "max_search_llm_max_cost_usd_per_company": 0.05,
        "disable_tavily": False,
        "disable_llm": False,
        "tavily_remaining_credits": 10,
        "tavily_provider_unavailable": False,
        "output_dir": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _baseline() -> dict[str, object]:
    return {
        "company_key": "example",
        "company_name": "Example GmbH",
        "decision": "not_found",
        "selected_url": None,
        "confidence_score": 0.2,
        "candidate_count": 0,
        "reason": "no deterministic origin",
        "alternatives": [],
        "rejected": [],
        "search_results": [],
    }


def _selected(url: str) -> dict[str, object]:
    return {
        "company_key": "example",
        "company_name": "Example GmbH",
        "decision": "origin_url_candidate_selected",
        "selected_url": url,
        "confidence_score": 1.0,
        "candidate_count": 1,
        "reason": "deterministically validated origin",
        "alternatives": [{"url": url}],
        "rejected": [],
        "search_results": [{"url": url}],
    }


def _install_deterministic_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )


def _install_luna_success(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def fake_stage(args, **kwargs):  # type: ignore[no-untyped-def]
        stage_name = str(kwargs["stage_name"])
        calls.append(stage_name)
        payload = (
            _selected("https://careers.example.com/")
            if stage_name == cascade.PRIMARY_STAGE
            else _baseline()
        )
        return (
            stage_from_discovery(stage_name, payload, provider_request_count=1),
            payload,
            {"model": kwargs["model"], "status": "completed"},
            (),
        )

    monkeypatch.setattr(
        cascade.empirical.model_first,
        "_run_direct_model_stage",
        fake_stage,
    )
    return calls


def test_deterministic_success_skips_tavily_and_all_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _selected("https://jobs.example.com/"),
    )
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_search_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tavily must not run after deterministic success")
        ),
    )
    monkeypatch.setattr(
        cascade.empirical.model_first,
        "_run_direct_model_stage",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("models must not run after deterministic success")
        ),
    )

    payload = cascade.run_default_repair_for_company(_args(), "example")
    repair = payload["default_repair"]
    assert isinstance(repair, Mapping)
    assert repair["selected_url"] == "https://jobs.example.com/"
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages["tavily_repair"]["attempted"] is False
    for name in cascade.MODEL_STAGE_NAMES:
        assert stages[name]["attempted"] is False


def test_tavily_success_precedes_and_skips_all_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_deterministic_miss(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        providers = {str(row.get("provider") or "") for row in rows}
        if "tavily_adaptive_search" in providers:
            return _selected("https://careers.example.com/")
        return _baseline()

    monkeypatch.setattr(cascade.empirical.adaptive, "_run_atomic_with_rows", fake_atomic)
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_search_rows",
        lambda args, **kwargs: (
            [
                {
                    "company_key": "example",
                    "url": "https://careers.example.com/",
                    "provider": "tavily_adaptive_search",
                    "title": "Careers",
                    "snippet": "Official careers",
                    "query": "Example GmbH careers",
                }
            ],
            1,
        ),
    )
    monkeypatch.setattr(
        cascade.empirical.model_first,
        "_run_direct_model_stage",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tavily success must skip all model stages")
        ),
    )

    payload = cascade.run_default_repair_for_company(
        _args(tavily_remaining_credits=2),
        "example",
    )
    repair = payload["default_repair"]
    assert isinstance(repair, Mapping)
    names = [stage["name"] for stage in repair["stages"]]
    assert names[:3] == [
        "deterministic_baseline",
        "deterministic_symbol_brand",
        "tavily_repair",
    ]
    assert repair["selected_stage"] == "tavily_repair"
    stages = {stage["name"]: stage for stage in repair["stages"]}
    for name in cascade.MODEL_STAGE_NAMES:
        assert stages[name]["attempted"] is False
    assert payload["search_first_origin_cascade"]["canonical"] is True
    assert payload["search_first_origin_cascade"]["pro_mode_enabled"] is False


def test_insufficient_advanced_credit_skips_tavily_and_continues_to_luna(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_deterministic_miss(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_run_atomic_with_rows",
        lambda args, *, company_key, rows: _baseline(),
    )
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_search_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("one advanced credit must not fund a Tavily request")
        ),
    )
    calls = _install_luna_success(monkeypatch)

    payload = cascade.run_default_repair_for_company(
        _args(tavily_remaining_credits=1),
        "example",
    )
    repair = payload["default_repair"]
    assert isinstance(repair, Mapping)
    names = [stage["name"] for stage in repair["stages"]]
    assert names.index("tavily_repair") < names.index(cascade.PRIMARY_STAGE)
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages["tavily_repair"]["attempted"] is False
    assert calls == [cascade.PRIMARY_STAGE]
    assert repair["selected_stage"] == cascade.PRIMARY_STAGE


@pytest.mark.parametrize(
    ("overrides", "expected_state"),
    [
        ({"tavily_remaining_credits": None}, "unknown"),
        ({"disable_tavily": True}, "disabled"),
        ({"tavily_provider_unavailable": True}, "provider_unavailable"),
    ],
)
def test_non_available_tavily_states_still_allow_luna(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
    expected_state: str,
) -> None:
    _install_deterministic_miss(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_run_atomic_with_rows",
        lambda args, *, company_key, rows: _baseline(),
    )
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_search_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unavailable Tavily state must not call search")
        ),
    )
    calls = _install_luna_success(monkeypatch)

    payload = cascade.run_default_repair_for_company(_args(**overrides), "example")
    plan = payload["default_repair"]["trace"]["search_first_plan"]
    assert plan["tavily_budget"]["state"] == expected_state
    assert calls == [cascade.PRIMARY_STAGE]


def test_advanced_credit_budget_caps_actual_search_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_deterministic_miss(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_run_atomic_with_rows",
        lambda args, *, company_key, rows: _baseline(),
    )
    seen_queries: list[str] = []

    def fake_search(args, *, company_key, queries, ledger, maximum_results):  # type: ignore[no-untyped-def]
        seen_queries.extend(str(query) for query in queries)
        return [], len(queries)

    monkeypatch.setattr(cascade.empirical.adaptive, "_search_rows", fake_search)
    _install_luna_success(monkeypatch)

    payload = cascade.run_default_repair_for_company(
        _args(tavily_remaining_credits=2),
        "example",
    )
    assert len(seen_queries) == 1
    trace = payload["default_repair"]["trace"]["search_first_tavily_round"]
    assert trace["provider_requests"] == 1
    assert trace["credits_consumed"] == 2
    assert trace["budget"]["affordable_max_requests"] == 1


def test_one_progress_ledger_spans_tavily_and_model_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_deterministic_miss(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    ledger_ids: list[int] = []

    monkeypatch.setattr(
        cascade.empirical.adaptive,
        "_run_atomic_with_rows",
        lambda args, *, company_key, rows: _baseline(),
    )

    def fake_search(args, *, company_key, queries, ledger, maximum_results):  # type: ignore[no-untyped-def]
        ledger_ids.append(id(ledger))
        return [], min(1, len(queries))

    monkeypatch.setattr(cascade.empirical.adaptive, "_search_rows", fake_search)

    def fake_stage(args, **kwargs):  # type: ignore[no-untyped-def]
        ledger_ids.append(id(kwargs["ledger"]))
        payload = _selected("https://careers.example.com/")
        return (
            stage_from_discovery(
                str(kwargs["stage_name"]), payload, provider_request_count=1
            ),
            payload,
            {"status": "completed"},
            (),
        )

    monkeypatch.setattr(
        cascade.empirical.model_first,
        "_run_direct_model_stage",
        fake_stage,
    )

    cascade.run_default_repair_for_company(
        _args(tavily_remaining_credits=2),
        "example",
    )
    assert ledger_ids
    assert len(set(ledger_ids)) == 1
