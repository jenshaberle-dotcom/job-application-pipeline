from __future__ import annotations

import json
from pathlib import Path

from src.search_intelligence.eo002c_reprocessing_decision_report import (
    build_decision_recommendations,
    build_decision_report,
    load_metrics_from_reports,
    normalize_metric,
    render_markdown_report,
    summarize_metrics,
)

SCRIPT = Path("scripts/run_eo002c_reprocessing_decision_report.py")


def test_normalize_metric_keeps_required_decision_fields() -> None:
    metric = normalize_metric(
        {
            "candidate_id": "7",
            "company_key": "hannover_ruck",
            "company_name": "Hannover Rück SE",
            "success_tier": "a",
            "selected_url": "https://jobs.hannover-re.com/",
            "confidence_score": "0.91",
            "decision": "origin_url_candidate_selected",
            "gate_stop": "detail_evidence_gate",
            "false_negative_candidate": "true",
            "alternative_url_count": "2",
            "rejected_url_count": "3",
            "risk_level": "low",
            "reason": "selected best origin source candidate",
        }
    )

    assert metric.candidate_id == 7
    assert metric.company_key == "hannover_ruck"
    assert metric.success_tier == "A"
    assert metric.selected_url == "https://jobs.hannover-re.com/"
    assert metric.confidence_score == 0.91
    assert metric.false_negative_candidate is True
    assert metric.alternative_url_count == 2
    assert metric.rejected_url_count == 3


def test_summarize_metrics_counts_tiers_gate_stops_and_read_only_boundary() -> None:
    metrics = [
        normalize_metric(
            {
                "company_key": "hannover_ruck",
                "company_name": "Hannover Rück SE",
                "success_tier": "A",
                "selected_url": "https://jobs.hannover-re.com/",
                "confidence_score": 0.9,
                "decision": "origin_url_candidate_selected",
                "gate_stop": "detail_evidence_gate",
                "false_negative_candidate": True,
            }
        ),
        normalize_metric(
            {
                "company_key": "vhv",
                "company_name": "VHV Gruppe",
                "success_tier": "D",
                "selected_url": None,
                "confidence_score": 0.1,
                "decision": "not_found",
                "gate_stop": None,
                "false_negative_candidate": False,
            }
        ),
    ]

    summary = summarize_metrics(metrics)

    assert summary["candidate_count"] == 2
    assert summary["selected_url_count"] == 1
    assert summary["selected_url_rate"] == 0.5
    assert summary["success_tier_counts"] == {"A": 1, "B": 0, "C": 0, "D": 1}
    assert summary["gate_stop_counts"]["detail_evidence_gate"] == 1
    assert summary["gate_stop_counts"]["<none>"] == 1
    assert summary["boundary"]["read_only_decision_report"] is True
    assert summary["boundary"]["no_scheduler_change"] is True


def test_decision_recommendations_do_not_jump_to_scheduler_or_gate_rewrite() -> None:
    metrics = [
        normalize_metric(
            {
                "company_key": "hdi",
                "success_tier": "D",
                "selected_url": None,
                "confidence_score": 0.1,
                "decision": "not_found",
                "false_negative_candidate": True,
            }
        )
    ]

    recommendations = build_decision_recommendations(metrics)

    assert any("prioritize_url_finder_repair" in item for item in recommendations)
    assert any("inspect_false_negative_candidates" in item for item in recommendations)
    assert any("keep_scheduler_changes_deferred" in item for item in recommendations)


def test_load_metrics_from_reports_deduplicates_and_renders_markdown(tmp_path: Path) -> None:
    report_path = tmp_path / "eo002b.json"
    payload = {
        "metrics": [
            {
                "candidate_id": 1,
                "company_key": "hannover_ruck",
                "company_name": "Hannover Rück SE",
                "success_tier": "A",
                "selected_url": "https://jobs.hannover-re.com/",
                "confidence_score": 0.91,
                "decision": "origin_url_candidate_selected",
                "gate_stop": "detail_evidence_gate",
                "false_negative_candidate": True,
            },
            {
                "candidate_id": 1,
                "company_key": "hannover_ruck",
                "company_name": "Hannover Rück SE",
                "success_tier": "A",
                "selected_url": "https://jobs.hannover-re.com/",
                "confidence_score": 0.91,
                "decision": "origin_url_candidate_selected",
                "gate_stop": "detail_evidence_gate",
                "false_negative_candidate": True,
            },
        ]
    }
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    metrics = load_metrics_from_reports([report_path])
    report = build_decision_report(metrics, benchmark_label="eo002c_test", source_reports=[str(report_path)])
    markdown = render_markdown_report(report)

    assert len(metrics) == 1
    assert report["summary"]["candidate_count"] == 1
    assert report["false_negative_candidates"][0]["company_key"] == "hannover_ruck"
    assert "EO-002C Reprocessing Metrics & Decision Report" in markdown
    assert "Hannover Rück SE" in markdown
    assert "read-only" in markdown


def test_eo002c_script_is_report_only_and_has_no_apply_flag() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "read-only metrics and decision report" in text
    assert "--report-json" in text
    assert "--input-dir" in text
    assert "--output-dir" in text
    assert "--apply" not in text
    assert "UPDATE " not in text
    assert "INSERT " not in text
    assert "DELETE " not in text


def test_render_markdown_names_decision_confidence_explicitly() -> None:
    report = build_decision_report(
        [
            normalize_metric(
                {
                    "company_key": "hannover_ruck",
                    "company_name": "Hannover Rück SE",
                    "success_tier": "D",
                    "selected_url": None,
                    "confidence_score": 1.0,
                    "decision": "not_found",
                    "false_negative_candidate": True,
                }
            )
        ],
        benchmark_label="eo002c_confidence_wording",
        source_reports=[],
    )

    markdown = render_markdown_report(report)

    assert "Decision confidence describes confidence in the URL-finder decision" in markdown
    assert "Average decision confidence" in markdown
    assert "Average confidence" not in markdown


def test_eo002c_script_filters_empty_report_path_and_rejects_directories() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "if str(raw_path).strip()" in text
    assert "path.is_dir()" in text
    assert "not a JSON file" in text
