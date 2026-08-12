from __future__ import annotations

import argparse
from typing import Mapping, Sequence

import scripts.run_origin_url_staged_repair as staged
from src.search_intelligence.adaptive_origin_search import SearchHypothesisSet
from src.search_intelligence.origin_search_hypothesis_provider import (
    SearchHypothesisObservation,
)


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "company_key": ["1_1"],
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
        "operator_url": [],
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
        "search_llm_model": "gpt-5.4-mini",
        "search_llm_escalation_model": "gpt-5.5",
        "search_llm_reasoning_effort": "low",
        "search_llm_max_output_tokens": 500,
        "search_llm_reserved_input_tokens": 3500,
        "search_llm_timeout_seconds": 1.0,
        "max_search_llm_cost_usd_per_company": 0.01,
        "max_search_llm_escalation_cost_usd_per_company": 0.05,
        "disable_tavily": False,
        "disable_llm": False,
        "output_dir": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _baseline() -> dict[str, object]:
    return {
        "company_key": "1_1",
        "company_name": "1&1",
        "decision": "not_found",
        "selected_url": None,
        "confidence_score": 0.83,
        "candidate_count": 6,
        "reason": "best candidate remained below selection threshold",
        "alternatives": [],
        "rejected": [],
        "search_results": [],
    }


def _selected(url: str) -> dict[str, object]:
    return {
        "company_key": "1_1",
        "company_name": "1&1",
        "decision": "origin_url_candidate_selected",
        "selected_url": url,
        "confidence_score": 1.0,
        "candidate_count": 1,
        "reason": "validated company identity and career surface",
        "alternatives": [{"url": url}],
        "rejected": [],
        "search_results": [{"url": url}],
    }


def _observation(
    model: str,
    *,
    queries: Sequence[str] = (),
    urls: Sequence[str] = (),
) -> SearchHypothesisObservation:
    return SearchHypothesisObservation(
        status="completed",
        request_attempted=True,
        model=model,
        response_id=f"resp-{model}",
        latency_ms=1,
        estimated_cost_usd=0.001,
        packet_sha256="a" * 64,
        hypotheses=SearchHypothesisSet(
            queries=tuple(queries),
            urls=tuple(urls),
            rationale="bounded test hypotheses",
        ),
    )


def _failed_observation(model: str) -> SearchHypothesisObservation:
    return SearchHypothesisObservation(
        status="failed_closed",
        request_attempted=True,
        model=model,
        response_id=None,
        latency_ms=1,
        estimated_cost_usd=0.0,
        packet_sha256="b" * 64,
        hypotheses=None,
        failure_class="RuntimeError",
        failure_message="test provider failure",
    )


def _providers(rows: Sequence[Mapping[str, object]]) -> set[str]:
    return {str(row.get("provider") or "") for row in rows}


def test_deterministic_symbol_brand_hit_skips_every_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )
    atomic_rows: list[Sequence[Mapping[str, object]]] = []

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        atomic_rows.append(rows)
        return _selected("https://career.1and1.org/")

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)
    monkeypatch.setattr(
        staged.adaptive,
        "request_search_hypotheses",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("LLM must not run after deterministic selection")
        ),
    )
    monkeypatch.setattr(
        staged.adaptive,
        "_search_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tavily must not run after deterministic selection")
        ),
    )

    payload = staged.run_default_repair_for_company(_args(), "1_1")
    repair = payload["default_repair"]
    assert isinstance(repair, dict)
    assert repair["final_state"] == "selected_deterministic_symbol_brand"
    assert repair["selected_url"] == "https://career.1and1.org/"
    assert repair["selected_stage"] == "deterministic_symbol_brand"
    assert len(atomic_rows) == 1
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages[staged.PRIMARY_STAGE]["attempted"] is False
    assert stages[staged.ESCALATION_STAGE]["attempted"] is False
    assert stages["tavily_repair"]["attempted"] is False
    assert sum(int(stage["provider_request_count"]) for stage in repair["stages"]) == 0


def test_primary_model_direct_url_hit_skips_escalation_and_tavily(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        providers = _providers(rows)
        if "llm_primary_direct_url_hypothesis" in providers:
            return _selected("https://jobs.1und1.de/")
        return _baseline()

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)
    calls: list[str] = []

    def fake_model(**kwargs):  # type: ignore[no-untyped-def]
        model = str(kwargs["model"])
        calls.append(model)
        return _observation(model, urls=["https://jobs.1und1.de/"])

    monkeypatch.setattr(staged.adaptive, "request_search_hypotheses", fake_model)
    monkeypatch.setattr(
        staged.adaptive,
        "_search_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tavily must not run after primary direct URL selection")
        ),
    )

    payload = staged.run_default_repair_for_company(_args(), "1_1")
    repair = payload["default_repair"]
    assert repair["final_state"] == f"selected_{staged.PRIMARY_STAGE}"
    assert repair["selected_url"] == "https://jobs.1und1.de/"
    assert calls == ["gpt-5.4-mini"]
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages[staged.PRIMARY_STAGE]["provider_request_count"] == 1
    assert stages[staged.ESCALATION_STAGE]["attempted"] is False
    assert stages["tavily_repair"]["attempted"] is False


def test_primary_miss_then_escalation_direct_url_hit_skips_tavily(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        providers = _providers(rows)
        if "llm_escalation_direct_url_hypothesis" in providers:
            return _selected("https://careers.1und1.de/")
        return _baseline()

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)
    calls: list[str] = []

    def fake_model(**kwargs):  # type: ignore[no-untyped-def]
        model = str(kwargs["model"])
        calls.append(model)
        if model == "gpt-5.4-mini":
            return _observation(model, urls=["https://wrong.1und1.example/"])
        return _observation(model, urls=["https://careers.1und1.de/"])

    monkeypatch.setattr(staged.adaptive, "request_search_hypotheses", fake_model)
    monkeypatch.setattr(
        staged.adaptive,
        "_search_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Tavily must not run after escalation direct URL selection")
        ),
    )

    payload = staged.run_default_repair_for_company(_args(), "1_1")
    repair = payload["default_repair"]
    assert repair["final_state"] == f"selected_{staged.ESCALATION_STAGE}"
    assert repair["selected_url"] == "https://careers.1und1.de/"
    assert calls == ["gpt-5.4-mini", "gpt-5.5"]
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages[staged.PRIMARY_STAGE]["provider_request_count"] == 1
    assert stages[staged.ESCALATION_STAGE]["provider_request_count"] == 1
    assert stages["tavily_repair"]["attempted"] is False


def test_primary_provider_failure_remains_visible_but_escalation_can_recover(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        if "llm_escalation_direct_url_hypothesis" in _providers(rows):
            return _selected("https://careers.1und1.de/")
        return _baseline()

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)

    def fake_model(**kwargs):  # type: ignore[no-untyped-def]
        model = str(kwargs["model"])
        if model == "gpt-5.4-mini":
            return _failed_observation(model)
        return _observation(model, urls=["https://careers.1und1.de/"])

    monkeypatch.setattr(staged.adaptive, "request_search_hypotheses", fake_model)

    payload = staged.run_default_repair_for_company(_args(), "1_1")
    repair = payload["default_repair"]
    assert repair["final_state"] == f"selected_{staged.ESCALATION_STAGE}"
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages[staged.PRIMARY_STAGE]["status"] == "configuration_blocked"
    assert stages[staged.PRIMARY_STAGE]["blocker"] == "search_llm_provider_failed_closed"
    assert stages[staged.PRIMARY_STAGE]["provider_request_count"] == 1
    assert stages[staged.ESCALATION_STAGE]["status"] == "selected"


def test_both_model_misses_defer_unique_queries_to_tavily(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        providers = _providers(rows)
        if providers == {"tavily_adaptive_search"}:
            return _selected("https://karriere.1und1.de/")
        return _baseline()

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)

    def fake_model(**kwargs):  # type: ignore[no-untyped-def]
        model = str(kwargs["model"])
        ledger = kwargs["ledger"]
        if model == "gpt-5.4-mini":
            queries = ledger.novel_queries(["site:1und1.de karriere", "1und1 jobs"])
            urls = ledger.novel_urls(["https://wrong-one.example/"])
        else:
            queries = ledger.novel_queries(["1und1 jobs", "1&1 careers official"])
            urls = ledger.novel_urls(["https://wrong-two.example/"])
        return _observation(model, queries=queries, urls=urls)

    monkeypatch.setattr(staged.adaptive, "request_search_hypotheses", fake_model)
    search_calls: list[list[str]] = []

    def fake_search(
        args,
        *,
        company_key,
        queries,
        ledger,
        maximum_results,
    ):  # type: ignore[no-untyped-def]
        search_calls.append(list(queries))
        if len(search_calls) == 1:
            url = ledger.novel_urls(["https://karriere.1und1.de/"])[0]
            return (
                [
                    {
                        "company_key": company_key,
                        "url": url,
                        "provider": "tavily_adaptive_search",
                        "title": "1&1 Karriere",
                        "snippet": "Offizielle Karriereseite",
                        "query": str(queries[0]),
                    }
                ],
                1,
            )
        return [], 0

    monkeypatch.setattr(staged.adaptive, "_search_rows", fake_search)

    payload = staged.run_default_repair_for_company(_args(), "1_1")
    repair = payload["default_repair"]
    assert repair["final_state"] == "selected_tavily_repair"
    assert search_calls
    first_queries = search_calls[0]
    assert first_queries[:3] == [
        "site:1und1.de karriere",
        "1und1 jobs",
        "1&1 careers official",
    ]
    assert first_queries.count("1und1 jobs") == 1
    tavily = next(stage for stage in repair["stages"] if stage["name"] == "tavily_repair")
    assert tavily["provider_request_count"] == 1


def test_tavily_disabled_still_allows_model_first_direct_selection(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        if "llm_primary_direct_url_hypothesis" in _providers(rows):
            return _selected("https://jobs.1und1.de/")
        return _baseline()

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)
    monkeypatch.setattr(
        staged.adaptive,
        "request_search_hypotheses",
        lambda **kwargs: _observation(
            str(kwargs["model"]), urls=["https://jobs.1und1.de/"]
        ),
    )

    payload = staged.run_default_repair_for_company(
        _args(disable_tavily=True),
        "1_1",
    )
    repair = payload["default_repair"]
    assert repair["final_state"] == f"selected_{staged.PRIMARY_STAGE}"
    assert repair["selected_url"] == "https://jobs.1und1.de/"
    tavily = next(stage for stage in repair["stages"] if stage["name"] == "tavily_repair")
    assert tavily["attempted"] is False


def test_llm_disabled_preserves_deterministic_then_tavily_fallback(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )
    residual_url = "https://residual-origin.example/jobs/"

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        if _providers(rows) == {"tavily_adaptive_search"}:
            return _selected(residual_url)
        return _baseline()

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)
    monkeypatch.setattr(
        staged.adaptive,
        "request_search_hypotheses",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("no model call is allowed when --disable-llm is set")
        ),
    )

    def fake_search(
        args,
        *,
        company_key,
        queries,
        ledger,
        maximum_results,
    ):  # type: ignore[no-untyped-def]
        if not search_calls:
            url = ledger.novel_urls([residual_url])[0]
            search_calls.append(list(queries))
            return (
                [
                    {
                        "company_key": company_key,
                        "url": url,
                        "provider": "tavily_adaptive_search",
                        "title": "Residual official career surface",
                        "snippet": "Residual provider result",
                        "query": str(queries[0]),
                    }
                ],
                1,
            )
        search_calls.append(list(queries))
        return [], 0

    search_calls: list[list[str]] = []
    monkeypatch.setattr(staged.adaptive, "_search_rows", fake_search)

    payload = staged.run_default_repair_for_company(
        _args(disable_llm=True),
        "1_1",
    )
    repair = payload["default_repair"]
    assert repair["final_state"] == "selected_tavily_repair"
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages[staged.PRIMARY_STAGE]["status"] == "skipped"
    assert stages[staged.ESCALATION_STAGE]["status"] == "skipped"
    assert stages["tavily_repair"]["provider_request_count"] == 1


def test_primary_cost_ceiling_blocks_only_primary_and_escalation_can_continue(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        if "llm_escalation_direct_url_hypothesis" in _providers(rows):
            return _selected("https://careers.1und1.de/")
        return _baseline()

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)
    calls: list[str] = []

    def fake_model(**kwargs):  # type: ignore[no-untyped-def]
        model = str(kwargs["model"])
        calls.append(model)
        return _observation(model, urls=["https://careers.1und1.de/"])

    monkeypatch.setattr(staged.adaptive, "request_search_hypotheses", fake_model)

    payload = staged.run_default_repair_for_company(
        _args(max_search_llm_cost_usd_per_company=0.0),
        "1_1",
    )
    repair = payload["default_repair"]
    stages = {stage["name"]: stage for stage in repair["stages"]}
    assert stages[staged.PRIMARY_STAGE]["blocker"] == (
        "search_llm_cost_reservation_exceeds_ceiling"
    )
    assert stages[staged.PRIMARY_STAGE]["provider_request_count"] == 0
    assert calls == ["gpt-5.5"]
    assert repair["final_state"] == f"selected_{staged.ESCALATION_STAGE}"
