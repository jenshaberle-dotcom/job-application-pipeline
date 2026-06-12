from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.generic_pipeline_proof_gate import (
    build_candidate_generics_items,
    build_generic_pipeline_proof_report,
    find_latest_expand003_report,
    load_expand003_report,
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
            _review_item(
                company_key="clean_stop_control",
                company_name="Clean Stop Control GmbH",
                review_action="no_useful_external_hint_no_candidate_creation",
                evidence_strength="none",
            ),
        ],
    }


def test_build_candidate_items_identifies_dimensions_and_boundaries() -> None:
    items = build_candidate_generics_items(
        _expand003_report()["candidate_review_items"],
        positive_control_keys=["adesso_business_consulting"],
        negative_control_keys=["clean_stop_control"],
    )
    by_key = {item.company_key: item for item in items}

    assert "strong_evidence_candidate" in by_key["adesso_business_consulting"].generics_dimensions
    assert "positive_control_candidate" in by_key["adesso_business_consulting"].generics_dimensions
    assert "provider_backed_origin" in by_key["arnold_jager"].generics_dimensions
    assert "clear_career_origin" in by_key["cancom"].generics_dimensions
    assert "ambiguous_identity_candidate" in by_key["bge"].generics_dimensions
    assert "weak_only_candidate" in by_key["apo_data_service"].generics_dimensions
    assert "negative_control_candidate" in by_key["clean_stop_control"].generics_dimensions
    assert "automatic_candidate_creation" in by_key["cancom"].blocked_next_steps


def test_generic_proof_gate_passes_when_all_benchmark_dimensions_are_present() -> None:
    report = build_generic_pipeline_proof_report(
        _expand003_report(),
        expand003_path="expand003.json",
        positive_control_keys=["adesso_business_consulting"],
        negative_control_keys=["clean_stop_control"],
        generated_at="2026-06-12T18:31:23+00:00",
    )

    assert report["schema_version"] == "generic001.pipeline_generics_proof_gate.v1"
    assert report["overall_status"] == "passed_review_artifact_only"
    assert report["summary"]["candidate_count"] == 10
    assert report["summary"]["failed_check_count"] == 0
    assert report["mutation_counts"]["database_writes"] == 0
    assert report["safety_boundary"]["external_requests"] is False


def test_generic_proof_gate_keeps_current_artifact_gaps_explicit() -> None:
    report = build_generic_pipeline_proof_report(_expand003_report(), expand003_path="expand003.json")

    assert report["overall_status"] == "not_passed_needs_benchmark_gap_closure"
    assert "positive_control_coverage" in report["gap_ids"]
    assert "negative_control_coverage" in report["gap_ids"]
    assert report["summary"]["failed_check_count"] == 2
    assert any("explicit positive and negative control" in item for item in report["follow_up_recommendations"])


def test_outputs_are_review_artifacts_only(tmp_path: Path) -> None:
    report = build_generic_pipeline_proof_report(_expand003_report(), expand003_path="expand003.json")
    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    markdown = render_markdown(report)
    assert "GENERIC-001 Pipeline Generics Proof Gate" in markdown
    assert "Safety boundary" in markdown
    assert "automatic_candidate_creation" in markdown


def test_load_expand003_report_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"schema_version": "wrong.v1"}), encoding="utf-8")

    try:
        load_expand003_report(path)
    except ValueError as exc:
        assert "Unexpected EXPAND-003 schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError")


def test_find_latest_expand003_report_prefers_newest_timestamped_export(tmp_path: Path) -> None:
    old_dir = tmp_path / "expand003_candidate_review_delta_report_20260612-100000"
    new_dir = tmp_path / "expand003_candidate_review_delta_report_20260612-110000"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "expand003_candidate_review_delta_report.json"
    new_path = new_dir / "expand003_candidate_review_delta_report.json"
    old_path.write_text(json.dumps(_expand003_report()), encoding="utf-8")
    new_path.write_text(json.dumps(_expand003_report()), encoding="utf-8")
    old_path.touch()
    new_path.touch()

    assert find_latest_expand003_report(tmp_path) == new_path


def test_runner_creates_generic_proof_report_from_explicit_input(tmp_path: Path) -> None:
    input_path = tmp_path / "expand003.json"
    export_dir = tmp_path / "out"
    input_path.write_text(json.dumps(_expand003_report()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_generic001_pipeline_generics_proof_gate.py",
            "--input",
            str(input_path),
            "--positive-control-key",
            "adesso_business_consulting",
            "--negative-control-key",
            "clean_stop_control",
            "--export-dir",
            str(export_dir),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "overall_status=passed_review_artifact_only" in result.stdout
    assert "failed_check_count=0" in result.stdout
    assert (export_dir / "generic001_pipeline_generics_proof_gate.json").exists()
