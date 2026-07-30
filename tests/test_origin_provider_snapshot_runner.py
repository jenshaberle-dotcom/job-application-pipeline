from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from scripts import origin_provider_snapshot_runner as snapshot_runner
from scripts.run_origin_provider_event_benchmark import (
    CHECKPOINT_SCHEMA_VERSION,
    load_checkpoint,
    write_checkpoint,
)
from src.search_intelligence.origin_source_discovery_agent import OriginSearchResult


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        target_location="Hannover",
        timeout_seconds=1.0,
        max_candidates=10,
        market_evidence_limit=10,
        search_provider=["tavily"],
        search_query_limit=2,
        search_max_results=5,
        search_timeout_seconds=1.0,
        search_depth="basic",
        search_results_json=None,
        no_probe=True,
    )


def _projection_row() -> dict[str, object]:
    return {
        "candidate_id": 42,
        "company_key": "example-gmbh",
        "company_name": "Example GmbH",
        "source_family_candidate": "company_career_page",
        "status": "discovery",
        "risk_level": "low",
        "candidate_url": "",
        "market_evidence_urls": ["https://example.test/jobs"],
    }


def test_snapshot_runner_counts_actual_provider_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[tuple[str, str]] = []

    def fake_web_search(
        query: str,
        *,
        provider: str,
        max_results: int,
        timeout_seconds: float,
        search_depth: str,
    ) -> list[OriginSearchResult]:
        assert max_results == 5
        assert timeout_seconds == 1.0
        assert search_depth == "basic"
        return [
            OriginSearchResult(
                url="https://example.test/careers",
                title="Careers",
                snippet="Jobs at Example GmbH",
                query=query,
                provider=provider,
            )
        ]

    monkeypatch.setattr(snapshot_runner, "web_search", fake_web_search)
    payload = snapshot_runner.run_for_projection_row(
        _args(),
        _projection_row(),
        request_attempt_observer=lambda provider, query: observed.append((provider, query)),
    )

    assert len(observed) == 2
    assert all(provider == "tavily" for provider, _ in observed)
    assert payload["candidate_id"] == 42
    assert payload["market_evidence_url_count"] == 1
    assert payload["projection_snapshot_used"] is True


def test_checkpoint_round_trip_requires_exact_projection_prefix(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    company_keys = ["one", "two"]
    results: list[dict[str, Any]] = [{"company_key": "one", "decision": "not_found"}]

    write_checkpoint(
        checkpoint,
        fingerprint="a" * 64,
        company_keys=company_keys,
        results=results,
        provider_request_attempts=2,
        complete=False,
    )
    restored, attempts = load_checkpoint(
        checkpoint,
        expected_fingerprint="a" * 64,
        company_keys=company_keys,
    )

    assert restored == results
    assert attempts == 2
    assert CHECKPOINT_SCHEMA_VERSION in checkpoint.read_text(encoding="utf-8")


def test_checkpoint_rejects_different_fingerprint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    write_checkpoint(
        checkpoint,
        fingerprint="a" * 64,
        company_keys=["one"],
        results=[],
        provider_request_attempts=0,
        complete=False,
    )

    with pytest.raises(SystemExit, match="checkpoint fingerprint"):
        load_checkpoint(
            checkpoint,
            expected_fingerprint="b" * 64,
            company_keys=["one"],
        )
