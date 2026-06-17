from __future__ import annotations

from pathlib import Path
import subprocess

from src.search_intelligence.generic010_report_chain_refresh_runner import (
    build_dry_run_report,
    run_chain,
)


def test_dry_run_excludes_external_probe_by_default() -> None:
    report = build_dry_run_report(generated_at="2026-06-13T00:00:00+00:00")
    names = [step["name"] for step in report["steps"]]

    assert report["overall_status"] == "dry_run_only"
    assert "expand002_controlled_external_probe_trial_run" not in names
    assert report["safety_boundary"]["external_requests_allowed_by_runner"] is False
    assert report["safety_boundary"]["candidate_creation"] is False


def test_dry_run_can_include_external_probe_explicitly() -> None:
    report = build_dry_run_report(include_external_probe=True)
    names = [step["name"] for step in report["steps"]]

    assert "expand002_controlled_external_probe_trial_run" in names
    assert report["safety_boundary"]["external_requests_allowed_by_runner"] is True


def test_runner_stops_after_failure_without_keep_going(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_runner(command, cwd):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 1, stdout="bad", stderr="")

    report = run_chain(repo_root=tmp_path, runner=fake_runner, generated_at="2026-06-13T00:00:00+00:00")

    assert report["overall_status"] == "fail"
    assert report["summary"]["failure_count"] == 1
    assert report["summary"]["skipped_count"] > 0
    assert len(calls) == 1


def test_runner_keep_going_runs_all_steps_when_dependencies_are_available(tmp_path: Path) -> None:
    expand002_dir = tmp_path / "exports" / "expand002_controlled_external_probe_trial_run"
    expand002_dir.mkdir(parents=True)
    (expand002_dir / "expand002_controlled_external_probe_trial_run.json").write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_runner(command, cwd):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = run_chain(repo_root=tmp_path, runner=fake_runner, keep_going=True)

    assert report["overall_status"] == "pass"
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["dependency_block_count"] == 0
    assert len(calls) == report["summary"]["step_count"]

def test_runner_blocks_expand003_when_external_probe_is_excluded_and_input_missing(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_runner(command, cwd):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = run_chain(
        repo_root=tmp_path,
        runner=fake_runner,
        generated_at="2026-06-17T00:00:00+00:00",
    )

    assert report["overall_status"] == "blocked_missing_dependency"
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["dependency_block_count"] == 1
    assert report["summary"]["skipped_count"] > 0
    assert len(calls) == 4

    expand003_step = next(step for step in report["steps"] if step["name"] == "expand003_candidate_review_delta_report")
    assert expand003_step["skipped"] is True
    assert expand003_step["skip_reason"] == "missing_dependency"
    assert expand003_step["dependency_issue"]["required_report"] == "expand002_controlled_external_probe_trial_run"
    assert "do not auto-enable external requests" in expand003_step["dependency_issue"]["safe_next_action"]


def test_runner_uses_existing_expand002_report_without_auto_enabling_external_probe(tmp_path: Path) -> None:
    expand002_dir = tmp_path / "exports" / "expand002_controlled_external_probe_trial_run"
    expand002_dir.mkdir(parents=True)
    (expand002_dir / "expand002_controlled_external_probe_trial_run.json").write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_runner(command, cwd):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    report = run_chain(repo_root=tmp_path, runner=fake_runner)

    assert report["overall_status"] == "pass"
    assert report["summary"]["dependency_block_count"] == 0
    assert report["summary"]["include_external_probe"] is False
    assert len(calls) == report["summary"]["step_count"]

