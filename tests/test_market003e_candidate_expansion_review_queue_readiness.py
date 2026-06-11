from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.market003e_candidate_expansion_review_queue_readiness import (
    DISABLED_MUTATING_ACTIONS,
    build_missing_input_report,
    build_queue_card,
    build_queue_readiness_report,
    load_source_report,
    render_markdown,
    write_outputs,
)


def test_human_review_action_item_becomes_read_only_ui_queue_card() -> None:
    card = build_queue_card(
        {
            "company_key": "bahlsen_gmbh_and_co_kg",
            "company_name": "Bahlsen GmbH & Co. KG",
            "review_bucket": "candidate_expansion_human_review_queue",
            "review_priority": "high",
            "source_next_safe_action": "manual_candidate_expansion_review",
            "evidence_gap": None,
        }
    )

    assert card.queue_lane == "needs_human_candidate_expansion_review"
    assert card.ui_status == "review_required"
    assert card.ui_priority_rank == 10
    assert card.evidence_badge == "evidence_ready_for_human_review"
    assert "open_read_only_review_dialog" in card.display_actions
    assert card.disabled_mutating_actions == DISABLED_MUTATING_ACTIONS
    assert card.read_only is True
    assert card.candidate_creation_allowed is False
    assert card.gate_decision_allowed is False
    assert card.connector_activation_allowed is False


def test_known_candidate_context_card_is_context_review_only() -> None:
    card = build_queue_card(
        {
            "company_key": "hdi_group",
            "company_name": "HDI Group",
            "review_bucket": "known_candidate_context_queue",
            "review_priority": "medium",
            "source_next_safe_action": "link_as_review_context_without_candidate_creation",
            "evidence_gap": None,
        }
    )

    assert card.queue_lane == "known_candidate_context_review"
    assert card.ui_status == "context_review"
    assert card.ui_priority_rank == 30
    assert "create_candidate" in card.disabled_mutating_actions


def test_identity_gap_card_is_blocked_for_decision_use() -> None:
    card = build_queue_card(
        {
            "company_key": "unknown_company",
            "company_name": "<missing>",
            "review_bucket": "identity_gap_queue",
            "review_priority": "low",
            "source_next_safe_action": "ignore_until_company_identity_is_clear",
            "evidence_gap": "company_identity_missing",
        }
    )

    assert card.queue_lane == "identity_resolution_needed"
    assert card.ui_status == "blocked_identity_gap"
    assert card.evidence_badge == "identity_gap"
    assert "Company identity is not safe enough" in card.subline


def test_queue_readiness_report_preserves_no_mutation_contract() -> None:
    report = build_queue_readiness_report(
        {
            "schema_version": "market003d.candidate_expansion_review_action_plan.v1",
            "items": [
                {
                    "company_key": "getec",
                    "company_name": "GETEC",
                    "review_bucket": "candidate_expansion_human_review_queue",
                    "review_priority": "medium",
                    "source_next_safe_action": "manual_candidate_expansion_review",
                    "evidence_gap": "needs_origin_or_detail_evidence",
                }
            ],
        },
        generated_at="2026-06-11T20:00:00+00:00",
        input_path="input.json",
    )

    assert report["schema_version"] == "market003e.candidate_expansion_review_ui_queue_readiness.v1"
    assert report["safety_boundary"]["read_only"] is True
    assert report["safety_boundary"]["ui_write_actions"] is False
    assert report["mutation_counts"] == {
        "created_candidates": 0,
        "written_gate_decisions": 0,
        "activated_connectors": 0,
        "scheduler_changes": 0,
        "bronze_silver_gold_writes": 0,
        "database_writes": 0,
        "ui_write_actions": 0,
    }
    assert report["ui_contract"]["read_only_queue_model"] is True
    assert "create_candidate_button" in report["ui_contract"]["disallowed_frontend_capabilities"]
    assert report["summary"]["card_count"] == 1
    assert report["summary"]["candidate_creation_count"] == 0


def test_missing_input_is_bounded_report_not_crash(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    report = build_missing_input_report(missing, generated_at="2026-06-11T20:00:00+00:00")

    assert report["input_status"] == "input_missing"
    assert report["summary"]["card_count"] == 0
    assert "Run scripts/run_market003d_candidate_expansion_review_action_plan.py first" in str(report["input_warning"])


def test_load_source_report_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"schema_version": "wrong.v1", "items": []}), encoding="utf-8")

    try:
        load_source_report(path)
    except ValueError as exc:
        assert "Unexpected input schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError")


def test_outputs_are_export_only(tmp_path: Path) -> None:
    report = build_queue_readiness_report(
        {
            "schema_version": "market003d.candidate_expansion_review_action_plan.v1",
            "items": [
                {
                    "company_key": "medifox_dan",
                    "company_name": "MEDIFOX DAN",
                    "review_bucket": "insufficient_evidence_context_queue",
                    "review_priority": "low",
                    "source_next_safe_action": "retain_as_market_context_without_candidate_creation",
                    "evidence_gap": "weak_market_signal",
                }
            ],
        },
        generated_at="2026-06-11T20:00:00+00:00",
        input_path="input.json",
    )

    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    markdown = render_markdown(report)
    assert "Read-only UI queue model" in markdown
    assert "Created candidates: 0" in markdown
    assert "UI write actions: 0" in markdown
