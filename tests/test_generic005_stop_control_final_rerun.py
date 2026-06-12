from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.generic005_stop_control_final_rerun import (
    augment_expand003_with_stop_controls,
    build_stop_control_final_rerun_report,
    evaluate_capture_rows,
    stop_control_rows_from_generic004_report,
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


def _expand003_without_stop_control() -> dict[str, object]:
    return {
        "schema_version": "expand003.candidate_review_delta_report.v1",
        "generated_at_utc": "2026-06-12T18:31:23+00:00",
        "candidate_review_items": [
            _review_item(
                company_key="adesso_business_consulting",
                company_name="adesso business consulting AG",
                review_action="ready_for_human_evidence_review",
                evidence_strength="strong_detail",
                strong_urls=["https://www.adesso.de/en/jobs-karriere/einstiegsmoeglichkeiten/index.jsp"],
            ),
            _review_item(
                company_key="arnold_jager",
                company_name="Arnold Jäger Holding GmbH",
                review_action="ready_for_human_evidence_review",
                evidence_strength="strong_detail",
                strong_urls=["https://jaegergruppe.onlyfy.jobs/en", "https://3coresystems.zohorecruit.com/jobs/careers/123"],
            ),
            _review_item(
                company_key="cancom",
                company_name="CANCOM SE",
                review_action="ready_for_detail_followup_review",
                evidence_strength="strong_origin",
                strong_urls=["https://career.cancom.com/jobs"],
            ),
            _review_item(
                company_key="bge",
                company_name="Bundesgesellschaft für Endlagerung mbH (BGE)",
                review_action="ready_for_detail_followup_review",
                evidence_strength="strong_origin",
                strong_urls=["https://karriere.bge.de/go/BGE-ENG/9208055"],
            ),
            _review_item(
                company_key="amadeus_fire",
                company_name="Amadeus Fire AG",
                review_action="ready_for_detail_followup_review",
                evidence_strength="strong_origin",
                strong_urls=["https://group.amadeus-fire.de/en/work-with-us"],
            ),
            _review_item(
                company_key="3xperts",
                company_name="3XPERTS GmbH",
                review_action="weak_external_hint_no_candidate_creation",
                evidence_strength="weak_market_signal",
                weak_urls=["https://www.stepstone.de/jobs/data-engineer/in-hannover"],
            ),
            _review_item(
                company_key="apo_data_service",
                company_name="APO Data-Service GmbH",
                review_action="weak_external_hint_no_candidate_creation",
                evidence_strength="weak_market_signal",
                weak_urls=["https://dailyremote.com/remote-analytics-engineer-jobs-in-germany"],
            ),
            _review_item(
                company_key="avabis",
                company_name="AVABIS GmbH",
                review_action="weak_external_hint_no_candidate_creation",
                evidence_strength="weak_market_signal",
                weak_urls=["https://www.linkedin.com/jobs/data-engineer-jobs-hannover"],
            ),
            _review_item(
                company_key="b_edgile",
                company_name="b-edgile GmbH",
                review_action="weak_external_hint_no_candidate_creation",
                evidence_strength="weak_market_signal",
                weak_urls=["https://www.arbeitnow.com/jobs/data-engineer"],
            ),
        ],
    }


def _generic003_report() -> dict[str, object]:
    return {
        "schema_version": "generic003.benchmark_control_rerun_review.v1",
        "overall_status": "partial_control_closure_remaining_benchmark_gaps",
        "summary": {
            "positive_control_keys": ["adesso_business_consulting"],
            "negative_control_keys": [],
            "closed_gap_ids": ["positive_control_coverage"],
            "still_blocked_gap_ids": ["negative_control_coverage", "no_actionable_evidence_coverage"],
        },
    }


def _generic004_report() -> dict[str, object]:
    return {
        "schema_version": "generic004.stop_control_evidence_capture_plan.v1",
        "overall_status": "operator_capture_required_missing_stop_control_evidence",
    }


def _accepted_capture_row() -> dict[str, str]:
    return {
        "control_type": "new_clean_no_actionable_negative_control",
        "required_for_gap_ids": "no_actionable_evidence_coverage;negative_control_coverage",
        "company_key": "clean_stop_control",
        "company_name": "Clean Stop Control GmbH",
        "review_action": "no_useful_external_hint_no_candidate_creation",
        "evidence_strength": "none",
        "evidence_summary": "Bounded review found no company-origin URL, no detail page, and no actionable provider evidence.",
        "reviewer": "jens",
        "review_date": "2026-06-12",
        "boundary": "review_artifact_only_no_candidate_or_gate_write",
    }


def _template_placeholder_row() -> dict[str, str]:
    row = _accepted_capture_row()
    row["company_key"] = ""
    row["company_name"] = ""
    row["evidence_summary"] = "Describe why no company-origin/detail/provider evidence was actionable after bounded review."
    row["reviewer"] = ""
    row["review_date"] = ""
    return row


def test_capture_rows_accept_only_explicit_operator_stop_evidence() -> None:
    rows = evaluate_capture_rows([_accepted_capture_row(), _template_placeholder_row()])

    assert rows[0].status == "accepted_stop_control"
    assert rows[0].company_key == "clean_stop_control"
    assert rows[1].status == "rejected_capture_row"
    assert "company_key and company_name" in rows[1].rejection_reason


def test_final_rerun_passes_when_stop_control_is_explicitly_captured() -> None:
    report = build_stop_control_final_rerun_report(
        _generic003_report(),
        _generic004_report(),
        _expand003_without_stop_control(),
        [_accepted_capture_row()],
        generated_at="2026-06-12T20:15:00+00:00",
    )

    assert report["schema_version"] == "generic005.stop_control_final_rerun.v2"
    assert report["overall_status"] == "passed_all_generics_checks_review_artifact_only"
    assert report["summary"]["accepted_stop_control_count"] == 1
    assert report["summary"]["negative_control_keys"] == ["clean_stop_control"]
    assert report["summary"]["final_gap_ids"] == []
    assert report["summary"]["generic001_final_overall_status"] == "passed_review_artifact_only"
    assert report["mutation_counts"]["database_writes"] == 0
    assert report["safety_boundary"]["candidate_creation"] is False


def test_final_rerun_blocks_when_capture_template_is_unfilled() -> None:
    report = build_stop_control_final_rerun_report(
        _generic003_report(),
        _generic004_report(),
        _expand003_without_stop_control(),
        [_template_placeholder_row()],
    )

    assert report["overall_status"] == "stop_control_capture_missing_or_invalid"
    assert report["summary"]["accepted_stop_control_count"] == 0
    assert "negative_control_coverage" in report["summary"]["final_gap_ids"]
    assert "Keep EXPAND-004" in report["next_action"]


def test_augment_expand003_appends_benchmark_only_stop_control() -> None:
    rows = evaluate_capture_rows([_accepted_capture_row()])
    accepted = [row for row in rows if row.status == "accepted_stop_control"]
    augmented = augment_expand003_with_stop_controls(_expand003_without_stop_control(), accepted)
    items = augmented["candidate_review_items"]

    assert len(items) == 10
    assert items[-1]["company_key"] == "clean_stop_control"
    assert items[-1]["benchmark_control_source"] == "generic005_operator_stop_control_evidence"
    assert augmented["generic005_benchmark_augmentation"]["boundary"] == "benchmark_review_artifact_only_no_candidate_or_gate_write"


def test_markdown_and_outputs_include_nested_generic001_final(tmp_path: Path) -> None:
    report = build_stop_control_final_rerun_report(
        _generic003_report(),
        _generic004_report(),
        _expand003_without_stop_control(),
        [_accepted_capture_row()],
    )
    markdown = render_markdown(report)
    outputs = write_outputs(report, tmp_path)

    assert "GENERIC-005 Stop-Control Evidence" in markdown
    assert "passed_all_generics_checks_review_artifact_only" in markdown
    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
    assert Path(outputs["generic001_final_json"]).exists()
    assert Path(outputs["generic001_final_csv"]).exists()


def test_stop_control_rows_are_loaded_from_generic004_report_not_csv() -> None:
    report = {"stop_control_evidence_requirements": [_accepted_capture_row()]}

    assert stop_control_rows_from_generic004_report(report)[0]["company_key"] == "clean_stop_control"


def test_runner_writes_final_rerun_artifacts(tmp_path: Path) -> None:
    generic003_path = tmp_path / "generic003.json"
    generic004_path = tmp_path / "generic004.json"
    expand003_path = tmp_path / "expand003.json"
    export_dir = tmp_path / "out"
    generic003_path.write_text(json.dumps(_generic003_report()), encoding="utf-8")
    generic004_payload = dict(_generic004_report())
    generic004_payload["stop_control_evidence_requirements"] = [_accepted_capture_row()]
    generic004_path.write_text(json.dumps(generic004_payload), encoding="utf-8")
    expand003_path.write_text(json.dumps(_expand003_without_stop_control()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_generic005_stop_control_final_rerun.py",
            "--generic003-input",
            str(generic003_path),
            "--generic004-input",
            str(generic004_path),
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
    assert "overall_status=passed_all_generics_checks_review_artifact_only" in result.stdout
    assert "generic001_final_failed_check_count=0" in result.stdout
    assert (export_dir / "generic005_stop_control_final_rerun.json").exists()
    assert (export_dir / "generic001_final_rerun" / "generic001_pipeline_generics_proof_gate.json").exists()
