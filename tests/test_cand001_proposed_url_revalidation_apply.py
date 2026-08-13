from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.run_cand001_proposed_url_revalidation_apply as proposed
from src.search_intelligence.cand001_validated_origin_url_persistence import (
    CandidatePersistenceSnapshot,
    OriginUrlValidationEvidence,
)


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "benchmark_label": "test-proposed-url",
        "company_key": ["example"],
        "candidate_id": 42,
        "proposed_url": "https://careers.example.com/",
        "target_location": "Hannover",
        "target_locale": "de",
        "reviewed_by": "test",
        "apply": False,
        "include_active_controlled": False,
        "timeout_seconds": 5.0,
        "max_url_candidates": 12,
        "market_evidence_limit": 30,
        "search_provider": ["none"],
        "search_query_limit": 4,
        "search_max_results": 5,
        "search_timeout_seconds": 8.0,
        "search_depth": "advanced",
        "search_results_json": None,
        "max_evidence_candidates": 4,
        "max_evidence_http_requests": 12,
        "evidence_timeout_seconds": 8.0,
        "max_response_bytes": 750_000,
        "llm_model": "gpt-5.4-mini",
        "llm_reasoning_effort": "low",
        "llm_max_output_tokens": 600,
        "llm_reserved_input_tokens": 5000,
        "llm_timeout_seconds": 60.0,
        "max_estimated_llm_cost_usd_per_company": 0.01,
        "disable_tavily": False,
        "disable_llm": False,
        "single_pass_diagnostic": False,
        "no_probe": False,
        "output_json": tmp_path / "result.json",
        "output_markdown": tmp_path / "result.md",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class _Connection:
    committed = False
    rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@contextmanager
def _connection():
    yield _Connection()


def _candidate() -> CandidatePersistenceSnapshot:
    return CandidatePersistenceSnapshot(
        candidate_id=42,
        company_key="example",
        company_name="Example GmbH",
        status="url_discovery_pending",
        candidate_url=None,
        risk_level="low",
    )


def _payload(url: str | None) -> dict[str, object]:
    return {
        "company_key": "example",
        "company_name": "Example GmbH",
        "decision": "origin_url_candidate_selected" if url else "not_found",
        "selected_url": url,
        "confidence_score": 1.0 if url else 0.2,
        "reason": "fresh deterministic validation",
        "default_repair": {
            "selected_url": url,
            "final_state": "selected" if url else "repair_exhausted",
            "selected_stage": "deterministic_symbol_brand" if url else None,
        },
        "url_finder_tier": "A" if url else None,
    }


def _evidence(url: str) -> OriginUrlValidationEvidence:
    return OriginUrlValidationEvidence(
        selected_url=url,
        source="live_url_finder_validation",
        decision="origin_url_candidate_selected",
        confidence_score=1.0,
        url_finder_tier="A",
        reason="validated",
        risk_level="low",
    )


def _install_common(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proposed.cand001, "connect", _connection)
    monkeypatch.setattr(
        proposed.cand001,
        "load_candidate",
        lambda conn, company_key, candidate_id=None: _candidate(),
    )
    monkeypatch.setattr(
        proposed.cand001,
        "duplicate_selected_url_exists",
        lambda conn, *, candidate, selected_url: False,
    )


def test_origin_args_force_provider_free_exact_revalidation(tmp_path: Path) -> None:
    args = _args(tmp_path)
    origin = proposed._origin_args(args)
    assert origin.operator_url == ["https://careers.example.com/"]
    assert origin.disable_llm is True
    assert origin.disable_tavily is True
    assert origin.search_provider == ["none"]


def test_exact_selected_url_can_apply_without_stochastic_rediscovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_common(monkeypatch)
    observed: dict[str, object] = {}

    def fake_repair(origin_args, company_key):  # type: ignore[no-untyped-def]
        observed["origin_args"] = origin_args
        observed["company_key"] = company_key
        return _payload("https://careers.example.com/")

    monkeypatch.setattr(
        proposed.default_repair,
        "run_default_repair_for_company",
        fake_repair,
    )
    monkeypatch.setattr(
        proposed,
        "evidence_from_origin_discovery_payload",
        lambda payload: _evidence("https://careers.example.com/"),
    )
    monkeypatch.setattr(
        proposed,
        "build_persistence_plan_item",
        lambda candidate, evidence, **kwargs: SimpleNamespace(
            candidate_id=42,
            company_key="example",
            company_name="Example GmbH",
            candidate_status="url_discovery_pending",
            previous_candidate_url=None,
            selected_url=evidence.selected_url,
            selected_url_source=evidence.source,
            decision="persist_validated_candidate_url",
            review_status="write_recommended",
            reason=evidence.reason,
            url_finder_tier=evidence.url_finder_tier,
            url_finder_decision=evidence.decision,
            confidence_score=evidence.confidence_score,
            apply_allowed=True,
            applied=bool(kwargs.get("applied", False)),
            audit_review_id=kwargs.get("audit_review_id"),
            to_json=lambda: {},
        ),
    )
    writes: list[str] = []
    monkeypatch.setattr(
        proposed.cand001,
        "write_review_and_candidate_url",
        lambda conn, *, item, evidence, reviewed_by: writes.append(item.selected_url) or 99,
    )
    monkeypatch.setattr(
        proposed,
        "report_payload",
        lambda *, benchmark_label, items: {"benchmark_label": benchmark_label, "items": []},
    )
    monkeypatch.setattr(proposed, "markdown_report", lambda payload: "# report\n")

    result = proposed.run(_args(tmp_path, apply=True))

    assert writes == ["https://careers.example.com/"]
    assert observed["company_key"] == "example"
    origin = observed["origin_args"]
    assert origin.disable_llm is True
    assert origin.disable_tavily is True
    assert result["proposed_url_revalidation"]["exact_url_reselection_required"] is True
    assert result["proposed_url_revalidation"]["alternate_url_substitution_allowed"] is False


def test_alternate_selected_url_is_rejected_and_never_written(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_common(monkeypatch)
    monkeypatch.setattr(
        proposed.default_repair,
        "run_default_repair_for_company",
        lambda origin_args, company_key: _payload("https://jobs.example.com/"),
    )
    monkeypatch.setattr(
        proposed,
        "evidence_from_origin_discovery_payload",
        lambda payload: _evidence("https://jobs.example.com/"),
    )
    captured: dict[str, object] = {}

    def fake_plan(candidate, evidence, **kwargs):  # type: ignore[no-untyped-def]
        captured["evidence"] = evidence
        return SimpleNamespace(
            candidate_id=42,
            company_key="example",
            company_name="Example GmbH",
            candidate_status="url_discovery_pending",
            previous_candidate_url=None,
            selected_url=evidence.selected_url,
            selected_url_source=evidence.source,
            decision="no_selected_url",
            review_status="manual_review_required",
            reason=evidence.reason,
            url_finder_tier=evidence.url_finder_tier,
            url_finder_decision=evidence.decision,
            confidence_score=evidence.confidence_score,
            apply_allowed=False,
            applied=False,
            audit_review_id=None,
            to_json=lambda: {},
        )

    monkeypatch.setattr(proposed, "build_persistence_plan_item", fake_plan)
    monkeypatch.setattr(
        proposed.cand001,
        "write_review_and_candidate_url",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not write")),
    )
    monkeypatch.setattr(
        proposed,
        "report_payload",
        lambda *, benchmark_label, items: {"benchmark_label": benchmark_label, "items": []},
    )
    monkeypatch.setattr(proposed, "markdown_report", lambda payload: "# report\n")

    proposed.run(_args(tmp_path, apply=True))

    evidence = captured["evidence"]
    assert evidence.selected_url is None
    assert evidence.source == proposed.PROVENANCE
    assert evidence.decision == "proposed_url_revalidation_failed"
    assert evidence.url_finder_tier is None
    assert "No alternate URL may be substituted" in evidence.reason
