from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.expand002_controlled_external_probe_trial_run import (
    ProbeQuery,
    build_missing_input_report,
    build_probe_manifest,
    build_probe_manifest_with_diagnostics,
    build_probe_queries,
    build_trial_run_report,
    classify_evidence_hint,
    load_trial_plan,
    render_markdown,
    write_outputs,
)


def _plan() -> dict[str, object]:
    return {
        "schema_version": "market003f.expand001_controlled_manual_candidate_pipeline_trial.v1",
        "trial_candidates": [
            {
                "trial_id": "expand001::getec::ready_for_controlled_external_trial",
                "company_key": "getec",
                "company_name": "GETEC",
                "trial_lane": "ready_for_controlled_external_trial",
                "trial_priority_rank": 10,
                "eligible_for_explicit_external_probe": True,
            },
            {
                "trial_id": "expand001::unknown::blocked_until_identity_review",
                "company_key": "unknown",
                "company_name": "Unknown GmbH",
                "trial_lane": "blocked_until_identity_review",
                "trial_priority_rank": 20,
                "eligible_for_explicit_external_probe": False,
            },
        ],
    }


def test_probe_manifest_uses_only_eligible_candidates_and_caps_requests() -> None:
    manifest = build_probe_manifest(
        _plan(), max_candidates=50, max_queries_per_candidate=2, max_results_per_query=5, max_total_requests=1
    )

    assert len(manifest) == 1
    assert manifest[0].company_key == "getec"
    assert "GETEC" in manifest[0].query
    assert manifest[0].max_results == 5


def test_build_probe_queries_keeps_queries_short() -> None:
    queries = build_probe_queries(
        {"company_key": "x", "company_name": "Very Long Company " * 80, "trial_id": "trial"},
        max_queries_per_candidate=2,
    )

    assert len(queries) == 2
    assert all(len(query.query) <= 390 for query in queries)


def test_dry_run_executes_no_external_requests_and_no_mutations() -> None:
    report = build_trial_run_report(_plan(), generated_at="2026-06-11T21:30:00+00:00")

    assert report["schema_version"] == "expand002.controlled_external_probe_trial_run.v1"
    assert report["summary"]["planned_probe_count"] == 2
    assert report["summary"]["external_requests_executed_count"] == 0
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
    assert all(not item["request_executed"] for item in report["probe_results"])


def test_fake_provider_executes_bounded_external_trial_without_pipeline_mutation() -> None:
    report = build_trial_run_report(
        _plan(),
        execute_external_probes=True,
        provider="fake",
        max_candidates=1,
        max_queries_per_candidate=2,
        generated_at="2026-06-11T21:30:00+00:00",
    )

    assert report["summary"]["external_requests_executed_count"] == 2
    assert report["summary"]["completed_probe_count"] == 2
    assert report["summary"]["candidate_with_external_hint_count"] == 1
    assert report["summary"]["candidate_creation_count"] == 0
    assert report["summary"]["gate_decision_count"] == 0
    assert report["summary"]["connector_activation_count"] == 0
    assert report["candidate_results"][0]["allowed_next_step"] == "human_review_evidence_only"


def test_missing_input_is_bounded_report_not_crash(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    report = build_missing_input_report(missing, generated_at="2026-06-11T21:30:00+00:00")

    assert report["input_status"] == "input_missing"
    assert report["summary"]["planned_probe_count"] == 0
    assert "Run scripts/run_market003f" in str(report["input_warning"])


def test_load_trial_plan_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"schema_version": "wrong.v1", "trial_candidates": []}), encoding="utf-8")

    try:
        load_trial_plan(path)
    except ValueError as exc:
        assert "Unexpected input schema_version" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError")


def test_outputs_are_export_only(tmp_path: Path) -> None:
    report = build_trial_run_report(_plan(), generated_at="2026-06-11T21:30:00+00:00")
    outputs = write_outputs(report, tmp_path)

    assert Path(outputs["json"]).exists()
    assert Path(outputs["csv"]).exists()
    assert Path(outputs["markdown"]).exists()
    markdown = render_markdown(report)
    assert "EXPAND-002 Controlled External Probe Trial Run" in markdown
    assert "Created candidates: 0" in markdown
    assert "Connector activations: 0" in markdown


def test_runner_executes_directly_from_repo_root_with_fake_provider(tmp_path: Path) -> None:
    input_path = tmp_path / "plan.json"
    export_dir = tmp_path / "exports"
    input_path.write_text(json.dumps(_plan()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_expand002_controlled_external_probe_trial_run.py",
            "--input",
            str(input_path),
            "--export-dir",
            str(export_dir),
            "--execute-external-probes",
            "--provider",
            "fake",
            "--max-candidates",
            "1",
            "--max-total-requests",
            "2",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "external_requests_executed_count=2" in result.stdout
    assert "candidate_creation_count=0" in result.stdout
    assert (export_dir / "expand002_controlled_external_probe_trial_run.json").exists()


def test_manifest_dedupes_duplicate_trial_candidates_before_execution() -> None:
    plan = _plan()
    plan["trial_candidates"].append(
        {
            "trial_id": "expand001::getec::ready_for_controlled_external_trial",
            "company_key": "getec",
            "company_name": "GETEC Duplicate",
            "trial_lane": "ready_for_controlled_external_trial",
            "trial_priority_rank": 11,
            "eligible_for_explicit_external_probe": True,
        }
    )

    manifest, diagnostics = build_probe_manifest_with_diagnostics(
        plan,
        max_candidates=10,
        max_queries_per_candidate=2,
        max_total_requests=20,
    )

    assert len(manifest) == 2
    assert diagnostics["duplicate_candidate_count"] == 1
    assert {query.probe_id for query in manifest} == {
        "expand002::getec::origin_url_discovery_probe::1",
        "expand002::getec::detail_page_evidence_probe::2",
    }


def test_weak_aggregator_urls_do_not_become_actionable_origin_hints() -> None:
    query = ProbeQuery(
        probe_id="p1",
        trial_id="t1",
        company_key="3xperts",
        company_name="3XPERTS GmbH",
        stage="origin_url_discovery_probe",
        query="3XPERTS GmbH careers jobs Data Engineer",
        max_results=5,
    )

    hint = classify_evidence_hint(
        query,
        [
            "https://dailyremote.com/remote-analytics-engineer-jobs-in-germany",
            "https://www.linkedin.com/jobs/data-engineer-jobs-hannover",
        ],
        ["Remote Analytics Engineer Jobs in Germany", "Data Engineer Jobs Hannover"],
    )

    assert hint == "weak_market_or_aggregator_hint_found"


def test_company_specific_career_url_is_actionable_origin_hint() -> None:
    query = ProbeQuery(
        probe_id="p1",
        trial_id="t1",
        company_key="adesso_business_consulting",
        company_name="adesso business consulting AG",
        stage="origin_url_discovery_probe",
        query="adesso business consulting careers jobs",
        max_results=5,
    )

    hint = classify_evidence_hint(query, ["https://www.adesso-bc.com/career"], ["Career | adesso business consulting"])

    assert hint == "origin_or_career_hint_found"


def test_provider_auth_failure_blocks_remaining_probes_without_more_requests() -> None:
    calls: list[str] = []

    def failing_transport(url: str, payload: object, api_key: str | None) -> object:
        calls.append(str(payload))
        raise RuntimeError("Tavily request failed with HTTP 401: Unauthorized: missing or invalid API key")

    report = build_trial_run_report(
        _plan(),
        execute_external_probes=True,
        provider="tavily",
        max_candidates=1,
        max_queries_per_candidate=2,
        transport=failing_transport,
        api_key="bad-key",
    )

    assert len(calls) == 1
    assert report["summary"]["external_requests_executed_count"] == 1
    assert report["summary"]["failed_probe_count"] == 1
    assert report["summary"]["blocked_after_provider_auth_failure_count"] == 1
    assert report["candidate_results"][0]["trial_outcome"] == "provider_auth_failed_requires_key_review"
