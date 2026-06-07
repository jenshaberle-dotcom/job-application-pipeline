from __future__ import annotations

from pathlib import Path

from src.search_intelligence.eo002b_url_finder_validation import (
    SUCCESS_TIER_A,
    SUCCESS_TIER_C,
    SUCCESS_TIER_D,
    classify_success_tier,
    metric_from_discovery_payload,
    report_payload,
    summarize_metrics,
)

REPROCESS_SCRIPT = Path("scripts/run_employer_origin_reprocess_benchmark.py")
VALIDATION_SCRIPT = Path("scripts/run_eo002b_url_finder_validation.py")


def test_success_tier_classification_separates_selected_manual_and_failed() -> None:
    assert classify_success_tier(
        decision="origin_url_candidate_selected",
        confidence_score=0.82,
        selected_url="https://jobs.hannover-re.com/",
    ) == SUCCESS_TIER_A
    assert classify_success_tier(
        decision="manual_review_required",
        confidence_score=0.61,
        selected_url=None,
    ) == SUCCESS_TIER_C
    assert classify_success_tier(
        decision="not_found",
        confidence_score=0.1,
        selected_url=None,
    ) == SUCCESS_TIER_D


def test_metric_from_discovery_payload_keeps_required_evidence_fields() -> None:
    metric = metric_from_discovery_payload(
        {
            "candidate_id": 42,
            "company_key": "hannover_ruck",
            "company_name": "Hannover Rück SE",
            "candidate_status": "discovery",
            "candidate_url_before": None,
            "decision": "origin_url_candidate_selected",
            "selected_url": "https://jobs.hannover-re.com/",
            "confidence_score": 0.91,
            "risk_level": "low",
            "alternatives": [{"url": "https://jobs.hannover-re.com/"}],
            "rejected": [{"url": "https://jobs.hannover.de/"}],
            "candidate_risk_level": "critical",
            "reason": "selected best origin source candidate",
        },
        gate_stop="origin_source_discovery_gate",
    )

    assert metric.company_key == "hannover_ruck"
    assert metric.selected_url == "https://jobs.hannover-re.com/"
    assert metric.alternative_url_count == 1
    assert metric.rejected_url_count == 1
    assert metric.success_tier == SUCCESS_TIER_A
    assert metric.false_negative_candidate is True
    assert metric.gate_stop == "origin_source_discovery_gate"


def test_report_payload_contains_read_only_boundaries_and_tier_counts() -> None:
    metrics = [
        metric_from_discovery_payload(
            {
                "company_key": "hdi",
                "company_name": "HDI Group",
                "decision": "not_found",
                "confidence_score": 0.0,
                "alternatives": [],
                "rejected": [],
            }
        )
    ]

    summary = summarize_metrics(metrics)
    report = report_payload(metrics, benchmark_label="eo002b_20260607")

    assert summary["candidate_count"] == 1
    assert summary["success_tier_counts"][SUCCESS_TIER_D] == 1
    assert summary["boundary"]["no_candidate_url_write"] is True
    assert summary["boundary"]["no_connector_registration"] is True
    assert report["campaign"] == "EO-002B Candidate Reprocessing & URL Finder Validation"
    assert "next_decision_questions" in report


def test_reprocess_benchmark_supports_explicit_guest_list_and_active_controlled_guard() -> None:
    text = REPROCESS_SCRIPT.read_text(encoding="utf-8")

    assert "--company-key" in text
    assert "Explicit guest-list company key" in text
    assert "active_controlled without --include-active-controlled" in text
    assert "array_position(%s::text[], c.company_key)" in text
    assert "guest_list_candidate_ids" in text


def test_eo002b_validation_script_is_report_only_and_has_no_apply_flag() -> None:
    text = VALIDATION_SCRIPT.read_text(encoding="utf-8")

    assert "read-only URL Finder validation" in text
    assert "--company-key" in text
    assert "--search-results-json" in text
    assert "--include-active-controlled" in text
    assert "no_candidate_url_write" in text
    assert "no_connector_registration" in text
    assert "--apply" not in text
    assert "candidate_url write" not in text.lower()
