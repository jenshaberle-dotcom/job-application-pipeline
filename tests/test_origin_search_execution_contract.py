from __future__ import annotations

from types import SimpleNamespace

import requests

import scripts.run_origin_url_default_repair as default_entry  # noqa: F401
from scripts import run_origin_url_adaptive_repair as adaptive_runtime
from src.search_intelligence.adaptive_origin_search import SearchProgressLedger


def test_followup_domains_require_query_identity_and_exclude_shared_platforms() -> None:
    domains = adaptive_runtime._domains_from_rows(
        [
            {
                "url": "https://www.bridging-it.de/karriere/",
                "query": '"bridgingit" Karriere',
            },
            {
                "url": "https://www.levels.fyi/companies/bridgingit",
                "query": '"bridgingit" Karriere',
            },
            {
                "url": "https://careers.smartrecruiters.com/bridgingit",
                "query": '"bridgingit" Karriere',
            },
            {
                "url": "https://x1f-fink.one/en/career/",
                "query": '"x1f" Karriere',
            },
            {
                "url": "https://reveliolabs.com/company/bridgingit",
                "query": '"bridgingit" Karriere',
            },
        ]
    )

    assert domains == ("www.bridging-it.de", "x1f-fink.one")


def test_transport_timeout_is_recorded_without_same_query_retry(monkeypatch) -> None:
    calls: list[str] = []

    def fake_web_search(query, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(query)
        if query == "first query":
            raise requests.ReadTimeout("bounded timeout")
        return [
            SimpleNamespace(
                url="https://career.example.com/",
                title="Example Careers",
                snippet="Jobs at Example",
            )
        ]

    monkeypatch.setattr(adaptive_runtime, "web_search", fake_web_search)
    args = SimpleNamespace(
        search_max_results=5,
        search_timeout_seconds=1.0,
        search_depth="basic",
    )
    ledger = SearchProgressLedger()

    rows, requests_made = adaptive_runtime._search_rows(
        args,
        company_key="example",
        queries=("first query", "second query"),
        ledger=ledger,
        maximum_results=5,
    )

    assert calls == ["first query", "second query"]
    assert requests_made == 2
    assert len(rows) == 1
    trace = ledger.to_json()
    assert trace["transport_error_count"] == 1
    assert trace["transport_errors"][0]["query"] == "first query"
    assert trace["transport_errors"][0]["retried"] is False
    assert trace["same_query_transport_retry"] is False
