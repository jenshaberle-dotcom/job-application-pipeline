from __future__ import annotations

import json

from src.search_intelligence.listing_booster_progress import ListingProgressLedger
from src.search_intelligence.listing_route_hypothesis_provider import (
    request_listing_route_hypotheses,
)


def response_for(urls: list[str]) -> dict[str, object]:
    return {
        "id": "resp_test",
        "model": "gpt-5.6-luna",
        "output_text": json.dumps(
            {
                "urls": urls,
                "rationale": "bounded route candidates",
            }
        ),
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def test_provider_returns_novel_urls_without_consuming_execution_ledger() -> None:
    ledger = ListingProgressLedger()
    ledger.novel_urls(["https://www.example.com/karriere"])

    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        return response_for(
            [
                "https://jobs.example.com/de?id=458ccb&utm_source=test",
                "https://www.example.com/karriere",
            ]
        )

    observation = request_listing_route_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        origin_url="https://www.example.com/karriere",
        deterministic_evidence={
            "classification": "external_listing_information_gap",
            "reason_codes": ["reachable_surface_without_listing_evidence"],
        },
        attempted_candidate_summaries=(),
        ledger=ledger,
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )
    assert observation.status == "completed"
    assert observation.urls == ("https://jobs.example.com/de?id=458ccb",)
    assert observation.product_authority is False
    assert "https://jobs.example.com/de?id=458ccb" not in ledger.attempted_urls


def test_provider_packet_declares_no_selection_authority() -> None:
    captured: dict[str, object] = {}

    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        captured.update(payload)
        return response_for([])

    observation = request_listing_route_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        origin_url="https://www.example.com/karriere",
        deterministic_evidence={
            "final_url": "https://www.example.com/karriere",
            "classification": "external_listing_information_gap",
            "reason_codes": ["reachable_surface_without_listing_evidence"],
            "jsonld_types": [],
            "route_candidates": [],
            "delegated_route_candidates": [],
        },
        attempted_candidate_summaries=(),
        ledger=ListingProgressLedger(),
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )
    assert observation.status == "completed"
    assert captured["store"] is False
    text = json.dumps(captured)
    assert "listing_route_hypotheses" in text
    assert '"maxItems": 3' in text


def test_provider_fails_closed_on_invalid_json() -> None:
    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        return {"id": "resp_test", "output_text": "not-json"}

    observation = request_listing_route_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        origin_url="https://www.example.com/karriere",
        deterministic_evidence={"classification": "external_listing_information_gap"},
        attempted_candidate_summaries=(),
        ledger=ListingProgressLedger(),
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )
    assert observation.status == "failed_closed"
    assert observation.request_attempted is True
    assert observation.urls == ()
    assert observation.product_authority is False
