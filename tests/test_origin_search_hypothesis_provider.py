from __future__ import annotations

import json

from src.search_intelligence.adaptive_origin_search import SearchProgressLedger
from src.search_intelligence.origin_search_hypothesis_provider import (
    request_search_hypotheses,
)


def test_early_llm_provider_returns_only_novel_validated_hypotheses() -> None:
    ledger = SearchProgressLedger()
    ledger.novel_queries(["1and1 careers"])
    ledger.novel_urls(["https://career.1and1.org/"])

    def transport(url, headers, payload, timeout_seconds):  # type: ignore[no-untyped-def]
        assert url.endswith("/responses")
        assert headers["Authorization"].startswith("Bearer ")
        assert payload["store"] is False
        assert timeout_seconds == 10.0
        return {
            "id": "resp_test",
            "model": "gpt-5.4-mini",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "output_text": json.dumps(
                {
                    "queries": [
                        "1and1 careers",
                        "site:1and1.org jobs",
                    ],
                    "urls": [
                        "https://career.1and1.org/",
                        "https://jobs.1and1.org/",
                    ],
                    "rationale": "Try the official compact-brand domain.",
                }
            ),
        }

    observation = request_search_hypotheses(
        company_key="1_1",
        company_name="1&1",
        baseline_payload={"decision": "not_found", "rejected": []},
        latest_payload={"decision": "not_found", "search_results": []},
        ledger=ledger,
        api_key="test-key",
        model="gpt-5.4-mini",
        timeout_seconds=10.0,
        transport=transport,
    )

    assert observation.status == "completed"
    assert observation.request_attempted is True
    assert observation.hypotheses is not None
    assert observation.hypotheses.queries == ("site:1and1.org jobs",)
    assert observation.hypotheses.urls == ("https://jobs.1and1.org/",)


def test_early_llm_provider_fails_closed_on_invalid_output() -> None:
    ledger = SearchProgressLedger()

    def transport(url, headers, payload, timeout_seconds):  # type: ignore[no-untyped-def]
        return {
            "id": "resp_bad",
            "model": "gpt-5.4-mini",
            "output_text": "not-json",
        }

    observation = request_search_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        baseline_payload={"decision": "not_found"},
        latest_payload={"decision": "not_found"},
        ledger=ledger,
        api_key="test-key",
        model="gpt-5.4-mini",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert observation.request_attempted is True
    assert observation.hypotheses is None
    assert observation.failure_class == "JSONDecodeError"
