from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.expand008_freeze_path_blocker_snapshot import (
    build_freeze_path_blocker_snapshot,
    find_latest_expand007_report,
    find_latest_generic005_report,
    find_latest_generic006_report,
    render_markdown,
    write_outputs,
)


def _generic005_blocked() -> dict[str, object]:
    return {
        "schema_version": "generic005.stop_control_final_rerun.v1",
        "overall_status": "stop_control_capture_missing_or_invalid",
    }


def _generic005_passed() -> dict[str, object]:
    return {
        "schema_version": "generic005.stop_control_final_rerun.v1",
        "overall_status": "passed_all_generics_checks_review_artifact_only",
    }


def _generic006_ready() -> dict[str, object]:
    return {
        "schema_version": "generic006.stop_control_capture_repair_packet.v1",
        "overall_status": "ready_for_generic005_rerun_after_operator_review",
    }


def _expand007_blocked() -> dict[str, object]:
    return {
        "schema_version": "expand007.controlled_candidate_creation_apply_gate_readiness.v1",
        "overall_status": "blocked_before_apply_gate_design",
    }


def _expand007_ready() -> dict[str, object]:
    return {
        "schema_version": "expand007.controlled_candidate_creation_apply_gate_readiness.v1",
        "overall_status": "ready_for_manual_apply_gate_design_review_not_apply",
    }


def test_snapshot_blocks_on_generic005_first() -> None:
    report = build_freeze_path_blocker_snapshot(_generic005_blocked(), _expand007_blocked(), None)

    assert report["overall_status"] == "blocked_before_candidate_creation_apply_gate"
    assert report["summary"]["block_z_progress_numerator"] == 6.5
    assert report["summary"]["first_blocking_gate_id"] == "generic005_stop_control_final_rerun"
    assert report["summary"]["candidate_creation_apply_allowed"] is False
    assert report["mutation_counts"]["database_writes"] == 0


def test_snapshot_reaches_seven_when_review_gates_pass() -> None:
    report = build_freeze_path_blocker_snapshot(_generic005_passed(), _expand007_ready(), _generic006_ready())

    assert report["overall_status"] == "ready_for_expand004_rerun_review_only"
    assert report["summary"]["block_z_progress_numerator"] == 7.0
    assert report["summary"]["blocked_gate_count"] == 0
    assert report["summary"]["candidate_creation_apply_allowed"] is False


def test_markdown_and_outputs_include_freeze_gates(tmp_path: Path) -> None:
    report = build_freeze_path_blocker_snapshot(_generic005_blocked(), _expand007_blocked(), None)
    markdown = render_markdown(report)
    outputs = write_outputs(report, tmp_path)

    assert "EXPAND-008 Freeze-Path Blocker Snapshot" in markdown
    assert "generic005_stop_control_final_rerun" in markdown
    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()


def test_latest_report_finders(tmp_path: Path) -> None:
    generic005_dir = tmp_path / "generic005_stop_control_final_rerun"
    generic006_dir = tmp_path / "generic006_stop_control_capture_repair_packet"
    expand007_dir = tmp_path / "expand007_controlled_candidate_creation_apply_gate_readiness"
    generic005_dir.mkdir()
    generic006_dir.mkdir()
    expand007_dir.mkdir()
    generic005_path = generic005_dir / "generic005_stop_control_final_rerun.json"
    generic006_path = generic006_dir / "generic006_stop_control_capture_repair_packet.json"
    expand007_path = expand007_dir / "expand007_controlled_candidate_creation_apply_gate_readiness.json"
    generic005_path.write_text(json.dumps(_generic005_blocked()), encoding="utf-8")
    generic006_path.write_text(json.dumps(_generic006_ready()), encoding="utf-8")
    expand007_path.write_text(json.dumps(_expand007_blocked()), encoding="utf-8")

    assert find_latest_generic005_report(tmp_path) == generic005_path
    assert find_latest_generic006_report(tmp_path) == generic006_path
    assert find_latest_expand007_report(tmp_path) == expand007_path


def test_runner_writes_snapshot_with_explicit_inputs(tmp_path: Path) -> None:
    generic005_path = tmp_path / "generic005.json"
    expand007_path = tmp_path / "expand007.json"
    output_dir = tmp_path / "out"
    generic005_path.write_text(json.dumps(_generic005_blocked()), encoding="utf-8")
    expand007_path.write_text(json.dumps(_expand007_blocked()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_expand008_freeze_path_blocker_snapshot.py",
            "--generic005-input",
            str(generic005_path),
            "--expand007-input",
            str(expand007_path),
            "--export-dir",
            str(output_dir),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "overall_status=blocked_before_candidate_creation_apply_gate" in result.stdout
    assert "first_blocking_gate_id=generic005_stop_control_final_rerun" in result.stdout
    assert (output_dir / "expand008_freeze_path_blocker_snapshot.json").exists()
