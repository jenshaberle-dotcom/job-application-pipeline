from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.market003f_expand001_controlled_manual_candidate_pipeline_trial import (
    build_missing_input_report,
    build_trial_candidate,
    build_trial_report,
    load_source_report,
    render_markdown,
    write_outputs,
)


def test_ready_review_queue_card_becomes_controlled_external_trial_candidate() -> None:
    candidate = build_trial_candidate(
        {
            "company_key": "getec",
            "company_name": "GETEC",
            "queue_lane": "needs_human_candidate_expansion_review",
            "ui_status": "review_required",
            "ui_priority_rank": 10,
            "evidence_badge": "origin_or_detail_gap",
        }
    )

    assert candidate.trial_lane == "ready_for_controlled_external_trial"
    assert candidate.trial_readiness == "ready_for_trial_plan"
    assert candidate.eligible_for_explicit_external_probe is True
    assert "origin_url_discovery_probe" in candidate.external_probe_stages
    assert candidate.candidate_creation_allowed is False
    assert candidate.gate_decision_allowed is False
    assert candidate.connector_activation_allowed is False


def test_identity_gap_is_blocked_before_external_trial() -> None:
    candidate = build_trial_candidate(
        {
            "company_key": "unknown",
            "company_name": "Unknown GmbH?",
            "queue_lane": "identity_resolution_needed",
            "ui_status": "blocked_identity_gap",
            "ui_priority_rank": 30,
            "evidence_badge": "identity_gap",
        }
    )

    assert candidate.trial_lane == "blocked_until_identity_review"
    assert candidate.trial_readiness == "blocked_identity_gap"
    assert candidate.eligible_for_explicit_external_probe is False
    assert candidate.external_probe_stages == ()
    assert "unsafe_name_equivalence_assumption" in candidate.expected_stop_conditions


def test_known_candidate_context_can_be_revalidated_without_new_candidate_creation() -> None:
    candidate = build_trial_candidate(
        {
            "company_key": "enercity",
            "company_name": "enercity",
            "queue_lane": "known_candidate_context_review",
            "ui_status": "context_review",
            "ui_priority_rank": 20,
            "evidence_badge": "context_signal",
        }
    )

    assert candidate.trial_lane == "known_candidate_context_revalidation"
    assert candidate.eligible_for_explicit_external_probe is True
    assert candidate.candidate_creation_allowed is False
    assert "do not create a new candidate automatically" in candidate.trial_note


def test_trial_report_preserves_no_mutation_contract() -> None:
    report = build_trial_report(
        {
            "schema_version": "market003e.candidate_expansion_review_ui_queue_readiness.v1",
            "cards": [
                {
                    "company_key": "getec",
                    "company_name": "GETEC",
                    "queue_lane": "needs_human_candidate_expansion_review",
                    "ui_status": "review_required",
                    "ui_priority_rank": 10,
                    "evidence_badge": "origin_or_detail_gap",
                }
            ],
        },
        generated_at="2026-06-11T21:00:00+00:00",
        input_path="input.json",
    )

    assert report["schema_version"] == "market003f.expand001_controlled_manual_candidate_pipeline_trial.v1"
    assert report["safety_boundary"]["external_requests_executed_by_this_command"] is False
    assert report["safety_boundary"]["external_requests_allowed_only_after_explicit_operator_run"] is True
    assert report["mutation_counts"] == {
        "created_candidates": 0,
        "automatic_candidate_promotions": 0,
        "written_gate_decisions": 0,
        "activated_connectors": 0,
        "scheduler_changes": 0,
        "bronze_silver_gold_writes": 0,
        "database_writes": 0,
        "external_requests_executed_by_this_command": 0,
    }
    assert report["summary"]["eligible_for_explicit_external_probe_count"] == 1
    assert report["summary"]["automatic_candidate_creation_count"] == 0
    assert report["trial_policy"]["connector_policy"] == "no_connector_activation_or_registration"


def test_missing_input_is_bounded_report_not_crash(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    report = build_missing_input_report(missing, generated_at="2026-06-11T21:00:00+00:00")

    assert report["input_status"] == "input_missing"
    assert report["summary"]["candidate_count"] == 0
    assert "Run scripts/run_market003e_candidate_expansion_review_queue_readiness.py first" in str(report["input_warning"])


def test_load_source_report_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"schema_version": "wrong.v1", "cards": []}), encoding="utf-8")

    try:
        load_source_report(path)
    except ValueError as exc:
        assert "Unexpected input schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError")


def test_outputs_are_export_only(tmp_path: Path) -> None:
    report = build_trial_report(
        {
            "schema_version": "market003e.candidate_expansion_review_ui_queue_readiness.v1",
            "cards": [
                {
                    "company_key": "medifox_dan",
                    "company_name": "MEDIFOX DAN",
                    "queue_lane": "parked_market_context",
                    "ui_status": "insufficient_evidence",
                    "ui_priority_rank": 30,
                    "evidence_badge": "weak_signal",
                }
            ],
        },
        generated_at="2026-06-11T21:00:00+00:00",
        input_path="input.json",
    )

    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    markdown = render_markdown(report)
    assert "Controlled Manual Candidate Pipeline Trial" in markdown
    assert "Created candidates: 0" in markdown
    assert "External requests executed by this command: 0" in markdown

def test_runner_script_executes_directly_from_repo_root(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_market003f_expand001_controlled_manual_candidate_pipeline_trial.py",
            "--input",
            str(tmp_path / "missing_market003e_queue.json"),
            "--export-dir",
            str(tmp_path / "trial_export"),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "input_status=input_missing" in result.stdout
    assert "candidate_creation_count=0" in result.stdout
    assert "gate_decision_count=0" in result.stdout
    assert "connector_activation_count=0" in result.stdout
    assert (tmp_path / "trial_export" / "market003f_expand001_controlled_manual_candidate_pipeline_trial_plan.json").exists()

