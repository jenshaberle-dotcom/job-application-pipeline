from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.expand003_candidate_review_delta_report import (
    build_candidate_review_delta_report,
    build_candidate_review_items,
    find_latest_expand002_report,
    load_expand002_report,
    render_markdown,
    write_outputs,
)


def _probe_result(
    *,
    trial_id: str,
    company_key: str,
    company_name: str,
    evidence_hint: str,
    urls: list[str],
    classes: list[str],
    status: str = "completed",
) -> dict[str, object]:
    return {
        "probe_id": f"probe::{company_key}",
        "trial_id": trial_id,
        "company_key": company_key,
        "company_name": company_name,
        "stage": "origin_url_discovery_probe",
        "query": f"{company_name} jobs",
        "provider": "tavily",
        "status": status,
        "request_executed": True,
        "result_count": len(urls),
        "urls": urls,
        "titles": [],
        "evidence_hint": evidence_hint,
        "url_evidence_classes": classes,
    }


def _expand002_report() -> dict[str, object]:
    return {
        "schema_version": "expand002.controlled_external_probe_trial_run.v1",
        "generated_at_utc": "2026-06-12T16:31:23+00:00",
        "summary": {"candidate_count": 3},
        "probe_results": [
            _probe_result(
                trial_id="expand001::cancom::ready_for_controlled_external_trial",
                company_key="cancom",
                company_name="CANCOM SE",
                evidence_hint="origin_or_career_hint_found",
                urls=["https://career.cancom.com/jobs", "https://dailyremote.com/remote-data-engineer"],
                classes=["company_origin_or_career_url", "aggregator_or_market_url"],
            ),
            _probe_result(
                trial_id="expand001::adesso::ready_for_controlled_external_trial",
                company_key="adesso",
                company_name="adesso SE",
                evidence_hint="company_specific_job_detail_hint_found",
                urls=["https://www.adesso.de/en/services/data-and-analytics/roles.jsp"],
                classes=["company_specific_job_detail_url"],
            ),
            _probe_result(
                trial_id="expand001::apo_data_service::ready_for_controlled_external_trial",
                company_key="apo_data_service",
                company_name="APO Data-Service GmbH",
                evidence_hint="weak_market_or_aggregator_hint_found",
                urls=["https://dailyremote.com/remote-analytics-engineer-jobs-in-germany"],
                classes=["aggregator_or_market_url"],
            ),
        ],
    }


def test_build_candidate_review_items_prioritizes_detail_origin_then_weak() -> None:
    items = build_candidate_review_items(_expand002_report()["probe_results"])

    assert [item.company_key for item in items] == ["adesso", "cancom", "apo_data_service"]
    assert items[0].review_action == "ready_for_human_evidence_review"
    assert items[0].evidence_strength == "strong_detail"
    assert items[1].review_action == "ready_for_detail_followup_review"
    assert items[1].evidence_strength == "strong_origin"
    assert items[2].review_action == "weak_external_hint_no_candidate_creation"
    assert not any(item.candidate_creation_allowed_by_this_report for item in items)


def test_report_summary_keeps_review_counts_separate_from_mutation_counts() -> None:
    report = build_candidate_review_delta_report(_expand002_report(), input_path="expand002.json")

    assert report["schema_version"] == "expand003.candidate_review_delta_report.v1"
    assert report["summary"]["candidate_count"] == 3
    assert report["summary"]["ready_for_human_evidence_review_count"] == 1
    assert report["summary"]["ready_for_detail_followup_review_count"] == 1
    assert report["summary"]["weak_external_hint_no_candidate_creation_count"] == 1
    assert report["summary"]["candidate_creation_count"] == 0
    assert report["summary"]["gate_decision_count"] == 0
    assert report["summary"]["connector_activation_count"] == 0
    assert report["mutation_counts"]["database_writes"] == 0


def test_outputs_are_review_artifacts_only(tmp_path: Path) -> None:
    report = build_candidate_review_delta_report(_expand002_report(), input_path="expand002.json")
    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    markdown = render_markdown(report)
    assert "EXPAND-003 Candidate Review Delta Report" in markdown
    assert "Review artifact only" in markdown
    assert "career.cancom.com" in markdown


def test_load_expand002_report_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"schema_version": "wrong.v1"}), encoding="utf-8")

    try:
        load_expand002_report(path)
    except ValueError as exc:
        assert "Unexpected input schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError")


def test_find_latest_expand002_report_prefers_newest_timestamped_export(tmp_path: Path) -> None:
    old_dir = tmp_path / "expand002_controlled_external_probe_trial_run_20260612-100000"
    new_dir = tmp_path / "expand002_controlled_external_probe_trial_run_20260612-110000"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "expand002_controlled_external_probe_trial_run.json"
    new_path = new_dir / "expand002_controlled_external_probe_trial_run.json"
    old_path.write_text(json.dumps(_expand002_report()), encoding="utf-8")
    new_path.write_text(json.dumps(_expand002_report()), encoding="utf-8")
    old_path.touch()
    new_path.touch()

    assert find_latest_expand002_report(tmp_path) == new_path


def test_runner_creates_delta_report_from_explicit_input(tmp_path: Path) -> None:
    input_path = tmp_path / "expand002.json"
    export_dir = tmp_path / "out"
    input_path.write_text(json.dumps(_expand002_report()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_expand003_candidate_review_delta_report.py",
            "--input",
            str(input_path),
            "--export-dir",
            str(export_dir),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ready_for_human_evidence_review_count=1" in result.stdout
    assert "candidate_creation_count=0" in result.stdout
    assert (export_dir / "expand003_candidate_review_delta_report.json").exists()
