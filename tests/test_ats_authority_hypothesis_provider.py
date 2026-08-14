from __future__ import annotations

import json

from src.search_intelligence.ats_authority_gap_execution import ATSAuthorityProgressLedger
from src.search_intelligence.ats_authority_hypothesis_provider import (
    request_ats_authority_hypotheses,
)


def response_for(urls: list[str]) -> dict[str, object]:
    return {
        "id": "resp_test",
        "model": "gpt-5.6-luna",
        "output_text": json.dumps(
            {
                "urls": urls,
                "rationale": "bounded ATS evidence candidates",
            }
        ),
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


def test_provider_returns_novel_urls_without_consuming_execution_ledger() -> None:
    ledger = ATSAuthorityProgressLedger()
    ledger.seed_urls(("https://bridgingit.jobs.personio.de/xml",))

    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        return response_for(
            [
                "https://bridgingit.jobs.personio.de/xml?utm_source=test",
                "https://bridgingit.jobs.personio.de/jobs/42?utm_source=test",
            ]
        )

    observation = request_ats_authority_hypotheses(
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
        expected_provider="personio",
        authority_gap_evidence={
            "classification": "ats_authority_external_evidence_gap",
            "external_information_gap": True,
            "deterministic_request_replay_blocked": True,
            "evidence_fingerprint": "a" * 64,
        },
        attempted_candidate_summaries=(),
        ledger=ledger,
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    assert observation.urls == ("https://bridgingit.jobs.personio.de/jobs/42",)
    assert observation.product_authority is False
    assert "https://bridgingit.jobs.personio.de/jobs/42" not in ledger.attempted_urls


def test_provider_packet_declares_candidate_only_no_authority() -> None:
    captured: dict[str, object] = {}

    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        captured.update(payload)
        return response_for([])

    observation = request_ats_authority_hypotheses(
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
        expected_provider="personio",
        authority_gap_evidence={
            "classification": "ats_authority_external_evidence_gap",
            "external_information_gap": True,
            "deterministic_request_replay_blocked": True,
            "next_action": "search_for_alternate_ats_authority_evidence",
            "evidence_fingerprint": "b" * 64,
        },
        attempted_candidate_summaries=(),
        ledger=ATSAuthorityProgressLedger(),
        api_key="test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "completed"
    assert captured["store"] is False
    text = json.dumps(captured)
    assert "ats_authority_evidence_hypotheses" in text
    assert '"maxItems": 3' in text
    assert '"tenant_authority": false' in text
    assert '"delegation_permitted": false' in text
    assert '"product_authority": false' in text


def test_provider_fails_closed_on_invalid_json() -> None:
    def transport(url, headers, payload, timeout):  # type: ignore[no-untyped-def]
        return {"id": "resp_test", "output_text": "not-json"}

    observation = request_ats_authority_hypotheses(
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
        expected_provider="personio",
        authority_gap_evidence={"classification": "ats_authority_external_evidence_gap"},
        attempted_candidate_summaries=(),
        ledger=ATSAuthorityProgressLedger(),
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

    observation = request_ats_authority_hypotheses(
        company_key="bridgingit",
        company_name="BridgingIT GmbH",
        expected_provider="personio",
        authority_gap_evidence={"classification": "ats_authority_external_evidence_gap"},
        attempted_candidate_summaries=(),
        ledger=ATSAuthorityProgressLedger(),
        api_key="secret-value",
        model="gpt-5.6-luna",
        transport=transport,
    )

    assert observation.status == "failed_closed"
    assert "secret-value" not in observation.rationale
    assert "Bearer ***" in observation.rationale
