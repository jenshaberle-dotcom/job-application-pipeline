from __future__ import annotations

import json

from src.search_intelligence.detail_discovery_hypothesis_provider import (
    request_detail_discovery_hypotheses,
)
from src.search_intelligence.listing_booster_progress import ListingProgressLedger


def response_for(urls: list[str]) -> dict[str, object]:
    return {
        "id": "resp_test",
        "model": "gpt-5.6-luna",
        "output_text": json.dumps(
            {
                "urls": urls,
                "rationale": "bounded detail candidates",
            }
        ),
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def test_provider_returns_novel_urls_without_consuming_ledger() -> None:
    ledger = ListingProgressLedger()
    ledger.novel_urls(("https://jobs.example.com/jobs/old-role",))

    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        return response_for(
            [
                "https://jobs.example.com/jobs/old-role?utm_source=test",
                "https://jobs.example.com/jobs/123-data-engineer?utm_source=test",
            ]
        )

    observation = request_detail_discovery_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://jobs.example.com/",
        gap_evidence={
            "classification": "detail_external_information_gap",
            "external_information_gap": True,
            "preliminary_candidate_count": 0,
            "evidence_fingerprint": "a" * 64,
        },
        attempted_candidate_summaries=(),
        ledger=ledger,
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    assert observation.urls == ("https://jobs.example.com/jobs/123-data-engineer",)
    assert observation.product_authority is False
    assert "https://jobs.example.com/jobs/123-data-engineer" not in ledger.attempted_urls


def test_provider_packet_declares_candidate_only_deterministic_validation() -> None:
    captured: dict[str, object] = {}

    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        captured.update(payload)
        return response_for([])

    observation = request_detail_discovery_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://jobs.example.com/",
        gap_evidence={
            "classification": "detail_candidate_validation_gap",
            "external_information_gap": False,
            "preliminary_candidate_count": 1,
            "next_action": "interpret_or_propose_detail_candidates",
            "evidence_fingerprint": "b" * 64,
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
    assert "detail_discovery_url_hypotheses" in text
    assert '"maxItems": 3' in text

    input_items = captured["input"]
    assert isinstance(input_items, list)
    user_item = next(
        item
        for item in input_items
        if isinstance(item, dict) and item.get("role") == "user"
    )
    content = user_item["content"]
    assert isinstance(content, list)
    packet_text = content[0]["text"]
    assert isinstance(packet_text, str)
    packet = json.loads(packet_text)
    constraints = packet["authority_constraints"]
    assert constraints["same_employer_source_validation_required"] is True
    assert constraints["concrete_detail_validation_required"] is True
    assert constraints["gate_pass"] is False
    assert constraints["product_authority"] is False


def test_provider_fails_closed_on_invalid_json() -> None:
    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        return {"id": "resp_test", "output_text": "not-json"}

    observation = request_detail_discovery_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://jobs.example.com/",
        gap_evidence={"classification": "detail_external_information_gap"},
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
    assert "packet_sha256=" in observation.rationale


def test_provider_does_not_expose_api_key_in_failure_message() -> None:
    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        raise ValueError("Bearer secret-value leaked by synthetic transport")

    observation = request_detail_discovery_hypotheses(
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://jobs.example.com/",
        gap_evidence={"classification": "detail_external_information_gap"},
        attempted_candidate_summaries=(),
        ledger=ListingProgressLedger(),
        api_key="secret-value",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert "secret-value" not in observation.rationale
    assert "Bearer ***" in observation.rationale
