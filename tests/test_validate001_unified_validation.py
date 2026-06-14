from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_validate001_unified_validation import (
    CommandResult,
    ValidationCommand,
    build_validation_plan,
    build_validation_report,
    render_markdown,
    safety_boundary,
    write_reports,
)


def test_validate001_safety_boundary_is_read_only() -> None:
    boundary = safety_boundary()

    assert boundary["read_only"] is True
    assert boundary["external_requests"] is False
    assert boundary["database_writes"] is False
    assert boundary["pipeline_mutation"] is False
    assert boundary["candidate_or_gate_mutation"] is False
    assert boundary["connector_activation"] is False


def _write_active_tooling_paths(root: Path) -> None:
    for path in [
        "scripts/run_project_state_snapshot.py",
        "scripts/run_inspect001_repo_db_docs_bundle.py",
        "scripts/run_rules001_validate_index.py",
        "scripts/run_validate001_unified_validation.py",
        "tests/test_project_state_snapshot.py",
        "tests/test_inspect001_repo_db_docs_bundle.py",
        "tests/test_rules001_project_rules_index.py",
        "tests/test_validate001_unified_validation.py",
    ]:
        file_path = root / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("# placeholder\n", encoding="utf-8")


def test_validate001_profiles_keep_full_pytest_out_of_quick_profile(tmp_path: Path) -> None:
    _write_active_tooling_paths(tmp_path)

    quick_plan = build_validation_plan("quick", tmp_path, python_executable="python")
    commit_plan = build_validation_plan("commit", tmp_path, python_executable="python")

    assert "full_pytest" not in {command.name for command in quick_plan}
    assert "full_pytest" in {command.name for command in commit_plan}


def test_validate001_rejects_retired_restart_profile(tmp_path: Path) -> None:
    retired_profile = "hand" + "over"
    with pytest.raises(ValueError):
        build_validation_plan(retired_profile, tmp_path, python_executable="python")


def test_validate001_routes_active_child_contract_reports_to_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "validation_bundle"

    plan = build_validation_plan("quick", tmp_path, python_executable="python", output_dir=output_dir)

    command_names = {command.name for command in plan}
    assert "rules001_index" in command_names
    assert "retired001_contract" not in command_names
    assert ("next" + "001_report") not in command_names

    rules_command = next(command for command in plan if command.name == "rules001_index")
    assert rules_command.command[-2:] == ["--output-dir", str(output_dir)]


def test_validate001_report_passes_when_required_commands_pass(tmp_path: Path) -> None:
    def fake_runner(command: ValidationCommand, cwd: Path) -> CommandResult:
        return CommandResult(
            name=command.name,
            command=command.command,
            required=command.required,
            expect_empty_stdout=command.expect_empty_stdout,
            timeout_seconds=command.timeout_seconds,
            exit_code=0,
            stdout="",
            stderr="",
        )

    report = build_validation_report(
        root=tmp_path,
        profile="quick",
        generated_at="2026-06-08T12:00:00+00:00",
        command_runner=fake_runner,
        python_executable="python",
    )

    assert report["schema_version"] == "validate001.unified_validation.v1"
    assert report["overall_status"] == "pass"
    assert report["required_failure_count"] == 0
    assert report["next_safe_action"]["action"] == "continue_with_commit_pr_or_repo_backed_operator_decision"


def test_validate001_report_fails_on_required_command_failure(tmp_path: Path) -> None:
    def fake_runner(command: ValidationCommand, cwd: Path) -> CommandResult:
        exit_code = 1 if command.name == "rules001_index" else 0
        stderr = "missing anchors" if command.name == "rules001_index" else ""
        return CommandResult(
            name=command.name,
            command=command.command,
            required=command.required,
            expect_empty_stdout=command.expect_empty_stdout,
            timeout_seconds=command.timeout_seconds,
            exit_code=exit_code,
            stdout="",
            stderr=stderr,
        )

    report = build_validation_report(
        root=tmp_path,
        profile="quick",
        command_runner=fake_runner,
        python_executable="python",
    )

    assert report["overall_status"] == "fail"
    assert report["required_failures"] == ["rules001_index"]
    assert report["next_safe_action"]["action"] == "fix_required_validation_failures_before_commit_or_pr"


def test_validate001_optional_git_status_warning_does_not_fail_report(tmp_path: Path) -> None:
    def fake_runner(command: ValidationCommand, cwd: Path) -> CommandResult:
        stdout = " M README.md" if command.name == "git_status_short" else ""
        return CommandResult(
            name=command.name,
            command=command.command,
            required=command.required,
            expect_empty_stdout=command.expect_empty_stdout,
            timeout_seconds=command.timeout_seconds,
            exit_code=0,
            stdout=stdout,
            stderr="",
        )

    report = build_validation_report(
        root=tmp_path,
        profile="quick",
        command_runner=fake_runner,
        python_executable="python",
    )

    assert report["overall_status"] == "pass"
    assert report["optional_warning_count"] == 0
    status_command = next(command for command in report["commands"] if command["name"] == "git_status_short")
    assert status_command["stdout"] == " M README.md"


def test_validate001_expect_empty_stdout_failure_is_required_failure(tmp_path: Path) -> None:
    def fake_runner(command: ValidationCommand, cwd: Path) -> CommandResult:
        stdout = "README.md:1: trailing whitespace" if command.name == "git_diff_check" else ""
        return CommandResult(
            name=command.name,
            command=command.command,
            required=command.required,
            expect_empty_stdout=command.expect_empty_stdout,
            timeout_seconds=command.timeout_seconds,
            exit_code=0,
            stdout=stdout,
            stderr="",
        )

    report = build_validation_report(
        root=tmp_path,
        profile="quick",
        command_runner=fake_runner,
        python_executable="python",
    )

    assert report["overall_status"] == "fail"
    assert "git_diff_check" in report["required_failures"]


def test_validate001_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    report = {
        "schema_version": "validate001.unified_validation.v1",
        "generated_at_utc": "2026-06-08T12:00:00+00:00",
        "profile": "quick",
        "overall_status": "pass",
        "required_failure_count": 0,
        "optional_warning_count": 0,
        "safety_boundary": safety_boundary(),
        "commands": [
            {
                "name": "example",
                "command": ["python", "-m", "pytest", "-q"],
                "required": True,
                "passed": True,
                "exit_code": 0,
                "stdout": "1 passed",
                "stderr": "",
            }
        ],
        "next_safe_action": {
            "action": "continue_with_commit_pr_or_repo_backed_operator_decision",
            "requires_user_decision": False,
            "reason": "All required validation checks passed.",
        },
    }

    written = write_reports(report, tmp_path, stamp="20260608-120000")

    json_path = Path(written["json"])
    markdown_path = Path(written["markdown"])

    assert json_path.exists()
    assert markdown_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == "validate001.unified_validation.v1"
    assert "# VALIDATE-001A Unified Validation Report" in markdown_path.read_text(encoding="utf-8")


def test_validate001_render_markdown_contains_failure_details() -> None:
    report = {
        "schema_version": "validate001.unified_validation.v1",
        "generated_at_utc": "2026-06-08T12:00:00+00:00",
        "profile": "quick",
        "overall_status": "fail",
        "required_failure_count": 1,
        "optional_warning_count": 0,
        "safety_boundary": safety_boundary(),
        "commands": [
            {
                "name": "rules001_index",
                "command": ["python", "scripts/run_rules001_validate_index.py"],
                "required": True,
                "passed": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": "missing anchors",
            }
        ],
        "next_safe_action": {
            "action": "fix_required_validation_failures_before_commit_or_pr",
            "requires_user_decision": False,
            "reason": "Required validation checks failed: rules001_index",
        },
    }

    markdown = render_markdown(report)

    assert "Overall status: `fail`" in markdown
    assert "### rules001_index" in markdown
    assert "missing anchors" in markdown


def test_validate001_tooling_plan_excludes_retired_chat_continuation_tools(tmp_path: Path) -> None:
    _write_active_tooling_paths(tmp_path)

    plan = build_validation_plan("quick", tmp_path, python_executable="python")

    compile_command = next(command for command in plan if command.name == "py_compile_tooling_scripts")
    pytest_command = next(command for command in plan if command.name == "pytest_tooling_contracts")
    retired_marker = "hand" + "over"
    assert all(retired_marker not in value.lower() for value in compile_command.command)
    assert all(("next" + "001") not in value.lower() for value in compile_command.command)
    assert all(retired_marker not in value.lower() for value in pytest_command.command)
    assert all(("next" + "001") not in value.lower() for value in pytest_command.command)
