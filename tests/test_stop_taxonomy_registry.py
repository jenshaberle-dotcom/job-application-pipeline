from __future__ import annotations

from pathlib import Path

from src.search_intelligence.gate_stop_classification import classify_gate_stop
from src.search_intelligence.stop_taxonomy import (
    STOP_TAXONOMY,
    categories_by_lifecycle_class,
    repair_strategy_for_category,
    stop_taxonomy_evidence,
    taxonomy_reference_rows,
    validate_stop_taxonomy,
)

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/reference/search-intelligence/stop_taxonomy_and_repair_registry.md"


def test_stop_taxonomy_registry_is_internally_consistent() -> None:
    assert validate_stop_taxonomy() == []

    for category in STOP_TAXONOMY:
        strategy = repair_strategy_for_category(category)
        assert strategy.strategy_id
        assert strategy.safety_zone.startswith("SZ")
        assert strategy.default_next_safe_action


def test_stop_taxonomy_separates_good_stops_from_false_negative_risk_stops() -> None:
    assert categories_by_lifecycle_class("good_stop") == ("terminal_access_risk",)
    assert set(categories_by_lifecycle_class("false_negative_risk_stop")) == {
        "detail_discovery_gap",
        "recoverable_url_problem",
        "weak_relevance_evidence",
    }


def test_detail_discovery_gap_classification_carries_repair_registry_fields() -> None:
    classification = classify_gate_stop(
        gate_name="detail_evidence_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="bounded repair found no concrete detail pages with profile and target signals",
        evidence={"details": []},
    )

    assert classification.category == "detail_discovery_gap"
    assert classification.lifecycle_class == "false_negative_risk_stop"
    assert classification.false_negative_risk == "high"
    assert classification.repair_strategy_id == "bounded_detail_evidence_discovery"
    assert classification.recommended_next_safe_action == "run_detail_evidence_discovery_plan"
    assert classification.safety_zone == "SZ2_EVIDENCE_AND_GATES"

    evidence = classification.as_evidence()
    assert evidence["stop_lifecycle_class"] == "false_negative_risk_stop"
    assert evidence["repair_strategy_id"] == "bounded_detail_evidence_discovery"
    assert evidence["dry_run_required"] is True
    assert evidence["explicit_apply_required"] is True


def test_terminal_access_risk_is_registered_as_good_fail_closed_stop() -> None:
    evidence = stop_taxonomy_evidence("terminal_access_risk")

    assert evidence["stop_lifecycle_class"] == "good_stop"
    assert evidence["terminal"] is True
    assert evidence["default_reprocess"] == "block_without_explicit_override"
    assert evidence["human_review_required"] is True
    assert evidence["recommended_next_safe_action"] == "manual_review_terminal_stop"


def test_taxonomy_reference_rows_are_ui_and_report_ready() -> None:
    rows = taxonomy_reference_rows(["recoverable_url_problem", "terminal_access_risk"])

    assert [row["category"] for row in rows] == [
        "recoverable_url_problem",
        "terminal_access_risk",
    ]
    assert rows[0]["repair_label"] == "Bounded source URL recovery"
    assert rows[1]["lifecycle_class"] == "good_stop"


def test_stop002_reference_document_exists_and_links_to_code_contract() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "STOP-002" in text
    assert "src/search_intelligence/stop_taxonomy.py" in text
    assert "false_negative_risk_stop" in text
    assert "bounded_detail_evidence_discovery" in text
