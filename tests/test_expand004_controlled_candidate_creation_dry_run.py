from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.expand004_controlled_candidate_creation_dry_run import (
    build_candidate_creation_dry_run_report,
    build_dry_run_items,
    find_latest_expand003_report,
    find_latest_generic005_report,
    render_markdown,
    write_outputs,
)


def _review_item(
    *,
    company_key: str,
    company_name: str,
    review_action: str,
    evidence_strength: str,
    strong_urls: list[str] | None = None,
    weak_urls: list[str] | None = None,
) -> dict[str, object]:
    return {
        "company_key": company_key,
        "company_name": company_name,
        "review_action": review_action,
        "evidence_strength": evidence_strength,
        "top_strong_urls": strong_urls or [],
        "top_weak_urls": weak_urls or [],
    }


def _expand003_report() -> dict[str, object]:
    return {
        "schema_version": "expand003.candidate_review_delta_report.v1",
        "candidate_review_items": [
            _review_item(
                company_key="adesso_business_consulting",
                company_name="adesso business consulting AG",
                review_action="ready_for_human_evidence_review",
                evidence_strength="strong_detail",
                strong_urls=["https://www.adesso.de/jobs-karriere/data-engineer"],
            ),
            _review_item(
                company_key="arnold_jager",
                company_name="Arnold Jäger Holding GmbH",
                review_action="ready_for_human_evidence_review",
                evidence_strength="strong_detail",
                strong_urls=["https://jaegergruppe.onlyfy.jobs/en/jobs/123"],
            ),
            _review_item(
                company_key="cancom",
                company_name="CANCOM SE",
                review_action="ready_for_detail_followup_review",
                evidence_strength="strong_origin",
                strong_urls=["https://career.cancom.com/jobs"],
            ),
            _review_item(
                company_key="3xperts",
                company_name="3XPERTS GmbH",
                review_action="weak_external_hint_no_candidate_creation",
                evidence_strength="weak_market_signal",
                weak_urls=["https://www.stepstone.de/jobs/data-engineer/in-hannover"],
            ),
            _review_item(
                company_key="clean_stop_control",
                company_name="Clean Stop Control GmbH",
                review_action="no_useful_external_hint_no_candidate_creation",
                evidence_strength="none",
            ),
        ],
    }


def _generic005_passed() -> dict[str, object]:
    return {
        "schema_version": "generic005.stop_control_final_rerun.v1",
        "overall_status": "passed_all_generics_checks_review_artifact_only",
        "summary": {
            "positive_control_keys": ["adesso_business_consulting"],
            "negative_control_keys": ["clean_stop_control"],
            "final_gap_ids": [],
            "generic001_final_overall_status": "passed_review_artifact_only",
        },
    }


def _generic005_blocked() -> dict[str, object]:
    return {
        "schema_version": "generic005.stop_control_final_rerun.v1",
        "overall_status": "stop_control_capture_missing_or_invalid",
        "summary": {
            "positive_control_keys": ["adesso_business_consulting"],
            "negative_control_keys": [],
            "final_gap_ids": ["no_actionable_evidence_coverage", "negative_control_coverage"],
            "generic001_final_overall_status": "not_passed_needs_benchmark_gap_closure",
        },
    }


def test_dry_run_is_ready_only_after_generic005_final_passes() -> None:
    report = build_candidate_creation_dry_run_report(
        _generic005_passed(),
        _expand003_report(),
        generated_at="2026-06-12T20:30:00+00:00",
    )

    assert report["schema_version"] == "expand004.controlled_candidate_creation_dry_run.v1"
    assert report["overall_status"] == "ready_for_operator_candidate_creation_dry_run_review"
    assert report["summary"]["generics_ready_for_candidate_creation_dry_run"] is True
    assert report["summary"]["selected_candidate_creation_dry_run_keys"] == [
        "adesso_business_consulting",
        "arnold_jager",
        "cancom",
    ]
    assert report["mutation_counts"]["database_writes"] == 0
    assert report["safety_boundary"]["candidate_creation"] is False


def test_dry_run_blocks_when_generic005_has_remaining_gaps() -> None:
    report = build_candidate_creation_dry_run_report(_generic005_blocked(), _expand003_report())

    assert report["overall_status"] == "blocked_by_generic005_final_rerun"
    assert report["summary"]["selected_candidate_creation_dry_run_count"] == 0
    assert report["summary"]["blocked_by_generics_count"] == 3
    assert "Do not create or preview candidate records yet" in report["next_action"]


def test_weak_and_negative_controls_are_never_selected_for_candidate_creation() -> None:
    items = build_dry_run_items(_expand003_report()["candidate_review_items"], generics_ready=True)
    by_key = {item.company_key: item for item in items}

    assert by_key["3xperts"].dry_run_lane == "weak_stop_only"
    assert by_key["3xperts"].selected_for_creation_dry_run is False
    assert by_key["3xperts"].candidate_creation_allowed_by_this_report is False
    assert by_key["clean_stop_control"].dry_run_lane == "negative_stop_control"
    assert by_key["clean_stop_control"].selected_for_creation_dry_run is False


def test_manifest_selection_respects_max_candidate_limit() -> None:
    report = build_candidate_creation_dry_run_report(
        _generic005_passed(),
        _expand003_report(),
        max_dry_run_candidates=2,
    )

    assert report["summary"]["selected_candidate_creation_dry_run_keys"] == [
        "adesso_business_consulting",
        "arnold_jager",
    ]
    assert report["summary"]["selected_candidate_creation_dry_run_count"] == 2


def test_markdown_and_outputs_include_manifest(tmp_path: Path) -> None:
    report = build_candidate_creation_dry_run_report(_generic005_passed(), _expand003_report())
    markdown = render_markdown(report)
    outputs = write_outputs(report, tmp_path)

    assert "EXPAND-004 Controlled Candidate Creation Dry-Run" in markdown
    assert "ready_for_operator_candidate_creation_dry_run_review" in markdown
    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    csv_text = Path(outputs["csv"]).read_text(encoding="utf-8")
    assert "candidate_creation_allowed_by_this_report" in csv_text
    assert "adesso_business_consulting" in csv_text


def test_latest_report_finders_prefer_timestamped_parent(tmp_path: Path) -> None:
    old_generic = tmp_path / "generic005_stop_control_final_rerun_20260612-100000"
    new_generic = tmp_path / "generic005_stop_control_final_rerun_20260612-110000"
    old_expand = tmp_path / "expand003_candidate_review_delta_report_20260612-100000"
    new_expand = tmp_path / "expand003_candidate_review_delta_report_20260612-110000"
    for folder in [old_generic, new_generic, old_expand, new_expand]:
        folder.mkdir()
    (old_generic / "generic005_stop_control_final_rerun.json").write_text(json.dumps(_generic005_passed()), encoding="utf-8")
    (new_generic / "generic005_stop_control_final_rerun.json").write_text(json.dumps(_generic005_passed()), encoding="utf-8")
    (old_expand / "expand003_candidate_review_delta_report.json").write_text(json.dumps(_expand003_report()), encoding="utf-8")
    (new_expand / "expand003_candidate_review_delta_report.json").write_text(json.dumps(_expand003_report()), encoding="utf-8")

    assert find_latest_generic005_report(tmp_path) == new_generic / "generic005_stop_control_final_rerun.json"
    assert find_latest_expand003_report(tmp_path) == new_expand / "expand003_candidate_review_delta_report.json"


def test_runner_writes_outputs_with_explicit_inputs(tmp_path: Path) -> None:
    generic005_path = tmp_path / "generic005.json"
    expand003_path = tmp_path / "expand003.json"
    output_dir = tmp_path / "out"
    generic005_path.write_text(json.dumps(_generic005_passed()), encoding="utf-8")
    expand003_path.write_text(json.dumps(_expand003_report()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_expand004_controlled_candidate_creation_dry_run.py",
            "--generic005-input",
            str(generic005_path),
            "--expand003-input",
            str(expand003_path),
            "--export-dir",
            str(output_dir),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "overall_status=ready_for_operator_candidate_creation_dry_run_review" in result.stdout
    assert (output_dir / "expand004_controlled_candidate_creation_dry_run.json").exists()
    assert (output_dir / "expand004_candidate_creation_dry_run_manifest.csv").exists()
