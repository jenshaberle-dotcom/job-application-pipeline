from __future__ import annotations

import argparse
from typing import Mapping

import pytest

import scripts.run_origin_url_empirical_cascade as cascade
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
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
        "search_llm_reserved_input_tokens": 3500,
        "search_llm_timeout_seconds": 1.0,
        "search_llm_max_timeout_seconds": 1.0,
        "max_search_llm_cost_usd_per_company": 0.01,
        "max_search_llm_escalation_cost_usd_per_company": 0.02,
        "max_search_llm_sol_cost_usd_per_company": 0.05,
        "max_search_llm_max_cost_usd_per_company": 0.05,
        "disable_tavily": True,
        "disable_llm": False,
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
        cascade.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )
    monkeypatch.setattr(
        cascade.adaptive,
        "_run_atomic_with_rows",
        lambda args, *, company_key, rows: _baseline(),
    )


def test_parser_defaults_match_measured_production_order() -> None:
    args = cascade.build_parser().parse_args(["--company-key", "example"])
    assert args.search_llm_model == "gpt-5.6-luna"
    assert args.search_llm_escalation_model == "gpt-5.6-terra"
    assert args.search_llm_sol_model == "gpt-5.6-sol"
    assert args.search_llm_max_model == "gpt-5.6-luna"
    assert args.search_llm_reasoning_effort == "medium"
    assert args.search_llm_max_reasoning_effort == "max"
    assert args.search_llm_max_output_tokens == 6000


def test_price_reservations_cover_all_empirical_models() -> None:
    assert MODEL_PRICES_USD_PER_MILLION["gpt-5.6-luna"] == (1.0, 6.0)
    assert MODEL_PRICES_USD_PER_MILLION["gpt-5.6-terra"] == (2.5, 15.0)
    assert MODEL_PRICES_USD_PER_MILLION["gpt-5.6-sol"] == (5.0, 30.0)
    assert cascade.adaptive._reserved_cost_usd(
        model="gpt-5.6-luna",
        reserved_input_tokens=3500,
        max_output_tokens=500,
    ) == pytest.approx(0.0065)
    assert cascade.adaptive._reserved_cost_usd(
        model="gpt-5.6-sol",
        reserved_input_tokens=3500,
        max_output_tokens=500,
    ) == pytest.approx(0.0325)
    assert cascade.adaptive._reserved_cost_usd(
        model="gpt-5.6-luna",
        reserved_input_tokens=3500,
        max_output_tokens=6000,
    ) == pytest.approx(0.0395)


def test_medium_models_then_luna_max_share_one_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_deterministic_miss(monkeypatch)
    calls: list[tuple[str, str, str, int]] = []
    ledger_ids: list[int] = []
    duplicate_visibility: list[int] = []

    def fake_stage(args, **kwargs):  # type: ignore[no-untyped-def]
        model = str(kwargs["model"])
        stage_name = str(kwargs["stage_name"])
        ledger = kwargs["ledger"]
        ledger_ids.append(id(ledger))
        duplicate_visibility.append(
            len(ledger.novel_urls(["https://careers.example.com/"]))
        )
        calls.append(
            (
                stage_name,
                model,
                str(args.search_llm_reasoning_effort),
                int(args.search_llm_max_output_tokens),
            )
        )
        if stage_name == cascade.MAX_STAGE:
            payload = _selected("https://careers.example.com/")
        else:
            payload = _baseline()
        return (
            stage_from_discovery(stage_name, payload, provider_request_count=1),
            payload,
            {"model": model, "status": "completed"},
            (f"query-{stage_name}",),
        )

    monkeypatch.setattr(cascade.model_first, "_run_direct_model_stage", fake_stage)

    payload = cascade.run_default_repair_for_company(_args(), "example")
    repair = payload["default_repair"]
    assert isinstance(repair, Mapping)
    assert repair["selected_stage"] == cascade.MAX_STAGE
    assert repair["selected_url"] == "https://careers.example.com/"
    assert calls == [
        (cascade.PRIMARY_STAGE, "gpt-5.6-luna", "medium", 500),
        (cascade.TERRA_STAGE, "gpt-5.6-terra", "medium", 500),
        (cascade.SOL_STAGE, "gpt-5.6-sol", "medium", 500),
        (cascade.MAX_STAGE, "gpt-5.6-luna", "max", 6000),
    ]
    assert len(set(ledger_ids)) == 1
    assert duplicate_visibility == [1, 0, 0, 0]
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages["tavily_repair"]["attempted"] is False
    assert payload["empirical_origin_cascade"]["pro_mode_enabled"] is False


def test_sol_success_stops_before_max_and_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_deterministic_miss(monkeypatch)
    calls: list[str] = []

    def fake_stage(args, **kwargs):  # type: ignore[no-untyped-def]
        stage_name = str(kwargs["stage_name"])
        calls.append(stage_name)
        payload = (
            _selected("https://jobs.example.com/")
            if stage_name == cascade.SOL_STAGE
            else _baseline()
        )
        return (
            stage_from_discovery(stage_name, payload, provider_request_count=1),
            payload,
            {"model": kwargs["model"], "status": "completed"},
            (),
        )

    monkeypatch.setattr(cascade.model_first, "_run_direct_model_stage", fake_stage)
    payload = cascade.run_default_repair_for_company(_args(), "example")
    repair = payload["default_repair"]
    assert calls == [cascade.PRIMARY_STAGE, cascade.TERRA_STAGE, cascade.SOL_STAGE]
    assert repair["selected_stage"] == cascade.SOL_STAGE
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages[cascade.MAX_STAGE]["attempted"] is False
    assert stages["tavily_repair"]["attempted"] is False


def test_explicit_llm_disable_skips_all_four_model_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_deterministic_miss(monkeypatch)
    monkeypatch.setattr(
        cascade.model_first,
        "_run_direct_model_stage",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("no model stage may run when LLM is disabled")
        ),
    )

    payload = cascade.run_default_repair_for_company(
        _args(disable_llm=True, disable_tavily=True),
        "example",
    )
    repair = payload["default_repair"]
    stages = {stage["name"]: stage for stage in repair["stages"]}
    for name in cascade.MODEL_STAGE_NAMES:
        assert stages[name]["attempted"] is False
        assert stages[name]["status"] == "skipped"
    assert stages["tavily_repair"]["status"] == "configuration_blocked"
    assert payload["empirical_origin_cascade"]["pro_mode_enabled"] is False
