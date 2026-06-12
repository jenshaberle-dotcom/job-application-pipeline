from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.generic003_benchmark_control_rerun_review import (
    build_benchmark_control_rerun_review,
    find_latest_generic002_report,
    load_generic002_report,
    render_markdown,
    write_outputs,
)


def _candidate(
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


def _expand003_report(*, include_clean_stop: bool = False) -> dict[str, object]:
    items = [
        _candidate(
            company_key="adesso_business_consulting",
            company_name="adesso business consulting AG",
            review_action="ready_for_human_evidence_review",
            evidence_strength="strong_detail",
            strong_urls=["https://www.adesso.de/de/karriere/jobs/index.jsp"],
        ),
        _candidate(
            company_key="arnold_jager",
            company_name="Arnold Jäger Holding GmbH",
            review_action="ready_for_human_evidence_review",
            evidence_strength="strong_detail",
            strong_urls=["https://karriere.arnold-jaeger.de/jobs"],
        ),
        _candidate(
            company_key="amadeus_fire",
            company_name="Amadeus Fire AG",
            review_action="ready_for_detail_followup_review",
            evidence_strength="strong_origin",
            strong_urls=["https://amadeus-fire.onlyfy.jobs/jobs"],
        ),
        _candidate(
            company_key="bundesgesellschaft_fur_endlagerung_bge",
            company_name="Bundesgesellschaft für Endlagerung mbH (BGE)",
            review_action="ready_for_detail_followup_review",
            evidence_strength="strong_origin",
            strong_urls=["https://www.bge.de/de/karriere/stellenangebote/"],
        ),
        _candidate(
            company_key="cancom",
            company_name="CANCOM SE",
            review_action="ready_for_detail_followup_review",
            evidence_strength="strong_origin",
            strong_urls=["https://career.cancom.de/jobs"],
        ),
        _candidate(
            company_key="3xperts",
            company_name="3XPERTS GmbH",
            review_action="weak_external_hint_no_candidate_creation",
            evidence_strength="weak_market_signal",
            weak_urls=["https://www.stepstone.de/stellenangebote--data-engineer-3xperts--1"],
        ),
        _candidate(
            company_key="apo_data_service",
            company_name="APO Data-Service GmbH",
            review_action="weak_external_hint_no_candidate_creation",
            evidence_strength="weak_market_signal",
            weak_urls=["https://www.stepstone.de/stellenangebote--analytics-apo-data-service--2"],
        ),
        _candidate(
            company_key="avabis",
            company_name="AVABIS GmbH",
            review_action="weak_external_hint_no_candidate_creation",
            evidence_strength="weak_market_signal",
            weak_urls=["https://www.stepstone.de/stellenangebote--data-avabis--3"],
        ),
        _candidate(
            company_key="b_edgile",
            company_name="b-edgile GmbH",
            review_action="weak_external_hint_no_candidate_creation",
            evidence_strength="weak_market_signal",
            weak_urls=["https://www.stepstone.de/stellenangebote--data-b-edgile--4"],
        ),
        _candidate(
            company_key="cadwork_informatik_software",
            company_name="cadwork informatik Software GmbH",
            review_action="weak_external_hint_no_candidate_creation",
            evidence_strength="weak_market_signal",
            weak_urls=["https://www.stepstone.de/stellenangebote--data-cadwork--5"],
        ),
    ]
    if include_clean_stop:
        items[-1] = _candidate(
            company_key="clean_stop_control",
            company_name="Clean Stop Control GmbH",
            review_action="no_useful_external_hint_no_candidate_creation",
            evidence_strength="none",
        )
    return {
        "schema_version": "expand003.candidate_review_delta_report.v1",
        "generated_at_utc": "2026-06-12T18:00:00+00:00",
        "candidate_review_items": items,
    }


def _generic002_report(*, positive: bool = True, negative: bool = False) -> dict[str, object]:
    closure_steps: list[dict[str, object]] = []
    ready = "ready_to_close_with_existing_artifact"
    if positive:
        closure_steps.append(
            {
                "gap_id": "positive_control_coverage",
                "status": ready,
                "candidate_key": "adesso_business_consulting",
                "candidate_name": "adesso business consulting AG",
                "required_next_step": "rerun_generic001_with_explicit_positive_control_key",
                "rationale": "strong candidate present",
            }
        )
    else:
        closure_steps.append(
            {
                "gap_id": "positive_control_coverage",
                "status": "blocked_missing_strong_control_candidate",
                "required_next_step": "add_or_review_at_least_one_known_good_strong_evidence_candidate",
            }
        )
    if negative:
        closure_steps.append(
            {
                "gap_id": "negative_control_coverage",
                "status": ready,
                "candidate_key": "clean_stop_control",
                "candidate_name": "Clean Stop Control GmbH",
                "required_next_step": "rerun_generic001_with_explicit_negative_control_key",
                "rationale": "safe stop present",
            }
        )
    else:
        closure_steps.extend(
            [
                {
                    "gap_id": "no_actionable_evidence_coverage",
                    "status": "blocked_missing_no_actionable_evidence_case",
                    "required_next_step": "capture_one_clean_no_actionable_evidence_stop_case",
                },
                {
                    "gap_id": "negative_control_coverage",
                    "status": "blocked_missing_safe_negative_control",
                    "required_next_step": "capture_or_select_one_known_blocked_or_safe_stop_control_candidate",
                },
            ]
        )
    ready_gaps = [step["gap_id"] for step in closure_steps if step["status"] == ready]
    blocked_gaps = [step["gap_id"] for step in closure_steps if step["status"] != ready]
    return {
        "schema_version": "generic002.benchmark_gap_closure_plan.v1",
        "overall_status": "not_ready_missing_benchmark_evidence" if blocked_gaps else "ready_to_rerun_generic001_with_explicit_controls",
        "summary": {"ready_to_close_gaps": ready_gaps, "blocked_gaps": blocked_gaps},
        "closure_steps": closure_steps,
    }


def test_control_rerun_closes_positive_control_and_keeps_missing_evidence_blocked() -> None:
    report = build_benchmark_control_rerun_review(
        _generic002_report(positive=True, negative=False),
        _expand003_report(include_clean_stop=False),
        generic002_path="generic002.json",
        expand003_path="expand003.json",
        generated_at="2026-06-12T19:00:00+00:00",
    )

    assert report["schema_version"] == "generic003.benchmark_control_rerun_review.v1"
    assert report["overall_status"] == "partial_control_closure_remaining_benchmark_gaps"
    assert report["summary"]["closed_gap_ids"] == ["positive_control_coverage"]
    assert report["summary"]["still_blocked_gap_ids"] == [
        "negative_control_coverage",
        "no_actionable_evidence_coverage",
    ]
    assert report["mutation_counts"]["database_writes"] == 0
    assert "--positive-control-key adesso_business_consulting" in report["control_rerun_command"]
    assert report["remaining_benchmark_evidence_requests"][0]["boundary"].startswith("capture as review artifact only")


def test_control_rerun_can_pass_when_positive_and_negative_controls_are_available() -> None:
    report = build_benchmark_control_rerun_review(
        _generic002_report(positive=True, negative=True),
        _expand003_report(include_clean_stop=True),
    )

    assert report["overall_status"] == "passed_all_control_and_generics_checks_review_artifact_only"
    assert report["summary"]["after_gap_count"] == 0
    assert report["remaining_benchmark_evidence_requests"] == []
    assert "EXPAND-004" in report["next_action"]


def test_control_rerun_blocks_without_any_available_control_keys() -> None:
    report = build_benchmark_control_rerun_review(
        _generic002_report(positive=False, negative=False),
        _expand003_report(),
    )

    assert report["overall_status"] == "no_control_keys_available"
    assert report["control_rerun_command"] is None
    assert "capture positive/negative control metadata" in report["next_action"]


def test_outputs_include_generic001_after_rerun_artifacts(tmp_path: Path) -> None:
    report = build_benchmark_control_rerun_review(_generic002_report(), _expand003_report())
    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["markdown"]).exists()
    assert Path(outputs["generic001_after_json"]).exists()
    assert Path(outputs["generic001_after_csv"]).exists()
    assert Path(outputs["generic001_after_markdown"]).exists()
    markdown = render_markdown(report)
    assert "GENERIC-003 Benchmark Control Rerun Review" in markdown
    assert "Remaining benchmark evidence requests" in markdown


def test_load_generic002_report_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"schema_version": "wrong.v1"}), encoding="utf-8")

    try:
        load_generic002_report(path)
    except ValueError as exc:
        assert "Unexpected GENERIC-002 schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError")


def test_find_latest_generic002_report_prefers_timestamped_export(tmp_path: Path) -> None:
    old_dir = tmp_path / "generic002_benchmark_gap_closure_plan_20260612-100000"
    new_dir = tmp_path / "generic002_benchmark_gap_closure_plan_20260612-110000"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "generic002_benchmark_gap_closure_plan.json"
    new_path = new_dir / "generic002_benchmark_gap_closure_plan.json"
    old_path.write_text(json.dumps(_generic002_report()), encoding="utf-8")
    new_path.write_text(json.dumps(_generic002_report()), encoding="utf-8")

    assert find_latest_generic002_report(tmp_path) == new_path


def test_runner_creates_control_rerun_review_from_explicit_inputs(tmp_path: Path) -> None:
    generic002_path = tmp_path / "generic002.json"
    expand003_path = tmp_path / "expand003.json"
    export_dir = tmp_path / "out"
    generic002_path.write_text(json.dumps(_generic002_report()), encoding="utf-8")
    expand003_path.write_text(json.dumps(_expand003_report()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_generic003_benchmark_control_rerun_review.py",
            "--generic002-input",
            str(generic002_path),
            "--expand003-input",
            str(expand003_path),
            "--export-dir",
            str(export_dir),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "overall_status=partial_control_closure_remaining_benchmark_gaps" in result.stdout
    assert "closed_gap_count=1" in result.stdout
    assert (export_dir / "generic003_benchmark_control_rerun_review.json").exists()
