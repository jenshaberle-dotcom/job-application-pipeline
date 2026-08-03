from __future__ import annotations

import argparse
from typing import Mapping, Sequence

import scripts.run_origin_url_staged_repair as staged


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        target_location="Hannover",
        target_locale="de",
        reviewed_by="test",
        timeout_seconds=1.0,
        max_url_candidates=12,
        market_evidence_limit=30,
        search_query_limit=5,
        initial_search_query_limit=5,
        domain_followup_query_limit=3,
        max_brand_host_hypotheses=6,
        max_adaptive_candidates=18,
        search_max_results=5,
        search_timeout_seconds=1.0,
        search_depth="advanced",
        search_results_json=None,
        operator_url=[],
        max_evidence_candidates=4,
        max_evidence_http_requests=12,
        evidence_timeout_seconds=1.0,
        max_response_bytes=100_000,
        llm_model="gpt-5.4-mini",
        llm_reasoning_effort="low",
        llm_max_output_tokens=600,
        llm_reserved_input_tokens=5000,
        llm_timeout_seconds=1.0,
        max_estimated_llm_cost_usd_per_company=0.01,
        search_llm_model="gpt-5.4-mini",
        search_llm_reasoning_effort="low",
        search_llm_max_output_tokens=500,
        search_llm_reserved_input_tokens=3500,
        search_llm_timeout_seconds=1.0,
        max_search_llm_cost_usd_per_company=0.01,
        disable_tavily=False,
        disable_llm=False,
    )


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


def test_deterministic_symbol_brand_hit_skips_every_provider(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )
    direct_calls: list[Sequence[Mapping[str, object]]] = []

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        direct_calls.append(rows)
        return _selected("https://career.1and1.org/")

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)

    def forbidden_search(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Tavily must not run after deterministic selection")

    monkeypatch.setattr(staged.adaptive, "_search_rows", forbidden_search)

    payload = staged.run_default_repair_for_company(_args(), "1_1")
    repair = payload["default_repair"]
    assert isinstance(repair, dict)
    assert repair["final_state"] == "selected_deterministic_symbol_brand"
    assert repair["selected_url"] == "https://career.1and1.org/"
    assert repair["selected_stage"] == "deterministic_symbol_brand"
    assert len(direct_calls) == 1
    stages = repair["stages"]
    assert isinstance(stages, list)
    assert sum(int(stage["provider_request_count"]) for stage in stages) == 0
    assert stages[2]["name"] == "tavily_repair"
    assert stages[2]["attempted"] is False


def test_tavily_runs_only_after_deterministic_miss_and_receives_no_direct_rows(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        staged.adaptive,
        "run_atomic_origin_discovery",
        lambda args, company_key: _baseline(),
    )
    atomic_rows: list[list[dict[str, object]]] = []

    def fake_atomic(args, *, company_key, rows):  # type: ignore[no-untyped-def]
        materialized = [dict(row) for row in rows]
        atomic_rows.append(materialized)
        if len(atomic_rows) == 1:
            result = _baseline()
            result["reason"] = "deterministic brand hosts did not validate"
            return result
        return _selected("https://karriere.1und1.de/")

    monkeypatch.setattr(staged.adaptive, "_run_atomic_with_rows", fake_atomic)
    search_calls = 0

    def fake_search(
        args,
        *,
        company_key,
        queries,
        ledger,
        maximum_results,
    ):  # type: ignore[no-untyped-def]
        nonlocal search_calls
        search_calls += 1
        if search_calls == 1:
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
    assert isinstance(repair, dict)
    assert repair["final_state"] == "selected_tavily_repair"
    assert len(atomic_rows) == 2
    assert all(
        row["provider"] in {
            "deterministic_symbol_brand",
            "operator_supplied_unvalidated",
        }
        for row in atomic_rows[0]
    )
    assert all(row["provider"] == "tavily_adaptive_search" for row in atomic_rows[1])
    assert all(
        row["url"] not in {item["url"] for item in atomic_rows[0]}
        for row in atomic_rows[1]
    )
    stages = repair["stages"]
    assert isinstance(stages, list)
    tavily = next(stage for stage in stages if stage["name"] == "tavily_repair")
    assert tavily["provider_request_count"] == 1
