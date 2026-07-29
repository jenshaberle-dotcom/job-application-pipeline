from __future__ import annotations

import pytest

from src.search_intelligence.origin_provider_event_runtime import (
    OriginProviderRuntimeError,
    ProviderBudget,
    build_dispatch_payload,
    normalize_company_keys,
    projection_fingerprint,
)


def test_provider_budget_caps_candidate_count_before_provider_execution() -> None:
    budget = ProviderBudget(
        max_candidates=10,
        search_query_limit=3,
        search_max_results=5,
        max_provider_requests=8,
    )

    assert budget.effective_candidate_limit == 2
    assert budget.planned_provider_requests == 6


def test_provider_budget_requires_one_complete_candidate() -> None:
    with pytest.raises(OriginProviderRuntimeError):
        ProviderBudget(
            max_candidates=6,
            search_query_limit=3,
            search_max_results=5,
            max_provider_requests=2,
        ).validate()


def test_projection_fingerprint_is_canonical_and_change_sensitive() -> None:
    first = [
        {
            "company_key": "hannover_ruck",
            "candidate_url": "",
            "market_evidence_urls": ["https://example.test/job"],
        }
    ]
    same = [
        {
            "market_evidence_urls": ["https://example.test/job"],
            "candidate_url": "",
            "company_key": "hannover_ruck",
        }
    ]
    changed = [
        {
            "company_key": "hannover_ruck",
            "candidate_url": "",
            "market_evidence_urls": ["https://example.test/other-job"],
        }
    ]

    assert projection_fingerprint(first) == projection_fingerprint(same)
    assert projection_fingerprint(first) != projection_fingerprint(changed)


def test_dispatch_payload_contains_metadata_only_and_stays_within_api_limit() -> None:
    payload = build_dispatch_payload(
        pipeline_repository="jenshaberle-dotcom/job-application-pipeline",
        pipeline_ref="a" * 40,
        fingerprint="b" * 64,
        budget=ProviderBudget(),
        target_location="Hannover",
        requested_at="2026-07-29T21:00:00+00:00",
    )

    assert len(payload) == 10
    assert payload["projection_fingerprint"] == "b" * 64
    assert "company_key" not in payload
    assert "candidate_url" not in payload
    assert "market_evidence_urls" not in payload


def test_company_key_normalization_preserves_first_seen_order() -> None:
    assert normalize_company_keys([" hdi ", "", "hdi", "hannover_ruck"]) == (
        "hdi",
        "hannover_ruck",
    )
