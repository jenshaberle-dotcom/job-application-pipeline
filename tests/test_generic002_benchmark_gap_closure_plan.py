from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.generic002_benchmark_gap_closure_plan import (
    build_benchmark_gap_closure_plan,
    find_latest_generic001_report,
    load_generic001_report,
    render_markdown,
    write_outputs,
)


def _candidate(
    *,
    company_key: str,
    company_name: str,
    review_action: str,
    evidence_strength: str,
    identity_risk: str = "normal_identity_risk",
    dimensions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "company_key": company_key,
        "company_name": company_name,
        "review_action": review_action,
        "evidence_strength": evidence_strength,
        "identity_risk": identity_risk,
        "generics_dimensions": dimensions or [],
    }


def _generic001_report(gap_ids: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "generic001.pipeline_generics_proof_gate.v1",
        "overall_status": "not_passed_needs_benchmark_gap_closure" if gap_ids else "passed_review_artifact_only",
        "summary": {"candidate_count": 3},
        "gap_ids": gap_ids or [],
        "candidate_decision_table": [
            _candidate(
                company_key="adesso_business_consulting",
                company_name="adesso business consulting AG",
                review_action="ready_for_human_evidence_review",
                evidence_strength="strong_detail",
                dimensions=["strong_evidence_candidate"],
            ),
            _candidate(
                company_key="clean_stop_control",
                company_name="Clean Stop Control GmbH",
                review_action="no_useful_external_hint_no_candidate_creation",
                evidence_strength="none",
                dimensions=["no_actionable_evidence_candidate"],
            ),
            _candidate(
                company_key="weak_only_company",
                company_name="Weak Only GmbH",
                review_action="weak_external_hint_no_candidate_creation",
                evidence_strength="weak_market_signal",
                dimensions=["weak_only_candidate"],
            ),
        ],
    }


def test_closure_plan_builds_rerun_command_when_controls_exist() -> None:
    report = build_benchmark_gap_closure_plan(
        _generic001_report(["positive_control_coverage", "negative_control_coverage"]),
        input_path="generic001.json",
        generated_at="2026-06-12T18:40:00+00:00",
    )

    assert report["schema_version"] == "generic002.benchmark_gap_closure_plan.v1"
    assert report["overall_status"] == "ready_to_rerun_generic001_with_explicit_controls"
    assert report["summary"]["ready_to_close_gap_count"] == 2
    assert report["mutation_counts"]["database_writes"] == 0
    assert "--positive-control-key adesso_business_consulting" in report["rerun_command"]
    assert "--negative-control-key clean_stop_control" in report["rerun_command"]


def test_closure_plan_blocks_when_no_clean_stop_case_exists() -> None:
    source = _generic001_report(["no_actionable_evidence_coverage", "negative_control_coverage"])
    source["candidate_decision_table"] = [source["candidate_decision_table"][0], source["candidate_decision_table"][2]]

    report = build_benchmark_gap_closure_plan(source)

    assert report["overall_status"] == "not_ready_missing_benchmark_evidence"
    assert report["summary"]["blocked_gaps"] == ["no_actionable_evidence_coverage", "negative_control_coverage"]
    assert report["rerun_command"] is None
    assert "Do not proceed to EXPAND-004" in report["next_action"]


def test_closure_plan_is_noop_when_generic001_passed() -> None:
    report = build_benchmark_gap_closure_plan(_generic001_report([]))

    assert report["overall_status"] == "no_gaps_detected_ready_for_expand004_dry_run_review"
    assert report["summary"]["gap_count"] == 0
    assert "EXPAND-004 dry-run" in report["next_action"]


def test_outputs_are_review_artifacts_only(tmp_path: Path) -> None:
    report = build_benchmark_gap_closure_plan(_generic001_report(["positive_control_coverage"]))
    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
    markdown = render_markdown(report)
    assert "GENERIC-002 Benchmark Gap Closure Plan" in markdown
    assert "database_writes" in markdown


def test_load_generic001_report_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"schema_version": "wrong.v1"}), encoding="utf-8")

    try:
        load_generic001_report(path)
    except ValueError as exc:
        assert "Unexpected GENERIC-001 schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError")


def test_find_latest_generic001_report_prefers_timestamped_export(tmp_path: Path) -> None:
    old_dir = tmp_path / "generic001_pipeline_generics_proof_gate_20260612-100000"
    new_dir = tmp_path / "generic001_pipeline_generics_proof_gate_20260612-110000"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "generic001_pipeline_generics_proof_gate.json"
    new_path = new_dir / "generic001_pipeline_generics_proof_gate.json"
    old_path.write_text(json.dumps(_generic001_report([])), encoding="utf-8")
    new_path.write_text(json.dumps(_generic001_report([])), encoding="utf-8")

    assert find_latest_generic001_report(tmp_path) == new_path


def test_runner_creates_closure_plan_from_explicit_input(tmp_path: Path) -> None:
    input_path = tmp_path / "generic001.json"
    export_dir = tmp_path / "out"
    input_path.write_text(json.dumps(_generic001_report(["positive_control_coverage"])), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_generic002_benchmark_gap_closure_plan.py",
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
    assert "overall_status=ready_to_rerun_generic001_with_explicit_controls" in result.stdout
    assert "ready_to_close_gap_count=1" in result.stdout
    assert (export_dir / "generic002_benchmark_gap_closure_plan.json").exists()
