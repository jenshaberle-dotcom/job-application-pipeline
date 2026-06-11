from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.market003d_candidate_expansion_review_action_plan import (
    DISALLOWED_ACTIONS,
    build_action_item,
    build_action_plan,
    build_missing_input_plan,
    load_source_report,
    render_markdown,
    write_outputs,
)


def test_manual_review_item_becomes_human_review_queue_without_mutation() -> None:
    item = build_action_item(
        {
            "company_key": "bahlsen_gmbh_and_co_kg",
            "company_name": "Bahlsen GmbH & Co. KG",
            "review_recommendation": "manual_review_required_manual_market_signal",
            "recommended_next_safe_action": "manual_candidate_expansion_review",
            "evidence_strength_score": 5,
        }
    )

    assert item.review_bucket == "candidate_expansion_human_review_queue"
    assert item.review_priority == "high"
    assert "collect_origin_url_evidence" in item.allowed_review_actions
    assert item.disallowed_actions == DISALLOWED_ACTIONS
    assert item.candidate_creation_allowed is False
    assert item.gate_decision_allowed is False
    assert item.connector_activation_allowed is False


def test_known_candidate_context_remains_context_only() -> None:
    item = build_action_item(
        {
            "company_key": "hdi_group",
            "company_name": "HDI Group",
            "known_candidate_id": "42",
            "review_recommendation": "known_candidate_review_context_only",
            "recommended_next_safe_action": "link_as_review_context_without_candidate_creation",
            "evidence_strength_score": 4,
        }
    )

    assert item.review_bucket == "known_candidate_context_queue"
    assert item.review_priority == "medium"
    assert "confirm_known_candidate_context" in item.allowed_review_actions
    assert "create_candidate" in item.disallowed_actions


def test_action_plan_preserves_no_mutation_boundary() -> None:
    report = build_action_plan(
        {
            "schema_version": "market003c.candidate_expansion_review_no_promotion.v1",
            "items": [
                {
                    "company_key": "getec",
                    "company_name": "GETEC",
                    "review_recommendation": "manual_review_required_evidence_rich_market_signal",
                    "recommended_next_safe_action": "manual_candidate_expansion_review",
                    "evidence_strength_score": 4,
                }
            ],
        },
        generated_at="2026-06-11T20:00:00+00:00",
        input_path="input.json",
    )

    assert report["schema_version"] == "market003d.candidate_expansion_review_action_plan.v1"
    assert report["safety_boundary"]["candidate_creation"] is False
    assert report["safety_boundary"]["gate_decision"] is False
    assert report["safety_boundary"]["connector_activation"] is False
    assert report["mutation_counts"] == {
        "created_candidates": 0,
        "written_gate_decisions": 0,
        "activated_connectors": 0,
        "scheduler_changes": 0,
        "bronze_silver_gold_writes": 0,
    }
    assert report["summary"]["human_review_queue_count"] == 1
    assert report["summary"]["candidate_creation_count"] == 0


def test_missing_input_is_bounded_report_not_crash(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    report = build_missing_input_plan(missing, generated_at="2026-06-11T20:00:00+00:00")

    assert report["input_status"] == "input_missing"
    assert report["summary"]["item_count"] == 0
    assert "Run scripts/run_market003c_candidate_expansion_review.py first" in str(report["input_warning"])


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
    report = build_action_plan(
        {
            "schema_version": "market003c.candidate_expansion_review_no_promotion.v1",
            "items": [
                {
                    "company_key": "medifox_dan",
                    "company_name": "MEDIFOX DAN",
                    "review_recommendation": "insufficient_evidence_review_context_only",
                    "recommended_next_safe_action": "retain_as_market_context_without_candidate_creation",
                    "evidence_strength_score": 2,
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
    assert "No automatic candidate creation" in markdown
    assert "Created candidates: 0" in markdown
