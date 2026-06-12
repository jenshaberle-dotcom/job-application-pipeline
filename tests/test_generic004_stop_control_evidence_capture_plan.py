from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.generic004_stop_control_evidence_capture_plan import (
    build_stop_control_evidence_capture_plan,
    find_latest_generic003_report,
    load_generic003_report,
    render_markdown,
    write_outputs,
)


def _candidate(
    *,
    company_key: str,
    company_name: str,
    review_action: str,
    evidence_strength: str,
) -> dict[str, object]:
    return {
        "company_key": company_key,
        "company_name": company_name,
        "review_action": review_action,
        "evidence_strength": evidence_strength,
        "top_strong_urls": [],
        "top_weak_urls": [],
    }


def _expand003_report(*, include_safe_stop: bool = False) -> dict[str, object]:
    items = [
        _candidate(
            company_key="adesso_business_consulting",
            company_name="adesso business consulting AG",
            review_action="ready_for_human_evidence_review",
            evidence_strength="strong_detail",
        ),
        _candidate(
            company_key="apo_data_service",
            company_name="APO Data-Service GmbH",
            review_action="weak_external_hint_no_candidate_creation",
            evidence_strength="weak_market_signal",
        ),
        _candidate(
            company_key="b_edgile",
            company_name="b-edgile GmbH",
            review_action="weak_external_hint_no_candidate_creation",
            evidence_strength="weak_market_signal",
        ),
    ]
    if include_safe_stop:
        items.append(
            _candidate(
                company_key="clean_stop_control",
                company_name="Clean Stop Control GmbH",
                review_action="no_useful_external_hint_no_candidate_creation",
                evidence_strength="none",
            )
        )
    return {
        "schema_version": "expand003.candidate_review_delta_report.v1",
        "candidate_review_items": items,
    }


def _generic003_report(*, remaining: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "generic003.benchmark_control_rerun_review.v1",
        "overall_status": "partial_control_closure_remaining_benchmark_gaps",
        "summary": {
            "still_blocked_gap_ids": remaining
            if remaining is not None
            else ["negative_control_coverage", "no_actionable_evidence_coverage"],
            "closed_gap_ids": ["positive_control_coverage"],
        },
    }


def test_capture_plan_blocks_when_only_weak_candidates_exist_without_file_input() -> None:
    report = build_stop_control_evidence_capture_plan(
        _generic003_report(),
        _expand003_report(include_safe_stop=False),
        generic003_path="generic003.json",
        expand003_path="expand003.json",
        generated_at="2026-06-12T20:00:00+00:00",
    )

    assert report["schema_version"] == "generic004.stop_control_evidence_capture_plan.v2"
    assert report["overall_status"] == "operator_capture_required_missing_stop_control_evidence"
    assert report["summary"]["remaining_gap_ids"] == [
        "no_actionable_evidence_coverage",
        "negative_control_coverage",
    ]
    assert report["summary"]["eligible_safe_stop_candidate_count"] == 0
    assert report["summary"]["weak_only_not_eligible_candidate_count"] == 2
    assert report["summary"]["capture_template_row_count"] == 1
    assert report["safety_boundary"]["csv_or_excel_input"] is False
    assert report["safety_boundary"]["no_file_based_operator_input"] is True
    assert report["mutation_counts"]["database_writes"] == 0
    assert report["follow_up_command_if_template_filled"] is None
    assert "DB-backed or code-backed" in report["next_action"]
    requirement = report["stop_control_evidence_requirements"][0]
    assert requirement["review_action"] == "no_useful_external_hint_no_candidate_creation"


def test_capture_plan_ready_when_safe_stop_artifact_exists() -> None:
    report = build_stop_control_evidence_capture_plan(
        _generic003_report(),
        _expand003_report(include_safe_stop=True),
    )

    assert report["overall_status"] == "ready_to_close_stop_controls_with_existing_safe_stop_artifact"
    assert report["summary"]["safe_stop_candidate_keys"] == ["clean_stop_control"]
    assert report["summary"]["eligible_safe_stop_candidate_count"] == 1
    assert "--negative-control-key clean_stop_control" in report["follow_up_command_if_template_filled"]
    assessments = report["candidate_stop_assessments"]
    eligible = [row for row in assessments if row["assessment_status"] == "eligible_safe_stop_control"]
    assert eligible[0]["can_close_gap_ids"] == [
        "no_actionable_evidence_coverage",
        "negative_control_coverage",
    ]


def test_capture_plan_noops_when_no_stop_gaps_remain() -> None:
    report = build_stop_control_evidence_capture_plan(
        _generic003_report(remaining=[]),
        _expand003_report(include_safe_stop=False),
    )

    assert report["overall_status"] == "no_remaining_stop_control_gaps"
    assert report["summary"]["capture_template_row_count"] == 0
    assert "EXPAND-004" in report["next_action"]


def test_render_markdown_contains_no_csv_handoff() -> None:
    report = build_stop_control_evidence_capture_plan(_generic003_report(), _expand003_report())
    markdown = render_markdown(report)

    assert "# GENERIC-004 Stop-Control Evidence Capture Plan" in markdown
    assert "review_artifact_only" in markdown
    assert "not_eligible_weak_only_signal" in markdown
    assert "No rerun command is available" in markdown
    assert "No CSV/Excel/export template is written" in markdown


def test_write_outputs_excludes_capture_template_csv(tmp_path: Path) -> None:
    report = build_stop_control_evidence_capture_plan(_generic003_report(), _expand003_report())
    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
    assert "capture_template_csv" not in outputs
    assert not (tmp_path / "generic004_stop_control_capture_template.csv").exists()


def test_find_latest_generic003_report_prefers_timestamped_export(tmp_path: Path) -> None:
    old_dir = tmp_path / "generic003_benchmark_control_rerun_review_20260612-100000"
    new_dir = tmp_path / "generic003_benchmark_control_rerun_review_20260612-110000"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "generic003_benchmark_control_rerun_review.json"
    new_path = new_dir / "generic003_benchmark_control_rerun_review.json"
    old_path.write_text(json.dumps(_generic003_report()), encoding="utf-8")
    new_path.write_text(json.dumps(_generic003_report()), encoding="utf-8")

    assert find_latest_generic003_report(tmp_path) == new_path


def test_load_generic003_rejects_unexpected_schema(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "other.v1"}), encoding="utf-8")

    try:
        load_generic003_report(path)
    except ValueError as exc:
        assert "Unexpected GENERIC-003 schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion path
        raise AssertionError("expected ValueError")


def test_runner_writes_json_and_markdown_without_csv(tmp_path: Path) -> None:
    generic003_path = tmp_path / "generic003.json"
    expand003_path = tmp_path / "expand003.json"
    export_dir = tmp_path / "out"
    generic003_path.write_text(json.dumps(_generic003_report()), encoding="utf-8")
    expand003_path.write_text(json.dumps(_expand003_report()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_generic004_stop_control_evidence_capture_plan.py",
            "--generic003-input",
            str(generic003_path),
            "--expand003-input",
            str(expand003_path),
            "--export-dir",
            str(export_dir),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stderr
    assert "overall_status=operator_capture_required_missing_stop_control_evidence" in result.stdout
    assert "capture_template_csv" not in result.stdout
    assert (export_dir / "generic004_stop_control_evidence_capture_plan.json").exists()
    assert not (export_dir / "generic004_stop_control_capture_template.csv").exists()
