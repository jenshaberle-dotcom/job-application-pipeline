#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


FREEZE001_EXIT_GATE_SCHEMA_VERSION = "freeze001.exit_gate.v1"
MINIMAL_RESTART_PAYLOAD_SCHEMA_VERSION = "chatlevel.minimal_restart_payload.v1"
EXPECTED_PRODUCT_CANDIDATE = "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review"
EXPECTED_STANDARD_WORKFLOW_ITEMS = {
    "STATE-001A",
    "INSPECT-001A",
    "HANDOVER-001A",
    "RULES-001A",
    "VALIDATE-001A",
    "NEXT-001A",
}


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def iso_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def utc_timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "external_requests": False,
        "database_reads": False,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
        "scheduler_activation": False,
        "commit_or_merge_actions": False,
    }


def _run_command(root: Path, command: list[str]) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        return CommandResult(command=command, returncode=127, stdout="", stderr=str(exc))
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


def _lines(value: str) -> list[str]:
    return [line for line in value.splitlines() if line.strip()]


def build_git_state(root: Path) -> dict[str, object]:
    branch = _run_command(root, ["git", "branch", "--show-current"])
    head = _run_command(root, ["git", "log", "-1", "--oneline", "--decorate"])
    status = _run_command(root, ["git", "status", "--short"])
    status_lines = _lines(status.stdout) if status.ok else []
    return {
        "available": branch.ok and head.ok and status.ok,
        "branch": branch.stdout if branch.ok else None,
        "head": head.stdout if head.ok else None,
        "dirty": bool(status_lines),
        "status_short": status_lines,
        "command_errors": [
            {
                "command": result.command,
                "returncode": result.returncode,
                "stderr": result.stderr,
            }
            for result in [branch, head, status]
            if not result.ok
        ],
    }


def discover_latest_json(output_dir: Path, patterns: Sequence[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(output_dir.glob(pattern))
    candidates = [path for path in candidates if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _head_hash(head: object) -> str | None:
    if not isinstance(head, str) or not head.strip():
        return None
    return head.split(" ", 1)[0]


def _check(check_id: str, passed: bool, reason: str, *, severity: str = "required") -> dict[str, object]:
    return {
        "id": check_id,
        "passed": bool(passed),
        "severity": severity,
        "reason": reason,
    }


def evaluate_exit_gate(
    *,
    git_state: dict[str, object],
    validation_report: dict[str, Any],
    next_report: dict[str, Any],
    handover: dict[str, Any],
) -> dict[str, object]:
    git_head = git_state.get("head")
    handover_git = handover.get("git") if isinstance(handover.get("git"), dict) else {}
    handover_head = handover_git.get("head") if isinstance(handover_git, dict) else None
    completed_items = {str(item) for item in handover.get("completed_work_items") or []}

    validation_ok = (
        validation_report.get("profile") == "commit"
        and validation_report.get("overall_status") == "pass"
        and validation_report.get("required_failure_count") == 0
    )

    workflow_completion = next_report.get("standard_workflow_completion") or {}
    workflow_ok = (
        workflow_completion.get("present_in_head_count") == workflow_completion.get("required_count")
        and workflow_completion.get("required_count") == len(EXPECTED_STANDARD_WORKFLOW_ITEMS)
    )

    handover_signal = next_report.get("handover_signal") or {}
    restart_readiness = next_report.get("restart_readiness") or {}
    next_safe_action = next_report.get("next_safe_action") or {}
    freeze_mode = next_report.get("horizontal_freeze_path_bundle_mode") or {}
    minimal_payload = handover.get("minimal_restart_payload") or {}
    minimal_safety = minimal_payload.get("safety_boundary") or {}

    recommended_next = [str(item) for item in handover.get("recommended_next") or []]
    minimal_recommended_next = [str(item) for item in minimal_payload.get("recommended_next") or []]

    checks = [
        _check(
            "git_main_clean",
            git_state.get("available") is True
            and git_state.get("branch") == "main"
            and git_state.get("dirty") is False,
            "Repository must be available, on main, and clean.",
        ),
        _check(
            "validation_commit_pass",
            validation_ok,
            "Latest VALIDATE-001 report must be a passing commit-profile validation.",
        ),
        _check(
            "standard_workflow_complete",
            workflow_ok and EXPECTED_STANDARD_WORKFLOW_ITEMS.issubset(completed_items),
            "Standard workflow items must be complete in HEAD and represented in the handover.",
        ),
        _check(
            "handover_fresh",
            handover_signal.get("status") == "fresh"
            and _head_hash(git_head) == _head_hash(handover_head),
            "Latest handover must be fresh and match the current repository HEAD.",
        ),
        _check(
            "minimal_restart_payload_present",
            minimal_payload.get("schema_version") == MINIMAL_RESTART_PAYLOAD_SCHEMA_VERSION,
            "Handover JSON must contain the compact minimal_restart_payload.",
        ),
        _check(
            "restart_ready_for_next_work_selection",
            restart_readiness.get("status") == "ready_for_next_work_selection",
            "NEXT-001 restart_readiness must allow explicit next work selection.",
        ),
        _check(
            "horizontal_bundle_mode_available",
            freeze_mode.get("available") is True,
            "Horizontal Freeze-Path bundle mode must be available from a clean repo state.",
        ),
        _check(
            "sensor001e_is_next_product_candidate",
            next_safe_action.get("work_item") == EXPECTED_PRODUCT_CANDIDATE
            and EXPECTED_PRODUCT_CANDIDATE in recommended_next
            and EXPECTED_PRODUCT_CANDIDATE in minimal_recommended_next,
            "The next explicit product candidate must be SENSOR-001E.",
        ),
        _check(
            "external_product_action_requires_approval",
            minimal_safety.get("requires_explicit_approval_before_external_or_product_action") is True,
            "The restart payload must preserve explicit approval before external/product actions.",
        ),
        _check(
            "no_mutation_boundary",
            minimal_safety.get("no_database_writes") is True
            and minimal_safety.get("no_scheduler_activation") is True
            and minimal_safety.get("no_candidate_gate_connector_or_bronze_silver_gold_mutation") is True,
            "The restart payload must preserve no-mutation boundaries.",
        ),
    ]

    required_failures = [
        check["id"] for check in checks
        if check["severity"] == "required" and not check["passed"]
    ]
    overall_status = "pass" if not required_failures else "fail"

    return {
        "schema_version": FREEZE001_EXIT_GATE_SCHEMA_VERSION,
        "generated_at_utc": iso_now(),
        "overall_status": overall_status,
        "required_failure_count": len(required_failures),
        "required_failures": required_failures,
        "safety_boundary": safety_boundary(),
        "git": git_state,
        "inputs": {
            "validation_profile": validation_report.get("profile"),
            "validation_status": validation_report.get("overall_status"),
            "next_action": next_safe_action.get("action"),
            "next_workstream": next_safe_action.get("workstream"),
            "next_work_item": next_safe_action.get("work_item"),
            "handover_status": handover_signal.get("status"),
            "restart_readiness": restart_readiness.get("status"),
        },
        "checks": checks,
        "next_safe_action": {
            "action": (
                "freeze_path_complete_return_to_sensor001e_after_explicit_user_approval"
                if overall_status == "pass"
                else "fix_freeze_exit_gate_failures_before_product_work"
            ),
            "workstream": "search_intelligence_product_work" if overall_status == "pass" else "tooling_governance",
            "work_item": EXPECTED_PRODUCT_CANDIDATE if overall_status == "pass" else "FREEZE-001C",
            "requires_user_decision": overall_status == "pass",
            "reason": (
                "Freeze path exit gate passed; SENSOR-001E may start only after explicit user approval."
                if overall_status == "pass"
                else "Freeze path exit gate has required failures: " + ", ".join(required_failures)
            ),
        },
    }


def build_exit_gate_report(
    root: Path,
    *,
    output_dir: Path,
    validation_json: Path | None = None,
    next_json: Path | None = None,
    handover_json: Path | None = None,
) -> dict[str, object]:
    root = root.resolve()
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    validation_path = validation_json or discover_latest_json(output_dir, ["validate001_unified_validation_*.json"])
    next_path = next_json or discover_latest_json(output_dir, ["next001_next_safe_action_report_*.json"])
    handover_path = handover_json or discover_latest_json(output_dir, ["efficient_handover_standard_workflow_*.json"])

    return evaluate_exit_gate(
        git_state=build_git_state(root),
        validation_report=read_json(validation_path),
        next_report=read_json(next_path),
        handover=read_json(handover_path),
    )


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# FREEZE-001C Exit Gate",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        f"Schema: `{report['schema_version']}`",
        f"Overall status: `{report['overall_status']}`",
        f"Required failures: `{report['required_failure_count']}`",
        "",
        "## Safety boundary",
        "",
    ]

    for key, value in report["safety_boundary"].items():
        lines.append(f"- {key}: `{value}`")

    inputs = report["inputs"]
    lines.extend(
        [
            "",
            "## Inputs",
            "",
            f"- Validation: `{inputs.get('validation_profile')}` / `{inputs.get('validation_status')}`",
            f"- Handover status: `{inputs.get('handover_status')}`",
            f"- Restart readiness: `{inputs.get('restart_readiness')}`",
            f"- Next action: `{inputs.get('next_action')}`",
            f"- Next work item: `{inputs.get('next_work_item')}`",
            "",
            "## Checks",
            "",
        ]
    )

    for check in report["checks"]:
        status = "pass" if check["passed"] else "fail"
        lines.append(f"- `{check['id']}`: `{status}` — {check['reason']}")

    next_safe_action = report["next_safe_action"]
    lines.extend(
        [
            "",
            "## Next safe action",
            "",
            f"- Action: `{next_safe_action['action']}`",
            f"- Workstream: `{next_safe_action['workstream']}`",
            f"- Work item: `{next_safe_action['work_item']}`",
            f"- Requires user decision: `{next_safe_action['requires_user_decision']}`",
            f"- Reason: {next_safe_action['reason']}",
            "",
        ]
    )
    return "\\n".join(lines)


def write_reports(report: dict[str, object], output_dir: Path, stamp: str | None = None) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or utc_timestamp()
    json_path = output_dir / f"freeze001_exit_gate_{stamp}.json"
    markdown_path = output_dir / f"freeze001_exit_gate_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FREEZE-001C exit gate.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to current working directory.")
    parser.add_argument("--output-dir", default="exports", help="Output directory. Defaults to exports/.")
    parser.add_argument("--validation-json", default=None, help="Explicit VALIDATE-001 JSON path.")
    parser.add_argument("--next-json", default=None, help="Explicit NEXT-001 JSON path.")
    parser.add_argument("--handover-json", default=None, help="Explicit standard handover JSON path.")
    parser.add_argument("--json", action="store_true", help="Print full report JSON after the compact summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    report = build_exit_gate_report(
        root,
        output_dir=output_dir,
        validation_json=Path(args.validation_json) if args.validation_json else None,
        next_json=Path(args.next_json) if args.next_json else None,
        handover_json=Path(args.handover_json) if args.handover_json else None,
    )
    written = write_reports(report, output_dir=output_dir)

    next_safe_action = report["next_safe_action"]
    print("# FREEZE-001C Exit Gate")
    print(f"overall_status={report['overall_status']}")
    print(f"required_failures={report['required_failure_count']}")
    print(f"next_action={next_safe_action['action']}")
    print(f"workstream={next_safe_action['workstream']}")
    print(f"work_item={next_safe_action['work_item']}")
    print(f"requires_user_decision={next_safe_action['requires_user_decision']}")
    print(f"json={written['json']}")
    print(f"markdown={written['markdown']}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
