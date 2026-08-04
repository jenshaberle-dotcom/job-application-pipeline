from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_origin_url_budgeted_audit import (
    load_seed_hints,
    run_company_phases,
    seed_urls_from_selected_url,
)


def _args(*, phase: str = "two-stage") -> SimpleNamespace:
    return SimpleNamespace(
        phase=phase,
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
        search_depth="basic",
        max_evidence_candidates=4,
        max_evidence_http_requests=12,
        evidence_timeout_seconds=1.0,
        max_response_bytes=10_000,
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
        max_llm_requests=50,
        disable_tavily=False,
        disable_llm=False,
    )


def _payload(final_state: str, selected_url: str | None = None) -> dict[str, object]:
    return {
        "default_repair": {
            "final_state": final_state,
            "selected_url": selected_url,
        }
    }


def test_job_detail_seed_places_portal_before_original_detail() -> None:
    assert seed_urls_from_selected_url(
        "https://job-boards.greenhouse.io/zscaler/jobs/5193808007"
    ) == (
        "https://job-boards.greenhouse.io/zscaler",
        "https://job-boards.greenhouse.io/zscaler/jobs/5193808007",
    )


def test_seed_artifact_is_review_only_and_urls_remain_hints(tmp_path: Path) -> None:
    artifact = tmp_path / "audit.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "origin_url_database_audit.v2",
                "generated_at_utc": "2026-08-03T20:07:38+00:00",
                "review_output_only_not_pipeline_input": True,
                "database_write": False,
                "companies": [
                    {
                        "company_key": "zscaler_germany",
                        "selected_url": (
                            "https://job-boards.greenhouse.io/zscaler/jobs/5193808007"
                        ),
                    },
                    {
                        "company_key": "aok",
                        "selected_url": None,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    hints, provenance = load_seed_hints((artifact,))

    assert hints["zscaler_germany"] == (
        "https://job-boards.greenhouse.io/zscaler",
        "https://job-boards.greenhouse.io/zscaler/jobs/5193808007",
    )
    assert "aok" not in hints
    assert provenance[0]["selected_rows_used_as_untrusted_hints"] == 1


def test_seed_artifact_without_review_boundary_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "unsafe.json"
    artifact.write_text(
        json.dumps(
            {
                "review_output_only_not_pipeline_input": False,
                "database_write": False,
                "companies": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not review-only"):
        load_seed_hints((artifact,))


def test_deterministic_selection_stops_before_provider_phase() -> None:
    calls: list[SimpleNamespace] = []

    def runner(args, company_key):  # type: ignore[no-untyped-def]
        assert company_key == "1_1"
        calls.append(args)
        return _payload(
            "selected_deterministic_symbol_brand",
            "https://career.1and1.org/",
        )

    payload, phase_a, phase = run_company_phases(
        _args(),
        company_key="1_1",
        operator_urls=("https://career.1and1.org/",),
        runner=runner,
    )

    assert payload["default_repair"]["selected_url"] == "https://career.1and1.org/"
    assert phase_a is None
    assert phase == "phase_a_deterministic"
    assert len(calls) == 1
    assert calls[0].disable_tavily is True
    assert calls[0].disable_llm is True
    assert calls[0].operator_url == ["https://career.1and1.org/"]


def test_provider_phase_runs_only_after_deterministic_miss() -> None:
    calls: list[SimpleNamespace] = []

    def runner(args, company_key):  # type: ignore[no-untyped-def]
        calls.append(args)
        if len(calls) == 1:
            return _payload("repair_configuration_blocked")
        return _payload(
            "selected_tavily_repair",
            "https://careers.example.com/",
        )

    payload, phase_a, phase = run_company_phases(
        _args(),
        company_key="example",
        operator_urls=(),
        runner=runner,
    )

    assert phase == "phase_b_provider"
    assert phase_a is not None
    assert payload["default_repair"]["selected_url"] == "https://careers.example.com/"
    assert len(calls) == 2
    assert calls[0].disable_tavily is True
    assert calls[1].disable_tavily is False


def test_deterministic_mode_never_opens_provider_phase() -> None:
    calls: list[SimpleNamespace] = []

    def runner(args, company_key):  # type: ignore[no-untyped-def]
        calls.append(args)
        return _payload("repair_configuration_blocked")

    payload, phase_a, phase = run_company_phases(
        _args(phase="deterministic"),
        company_key="example",
        operator_urls=(),
        runner=runner,
    )

    assert payload["default_repair"]["final_state"] == "repair_configuration_blocked"
    assert phase_a is None
    assert phase == "phase_a_unresolved"
    assert len(calls) == 1
