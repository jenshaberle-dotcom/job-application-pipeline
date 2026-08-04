from __future__ import annotations

import argparse

import scripts.run_origin_url_default_repair as default_entry
from src.search_intelligence.origin_explicit_tavily_disable_contract import (
    normalize_explicit_tavily_disable_outcome,
)
from src.search_intelligence.origin_url_default_repair import (
    RepairStage,
    compatibility_payload,
    finalize_outcome,
)


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        operator_url=["https://operator.example/karriere"],
        disable_tavily=True,
        disable_llm=True,
        target_locale="de-DE",
    )


def _selected_payload(url: str) -> dict[str, object]:
    return {
        "company_key": "example",
        "company_name": "Example GmbH",
        "decision": "origin_url_candidate_selected",
        "selected_url": url,
        "confidence_score": 1.0,
        "candidate_count": 1,
        "reason": "validated operator-supplied origin URL",
        "alternatives": [{"url": url}],
        "rejected": [],
        "search_results": [{"url": url}],
    }


def test_operator_url_wins_before_selected_fallback(monkeypatch) -> None:
    fallback_calls = 0

    def fallback(args, company_key):  # type: ignore[no-untyped-def]
        nonlocal fallback_calls
        fallback_calls += 1
        return _selected_payload("https://fallback.example/karriere")

    monkeypatch.setattr(default_entry, "_STAGED_RUNNER", fallback)
    monkeypatch.setattr(
        default_entry.staged.adaptive,
        "_run_atomic_with_rows",
        lambda args, *, company_key, rows: _selected_payload(
            "https://operator.example/karriere"
        ),
    )

    payload = default_entry.run_default_repair_for_company(_args(), "example")
    repair = payload["default_repair"]
    assert isinstance(repair, dict)
    assert repair["final_state"] == "selected_deterministic_operator_url"
    assert repair["selected_url"] == "https://operator.example/karriere"
    assert repair["selected_stage"] == "deterministic_operator_url"
    assert fallback_calls == 0
    assert payload["operator_url_precedence"]["provider_requests"] == 0


def test_explicit_tavily_disable_preserves_deterministic_manual_review() -> None:
    stages = (
        RepairStage(
            name="deterministic_baseline",
            attempted=True,
            status="manual_review",
            decision="manual_review_required",
            selected_url=None,
            recommended_url=None,
            confidence_score=1.0,
            candidate_count=1,
            provider_request_count=0,
            reason="deterministic evidence requires review",
        ),
        RepairStage(
            name="tavily_repair",
            attempted=False,
            status="configuration_blocked",
            decision=None,
            selected_url=None,
            recommended_url=None,
            confidence_score=0.0,
            candidate_count=0,
            provider_request_count=0,
            reason="Tavily disabled",
            blocker="tavily_disabled_diagnostic_override",
        ),
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=stages,
    )
    payload = compatibility_payload(
        outcome,
        last_discovery_payload={
            "company_key": "example",
            "company_name": "Example GmbH",
            "decision": "repair_configuration_blocked",
            "selected_url": None,
        },
    )

    normalized = normalize_explicit_tavily_disable_outcome(
        payload,
        tavily_disabled=True,
    )

    assert normalized["repair_final_state"] == "operator_review_required"
    assert normalized["repair_configuration_blocked"] is False
    assert normalized["operator_review_required"] is True
    assert normalized["tavily_disable_semantics_normalized"] is True
    repair = normalized["default_repair"]
    assert isinstance(repair, dict)
    tavily = next(
        stage for stage in repair["stages"] if stage["name"] == "tavily_repair"
    )
    assert tavily["status"] == "skipped"
    assert tavily["blocker"] is None


def test_real_tavily_configuration_blocker_remains_blocking() -> None:
    stages = (
        RepairStage(
            name="deterministic_baseline",
            attempted=True,
            status="not_found",
            decision="not_found",
            selected_url=None,
            recommended_url=None,
            confidence_score=0.4,
            candidate_count=1,
            provider_request_count=0,
            reason="not found",
        ),
        RepairStage(
            name="tavily_repair",
            attempted=False,
            status="configuration_blocked",
            decision=None,
            selected_url=None,
            recommended_url=None,
            confidence_score=0.0,
            candidate_count=0,
            provider_request_count=0,
            reason="missing key",
            blocker="missing_tavily_api_key",
        ),
    )
    outcome = finalize_outcome(
        company_key="example",
        company_name="Example GmbH",
        stages=stages,
    )
    payload = compatibility_payload(
        outcome,
        last_discovery_payload={
            "company_key": "example",
            "company_name": "Example GmbH",
            "decision": "repair_configuration_blocked",
            "selected_url": None,
        },
    )

    normalized = normalize_explicit_tavily_disable_outcome(
        payload,
        tavily_disabled=True,
    )

    assert normalized["repair_final_state"] == "repair_configuration_blocked"
    assert normalized["repair_configuration_blocked"] is True
