from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.market003c_candidate_expansion_review import (
    NO_PROMOTION_BOUNDARY,
    build_report,
    build_review_items,
    normalize_company_key,
    render_markdown,
    write_outputs,
)


def test_normalize_company_key_is_conservative_and_does_not_strip_suffixes() -> None:
    assert normalize_company_key("adesso business consulting GmbH") == "adesso_business_consulting_gmbh"
    assert normalize_company_key("adesso SE") == "adesso_se"


def test_manual_market_observation_requires_review_without_promotion() -> None:
    items = build_review_items(
        [
            {
                "id": 17,
                "company_name": "Bahlsen GmbH & Co. KG",
                "evidence_origin": "manual_market_observation",
                "job_title": "Data Engineer",
                "source_url": "https://example.invalid/jobs/data-engineer",
                "notes": "Observed manually from market research.",
            }
        ],
        [],
    )

    assert len(items) == 1
    item = items[0]
    assert item.review_recommendation == "manual_review_required_manual_market_signal"
    assert item.recommended_next_safe_action == "manual_candidate_expansion_review"
    assert item.promotion_blocker == NO_PROMOTION_BOUNDARY
    assert item.candidate_creation_allowed is False
    assert item.gate_decision_allowed is False
    assert item.connector_activation_allowed is False


def test_known_candidate_is_context_only() -> None:
    items = build_review_items(
        [
            {
                "id": 1,
                "company_name": "HDI Group",
                "evidence_origin": "manual_market_observation",
                "job_title": "Analytics Engineer",
            }
        ],
        [{"id": 42, "company_key": "hdi_group", "company_name": "HDI Group", "status": "discovery"}],
    )

    item = items[0]
    assert item.review_recommendation == "known_candidate_review_context_only"
    assert item.known_candidate_id == "42"
    assert item.known_candidate_status == "discovery"
    assert item.recommended_next_safe_action == "link_as_review_context_without_candidate_creation"


def test_report_preserves_no_mutation_boundary() -> None:
    report = build_report(
        market_evidence_payloads=[{"company_name": "GETEC", "evidence_origin": "manual_market_observation", "notes": "manual"}],
        existing_candidate_payloads=[],
        generated_at="2026-06-11T20:00:00+00:00",
        db_access_method="input_json",
    )

    assert report["schema_version"] == "market003c.candidate_expansion_review_no_promotion.v1"
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
    assert report["summary"]["candidate_creation_count"] == 0


def test_outputs_are_export_only(tmp_path: Path) -> None:
    report = build_report(
        market_evidence_payloads=[{"company_name": "MEDIFOX DAN", "evidence_origin": "manual_market_observation", "notes": "manual"}],
        existing_candidate_payloads=[],
        generated_at="2026-06-11T20:00:00+00:00",
        db_access_method="input_json",
    )

    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    markdown = render_markdown(report)
    assert "No automatic candidate creation" in markdown
    assert "Created candidates: 0" in markdown
