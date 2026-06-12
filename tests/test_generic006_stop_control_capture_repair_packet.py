from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.generic006_stop_control_capture_repair_packet import (
    BLOCKED_STATUS,
    READY_STATUS,
    assess_capture_row,
    build_stop_control_capture_repair_packet,
    stop_control_rows_from_generic004_report,
    find_latest_generic004_report,
    find_latest_generic005_report,
    render_markdown,
    write_outputs,
)


def _generic004_report() -> dict[str, object]:
    return {
        "schema_version": "generic004.stop_control_evidence_capture_plan.v1",
        "overall_status": "operator_capture_required_missing_stop_control_evidence",
    }


def _generic005_report() -> dict[str, object]:
    return {
        "schema_version": "generic005.stop_control_final_rerun.v1",
        "overall_status": "stop_control_capture_missing_or_invalid",
        "summary": {
            "accepted_stop_control_count": 0,
            "rejected_stop_control_count": 1,
            "final_gap_ids": ["no_actionable_evidence_coverage", "negative_control_coverage"],
        },
    }


def _placeholder_row() -> dict[str, object]:
    return {
        "control_type": "new_clean_no_actionable_negative_control",
        "required_for_gap_ids": "no_actionable_evidence_coverage;negative_control_coverage",
        "company_key": "",
        "company_name": "",
        "review_action": "no_useful_external_hint_no_candidate_creation",
        "evidence_strength": "none",
        "evidence_summary": "Describe why no company-origin/detail/provider evidence was actionable after bounded review.",
        "reviewer": "",
        "review_date": "",
        "boundary": "review_artifact_only_no_candidate_or_gate_write",
    }


def _ready_row() -> dict[str, object]:
    return {
        "control_type": "new_clean_no_actionable_negative_control",
        "required_for_gap_ids": "no_actionable_evidence_coverage;negative_control_coverage",
        "company_key": "negative_control_company",
        "company_name": "Negative Control GmbH",
        "review_action": "no_useful_external_hint_no_candidate_creation",
        "evidence_strength": "none",
        "evidence_summary": "Bounded review found no actionable origin, detail, or provider evidence for this company.",
        "reviewer": "jens",
        "review_date": "2026-06-12",
        "boundary": "review_artifact_only_no_candidate_or_gate_write",
    }


def test_assess_capture_row_reports_all_placeholder_gaps() -> None:
    assessment = assess_capture_row(_placeholder_row(), 1)

    assert assessment.repair_status == "operator_repair_required"
    assert set(assessment.missing_or_invalid_fields) == {
        "company_key",
        "company_name",
        "evidence_summary",
        "reviewer",
        "review_date",
    }


def test_ready_row_allows_generic005_rerun_but_not_apply() -> None:
    report = build_stop_control_capture_repair_packet(_generic004_report(), _generic005_report(), [_ready_row()])

    assert report["overall_status"] == READY_STATUS
    assert report["summary"]["ready_for_generic005_rerun_count"] == 1
    assert report["summary"]["safe_rerun_command_available"] is True
    assert report["mutation_counts"]["database_writes"] == 0
    assert report["safety_boundary"]["candidate_creation"] is False


def test_placeholder_report_stays_blocked() -> None:
    report = build_stop_control_capture_repair_packet(_generic004_report(), _generic005_report(), [_placeholder_row()])

    assert report["overall_status"] == BLOCKED_STATUS
    assert report["summary"]["blocked_capture_row_count"] == 1
    assert report["summary"]["missing_or_invalid_field_counts"]["company_key"] == 1
    assert report["safe_rerun_command"] is None


def test_markdown_and_outputs_include_repair_fields_without_csv(tmp_path: Path) -> None:
    report = build_stop_control_capture_repair_packet(_generic004_report(), _generic005_report(), [_placeholder_row()])
    markdown = render_markdown(report)
    outputs = write_outputs(report, tmp_path)

    assert "GENERIC-006 Stop-Control Evidence Repair Packet" in markdown
    assert "company_key" in markdown
    assert Path(outputs["json"]).exists()
    assert "csv" not in outputs
    assert Path(outputs["markdown"]).exists()


def test_latest_report_finders_and_generic004_row_loader(tmp_path: Path) -> None:
    generic004_dir = tmp_path / "generic004_stop_control_evidence_capture_plan"
    generic004_dir.mkdir()
    generic004_path = generic004_dir / "generic004_stop_control_evidence_capture_plan.json"
    generic004_payload = dict(_generic004_report())
    generic004_payload["stop_control_evidence_requirements"] = [_placeholder_row()]
    generic004_path.write_text(json.dumps(generic004_payload), encoding="utf-8")

    generic005_dir = tmp_path / "generic005_stop_control_final_rerun"
    generic005_dir.mkdir()
    generic005_path = generic005_dir / "generic005_stop_control_final_rerun.json"
    generic005_path.write_text(json.dumps(_generic005_report()), encoding="utf-8")

    assert find_latest_generic004_report(tmp_path) == generic004_path
    assert stop_control_rows_from_generic004_report(generic004_payload)[0]["review_action"] == "no_useful_external_hint_no_candidate_creation"
    assert find_latest_generic005_report(tmp_path) == generic005_path


def test_runner_writes_repair_packet_with_explicit_inputs(tmp_path: Path) -> None:
    generic004_path = tmp_path / "generic004.json"
    generic005_path = tmp_path / "generic005.json"
    output_dir = tmp_path / "out"
    generic004_payload = dict(_generic004_report())
    generic004_payload["stop_control_evidence_requirements"] = [_placeholder_row()]
    generic004_path.write_text(json.dumps(generic004_payload), encoding="utf-8")
    generic005_path.write_text(json.dumps(_generic005_report()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_generic006_stop_control_capture_repair_packet.py",
            "--generic004-input",
            str(generic004_path),
            "--generic005-input",
            str(generic005_path),
            "--export-dir",
            str(output_dir),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "overall_status=operator_stop_control_capture_repair_required" in result.stdout
    assert "company_key" in result.stdout
    assert (output_dir / "generic006_stop_control_capture_repair_packet.json").exists()
