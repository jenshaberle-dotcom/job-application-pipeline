#!/usr/bin/env python3
"""VALIDATE-001A unified validation command.

This command is a compact, read-only validation entry point for the local
engineering workflow. It groups the validation checks that were previously
spread across chat instructions while keeping the console output short and
writing detailed JSON/Markdown reports under exports/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

VALIDATE001_SCHEMA_VERSION = "validate001.unified_validation.v1"

DEFAULT_OUTPUT_DIR = Path("exports")
DEFAULT_TIMEOUT_SECONDS = 300

TOOLING_SCRIPTS = [
    "scripts/run_project_state_snapshot.py",
    "scripts/run_inspect001_repo_db_docs_bundle.py",
    "scripts/run_handover001_validate_contract.py",
    "scripts/run_rules001_validate_index.py",
    "scripts/run_validate001_unified_validation.py",
]

TOOLING_TESTS = [
    "tests/test_project_state_snapshot.py",
    "tests/test_inspect001_repo_db_docs_bundle.py",
    "tests/test_handover001_contract.py",
    "tests/test_rules001_project_rules_index.py",
    "tests/test_validate001_unified_validation.py",
]


@dataclass(frozen=True)
class ValidationCommand:
    name: str
    command: list[str]
    required: bool = True
    expect_empty_stdout: bool = False
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]
    required: bool
    expect_empty_stdout: bool
    timeout_seconds: int
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        if self.timed_out:
            return False
        if self.exit_code != 0:
            return False
        if self.expect_empty_stdout and self.stdout.strip():
            return False
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "required": self.required,
            "expect_empty_stdout": self.expect_empty_stdout,
            "timeout_seconds": self.timeout_seconds,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "timed_out": self.timed_out,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "external_requests": False,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
    }


def _existing_paths(root: Path, relative_paths: Iterable[str]) -> list[str]:
    return [path for path in relative_paths if (root / path).exists()]


def build_validation_plan(profile: str, root: Path, python_executable: str = sys.executable) -> list[ValidationCommand]:
    """Build the validation command plan.

    Profiles:
    - quick: tooling compile, tooling tests, contract validators and diff checks.
    - commit: quick profile plus full pytest.
    - handover: commit profile plus state/inspect report generation.
    """

    if profile not in {"quick", "commit", "handover"}:
        raise ValueError(f"Unsupported validation profile: {profile}")

    existing_scripts = _existing_paths(root, TOOLING_SCRIPTS)
    existing_tests = _existing_paths(root, TOOLING_TESTS)

    commands: list[ValidationCommand] = [
        ValidationCommand(
            name="py_compile_tooling_scripts",
            command=[python_executable, "-m", "py_compile", *existing_scripts],
        ),
        ValidationCommand(
            name="pytest_tooling_contracts",
            command=[python_executable, "-m", "pytest", "-q", *existing_tests],
        ),
        ValidationCommand(
            name="handover001_contract",
            command=[python_executable, "scripts/run_handover001_validate_contract.py"],
        ),
        ValidationCommand(
            name="rules001_index",
            command=[python_executable, "scripts/run_rules001_validate_index.py"],
        ),
    ]

    if profile == "handover":
        commands.extend(
            [
                ValidationCommand(
                    name="state001_snapshot",
                    command=[python_executable, "scripts/run_project_state_snapshot.py", "--write-report"],
                ),
                ValidationCommand(
                    name="inspect001_repo_db_docs_no_db",
                    command=[python_executable, "scripts/run_inspect001_repo_db_docs_bundle.py"],
                ),
            ]
        )

    if profile in {"commit", "handover"}:
        commands.append(
            ValidationCommand(
                name="full_pytest",
                command=[python_executable, "-m", "pytest", "-q"],
                timeout_seconds=600,
            )
        )

    commands.extend(
        [
            ValidationCommand(
                name="git_diff_check",
                command=["git", "diff", "--check"],
                expect_empty_stdout=True,
            ),
            ValidationCommand(
                name="git_cached_diff_check",
                command=["git", "diff", "--cached", "--check"],
                expect_empty_stdout=True,
            ),
            ValidationCommand(
                name="git_status_short",
                command=["git", "status", "--short"],
                required=False,
            ),
        ]
    )

    return commands


def run_validation_command(command: ValidationCommand, cwd: Path) -> CommandResult:
    try:
        completed = subprocess.run(
            command.command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=command.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return CommandResult(
            name=command.name,
            command=command.command,
            required=command.required,
            expect_empty_stdout=command.expect_empty_stdout,
            timeout_seconds=command.timeout_seconds,
            exit_code=124,
            stdout=stdout if isinstance(stdout, str) else stdout.decode(errors="replace"),
            stderr=stderr if isinstance(stderr, str) else stderr.decode(errors="replace"),
            timed_out=True,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            name=command.name,
            command=command.command,
            required=command.required,
            expect_empty_stdout=command.expect_empty_stdout,
            timeout_seconds=command.timeout_seconds,
            exit_code=127,
            stdout="",
            stderr=str(exc),
        )

    return CommandResult(
        name=command.name,
        command=command.command,
        required=command.required,
        expect_empty_stdout=command.expect_empty_stdout,
        timeout_seconds=command.timeout_seconds,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


CommandRunner = Callable[[ValidationCommand, Path], CommandResult]


def build_validation_report(
    root: Path,
    profile: str,
    *,
    generated_at: str | None = None,
    command_runner: CommandRunner = run_validation_command,
    python_executable: str = sys.executable,
) -> dict[str, object]:
    root = root.resolve()
    plan = build_validation_plan(profile=profile, root=root, python_executable=python_executable)
    results = [command_runner(command, root) for command in plan]

    required_failures = [
        result.name
        for result in results
        if result.required and not result.passed
    ]
    optional_warnings = [
        result.name
        for result in results
        if not result.required and not result.passed
    ]

    overall_status = "pass" if not required_failures else "fail"

    return {
        "schema_version": VALIDATE001_SCHEMA_VERSION,
        "generated_at_utc": generated_at or iso_now(),
        "profile": profile,
        "repo_root": str(root),
        "overall_status": overall_status,
        "required_failure_count": len(required_failures),
        "optional_warning_count": len(optional_warnings),
        "required_failures": required_failures,
        "optional_warnings": optional_warnings,
        "safety_boundary": safety_boundary(),
        "commands": [result.to_dict() for result in results],
        "next_safe_action": choose_next_safe_action(overall_status, required_failures),
    }


def choose_next_safe_action(overall_status: str, required_failures: Sequence[str]) -> dict[str, object]:
    if overall_status == "pass":
        return {
            "action": "continue_with_commit_pr_or_next_safe_action_selection",
            "requires_user_decision": False,
            "reason": "All required validation checks passed.",
        }

    return {
        "action": "fix_required_validation_failures_before_commit_or_pr",
        "requires_user_decision": False,
        "reason": "Required validation checks failed: " + ", ".join(required_failures),
    }


def _tail_lines(value: str, limit: int = 30) -> list[str]:
    lines = value.splitlines()
    if len(lines) <= limit:
        return lines
    return ["... output truncated ...", *lines[-limit:]]


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# VALIDATE-001A Unified Validation Report",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        f"Schema: `{report['schema_version']}`",
        f"Profile: `{report['profile']}`",
        f"Overall status: `{report['overall_status']}`",
        f"Required failures: `{report['required_failure_count']}`",
        f"Optional warnings: `{report['optional_warning_count']}`",
        "",
        "## Safety boundary",
        "",
    ]

    for key, value in report["safety_boundary"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Commands", ""])

    for command in report["commands"]:
        lines.extend(
            [
                f"### {command['name']}",
                "",
                f"- Required: `{command['required']}`",
                f"- Passed: `{command['passed']}`",
                f"- Exit code: `{command['exit_code']}`",
                f"- Command: `{' '.join(command['command'])}`",
            ]
        )

        stdout = command["stdout"]
        stderr = command["stderr"]

        if stdout:
            lines.extend(["", "Stdout tail:", ""])
            lines.extend(f"    {line}" for line in _tail_lines(str(stdout)))
        if stderr:
            lines.extend(["", "Stderr tail:", ""])
            lines.extend(f"    {line}" for line in _tail_lines(str(stderr)))
        lines.append("")

    next_safe_action = report["next_safe_action"]
    lines.extend(
        [
            "## Next safe action",
            "",
            f"- Action: `{next_safe_action['action']}`",
            f"- Requires user decision: `{next_safe_action['requires_user_decision']}`",
            f"- Reason: {next_safe_action['reason']}",
            "",
        ]
    )

    return "\n".join(lines)


def write_reports(report: dict[str, object], output_dir: Path, stamp: str | None = None) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or utc_timestamp()

    json_path = output_dir / f"validate001_unified_validation_{stamp}.json"
    markdown_path = output_dir / f"validate001_unified_validation_{stamp}.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VALIDATE-001A unified validation command.")
    parser.add_argument(
        "--profile",
        choices=["quick", "commit", "handover"],
        default="commit",
        help="Validation profile. Defaults to commit.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Defaults to current working directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for JSON/Markdown validation reports. Defaults to exports/.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full validation JSON to stdout in addition to the compact summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    report = build_validation_report(root=root, profile=args.profile)
    written = write_reports(report, output_dir=output_dir)

    print("# VALIDATE-001A Unified Validation")
    print(f"profile={report['profile']}")
    print(f"overall_status={report['overall_status']}")
    print(f"required_failures={report['required_failure_count']}")
    print(f"optional_warnings={report['optional_warning_count']}")
    print(f"json={written['json']}")
    print(f"markdown={written['markdown']}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
