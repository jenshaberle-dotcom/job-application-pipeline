from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.expand007_controlled_candidate_creation_apply_gate_readiness import (
    build_apply_gate_readiness_report,
    find_latest_expand004_report,
    find_latest_expand006_report,
    render_markdown,
    write_outputs,
)


def _dry_run_item(*, selected: bool = True, readiness: str = "ready_for_operator_creation_preview") -> dict[str, object]:
    return {
        "company_key": "adesso_business_consulting",
        "company_name": "adesso business consulting AG",
        "dry_run_lane": "detail_ready_candidate_creation_preview",
        "dry_run_readiness": readiness,
        "selected_for_creation_dry_run": selected,
        "planned_candidate_action": "preview_candidate_record_from_detail_evidence_after_operator_apply_gate",
        "expected_artifacts": ["candidate_identity_preview", "detail_evidence_snapshot"],
        "required_operator_checks": ["confirm_company_identity_not_alias_collision"],
    }


def _expand004_ready() -> dict[str, object]:
    return {
        "schema_version": "expand004.controlled_candidate_creation_dry_run.v1",
        "overall_status": "ready_for_operator_candidate_creation_dry_run_review",
        "summary": {
            "generics_ready_for_candidate_creation_dry_run": True,
            "generic001_final_gap_ids": [],
            "selected_candidate_creation_dry_run_count": 1,
            "selected_candidate_creation_dry_run_keys": ["adesso_business_consulting"],
        },
        "candidate_creation_dry_run_items": [_dry_run_item()],
    }


def _expand004_blocked() -> dict[str, object]:
    return {
        "schema_version": "expand004.controlled_candidate_creation_dry_run.v1",
        "overall_status": "blocked_by_generic005_final_rerun",
        "summary": {
            "generics_ready_for_candidate_creation_dry_run": False,
            "generic001_final_gap_ids": ["no_actionable_evidence_coverage", "negative_control_coverage"],
            "selected_candidate_creation_dry_run_count": 0,
            "selected_candidate_creation_dry_run_keys": [],
        },
        "candidate_creation_dry_run_items": [_dry_run_item(selected=False, readiness="blocked_until_generic_final_pass")],
    }


def _expand006_inspectable() -> dict[str, object]:
    return {
        "schema_version": "expand006.candidate_creation_evidence_review.v1",
        "database": {"status": "pass", "relation_count": 3},
        "apply_boundary": {
            "decision_boundary": "review_only_not_apply",
            "candidate_creation_allowed_by_this_report": False,
            "review_signal_strength": "inspectable",
        },
    }


def _expand006_context_only() -> dict[str, object]:
    return {
        "schema_version": "expand006.candidate_creation_evidence_review.v1",
        "database": {"status": "unavailable", "relations": []},
        "apply_boundary": {
            "decision_boundary": "review_only_not_apply",
            "candidate_creation_allowed_by_this_report": False,
            "review_signal_strength": "context_only",
        },
    }


def test_apply_gate_readiness_stays_blocked_for_current_generic_gaps() -> None:
    report = build_apply_gate_readiness_report(_expand004_blocked(), _expand006_context_only())

    assert report["schema_version"] == "expand007.controlled_candidate_creation_apply_gate_readiness.v1"
    assert report["overall_status"] == "blocked_before_apply_gate_design"
    assert report["apply_gate_boundary"]["apply_gate_design_allowed_by_this_report"] is False
    assert report["apply_gate_boundary"]["candidate_creation_execution_allowed_by_this_report"] is False
    assert report["summary"]["generic_gap_ids"] == ["no_actionable_evidence_coverage", "negative_control_coverage"]
    assert report["summary"]["selected_candidate_creation_dry_run_count"] == 0
    assert report["mutation_counts"]["database_writes"] == 0


def test_ready_inputs_only_allow_future_design_not_apply_execution() -> None:
    report = build_apply_gate_readiness_report(_expand004_ready(), _expand006_inspectable())

    assert report["overall_status"] == "ready_for_manual_apply_gate_design_review_not_apply"
    assert report["apply_gate_boundary"]["apply_gate_design_allowed_by_this_report"] is True
    assert report["apply_gate_boundary"]["candidate_creation_execution_allowed_by_this_report"] is False
    assert report["summary"]["ready_for_manual_apply_gate_design_keys"] == ["adesso_business_consulting"]
    assessment = report["candidate_apply_gate_assessments"][0]
    assert assessment["apply_gate_readiness"] == "ready_for_manual_apply_gate_design_review"
    assert assessment["candidate_creation_allowed_by_this_report"] is False


def test_context_only_expand006_blocks_even_when_expand004_is_ready() -> None:
    report = build_apply_gate_readiness_report(_expand004_ready(), _expand006_context_only())

    assert report["overall_status"] == "blocked_before_apply_gate_design"
    assert report["summary"]["ready_for_manual_apply_gate_design_count"] == 0
    blockers = report["candidate_apply_gate_assessments"][0]["blocker_reasons"]
    assert "expand006_evidence_review_not_db_inspectable" in blockers


def test_markdown_and_outputs_include_boundary(tmp_path: Path) -> None:
    report = build_apply_gate_readiness_report(_expand004_blocked(), _expand006_context_only())
    markdown = render_markdown(report)
    outputs = write_outputs(report, tmp_path)

    assert "EXPAND-007 Controlled Candidate Creation Apply-Gate Readiness" in markdown
    assert "candidate creation execution allowed" in markdown.lower()
    assert "not an apply mechanism" in markdown
    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    csv_text = Path(outputs["csv"]).read_text(encoding="utf-8")
    assert "apply_execution_allowed_by_this_report" in csv_text


def test_latest_report_finders(tmp_path: Path) -> None:
    expand004_dir = tmp_path / "expand004_controlled_candidate_creation_dry_run"
    expand004_dir.mkdir()
    expand004_path = expand004_dir / "expand004_controlled_candidate_creation_dry_run.json"
    expand004_path.write_text(json.dumps(_expand004_ready()), encoding="utf-8")

    old_expand006 = tmp_path / "expand006_candidate_creation_evidence_review_20260612-100000.json"
    new_expand006 = tmp_path / "expand006_candidate_creation_evidence_review_20260612-110000.json"
    old_expand006.write_text(json.dumps(_expand006_context_only()), encoding="utf-8")
    new_expand006.write_text(json.dumps(_expand006_inspectable()), encoding="utf-8")

    assert find_latest_expand004_report(tmp_path) == expand004_path
    assert find_latest_expand006_report(tmp_path) == new_expand006


def test_runner_writes_outputs_with_explicit_inputs(tmp_path: Path) -> None:
    expand004_path = tmp_path / "expand004.json"
    expand006_path = tmp_path / "expand006.json"
    output_dir = tmp_path / "out"
    expand004_path.write_text(json.dumps(_expand004_blocked()), encoding="utf-8")
    expand006_path.write_text(json.dumps(_expand006_context_only()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_expand007_controlled_candidate_creation_apply_gate_readiness.py",
            "--expand004-input",
            str(expand004_path),
            "--expand006-input",
            str(expand006_path),
            "--export-dir",
            str(output_dir),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "overall_status=blocked_before_apply_gate_design" in result.stdout
    assert "candidate_creation_execution_allowed=False" in result.stdout
    assert (output_dir / "expand007_controlled_candidate_creation_apply_gate_readiness.json").exists()
    assert (output_dir / "expand007_candidate_apply_gate_readiness.csv").exists()
