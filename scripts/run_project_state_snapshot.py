#!/usr/bin/env python3
"""STATE-001A minimal project state snapshot export.

The snapshot is a read-only handover aid. It intentionally does not run tests,
mutate the database, call external services or infer product decisions beyond a
small next-safe-action recommendation from repository state and documentation
architecture checks.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_documentation_architecture import build_documentation_architecture_report

SNAPSHOT_SCHEMA_VERSION = "state001a.project_state_snapshot.v1"
TOOLING_GOV_SEQUENCE = [
    "STATE-001 Project State Snapshot Contract",
    "INSPECT-001 Repo/DB/Docs Inspection Bundle",
    "HANDOVER-001 Standard Chat Handover Contract",
    "RULES-001 Project Rules Index",
    "VALIDATE-001 Unified Validation Command",
    "NEXT-001 Next Safe Action Report",
    "MCP-001 Project State Server, read-only-first",
]

HORIZONTAL_FREEZE_PATH_MODE_ID = "FREEZE-001A"
HORIZONTAL_FREEZE_PATH_ALLOWED_SCOPE = [
    "governance documentation",
    "validation tooling",
    "inspection tooling",
    "handover tooling",
    "read-only state and next-safe-action reporting",
]
HORIZONTAL_FREEZE_PATH_EXCLUDED_SCOPE = [
    "product pipeline decisions",
    "database mutation",
    "external source execution",
    "scheduler semantics",
    "candidate, gate, connector, Bronze, Silver, or Gold behavior",
]


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "ok": self.ok,
            "stdout": self.stdout,
            "stderr": self.stderr,
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


def _changed_files(status_lines: Iterable[str]) -> list[str]:
    files: list[str] = []
    for line in status_lines:
        if len(line) < 4:
            continue
        # git status --short uses two status columns plus a space. For renames,
        # keep the target side because that is what future commands usually need.
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return sorted(files)


def build_git_state(root: Path) -> dict[str, object]:
    branch = _run_command(root, ["git", "branch", "--show-current"])
    head = _run_command(root, ["git", "log", "-1", "--oneline", "--decorate"])
    status = _run_command(root, ["git", "status", "--short"])
    recent_log = _run_command(root, ["git", "log", "--oneline", "-5"])
    remote_status = _run_command(root, ["git", "status", "--branch", "--short"])

    status_lines = _lines(status.stdout) if status.ok else []
    return {
        "available": branch.ok and head.ok and status.ok,
        "branch": branch.stdout if branch.ok else None,
        "head": head.stdout if head.ok else None,
        "is_dirty": bool(status_lines),
        "status_short": status_lines,
        "changed_files": _changed_files(status_lines),
        "recent_log": _lines(recent_log.stdout) if recent_log.ok else [],
        "remote_status": _lines(remote_status.stdout) if remote_status.ok else [],
        "command_errors": [
            result.to_dict()
            for result in [branch, head, status, recent_log, remote_status]
            if not result.ok
        ],
    }


def build_documentation_state(root: Path) -> dict[str, object]:
    report = build_documentation_architecture_report(root)
    return {
        "architecture_status": report.status,
        "issue_count": report.issue_count,
        "unexpected_top_level_dirs": report.unexpected_top_level_dirs,
        "unexpected_top_level_files": report.unexpected_top_level_files,
        "forbidden_top_level_dirs_present": report.forbidden_top_level_dirs_present,
        "missing_required_files": report.missing_required_files,
    }


def build_validation_state() -> dict[str, object]:
    return {
        "latest_validation_known_to_snapshot": "not_run_by_snapshot",
        "reason": "STATE-001A is read-only and does not execute the full validation suite.",
        "required_before_commit_or_pr": [
            "python scripts/run_validate001_unified_validation.py --profile commit",
            "python -m py_compile <changed scripts/tests>",
            "python -m pytest -q <targeted tests>",
            "python -m pytest -q",
            "git diff --check",
            "git status --short",
        ],
    }


def choose_next_safe_action(git_state: dict[str, object], documentation_state: dict[str, object]) -> dict[str, object]:
    if documentation_state["architecture_status"] != "pass":
        return {
            "action": "fix_documentation_architecture_before_patch",
            "reason": "The documentation architecture guard is failing.",
            "requires_user_decision": False,
        }

    if git_state.get("is_dirty"):
        return {
            "action": "validate_current_worktree_before_commit_or_continue",
            "reason": "The working tree has uncommitted changes.",
            "requires_user_decision": False,
        }

    if git_state.get("branch") == "main":
        return {
            "action": "select_next_work_item_then_create_feature_branch",
            "reason": "Main is clean; the next change should start from an explicit work item branch.",
            "requires_user_decision": True,
        }

    return {
        "action": "inspect_branch_intent_before_patch",
        "reason": "A non-main branch is clean; confirm it is the intended branch before applying new work.",
        "requires_user_decision": False,
    }



def build_horizontal_freeze_path_bundle_mode(
    git_state: dict[str, object],
    documentation_state: dict[str, object],
) -> dict[str, object]:
    blocked_reasons: list[str] = []

    if documentation_state["architecture_status"] != "pass":
        blocked_reasons.append("documentation_architecture_not_pass")
    if git_state.get("is_dirty"):
        blocked_reasons.append("worktree_dirty")

    return {
        "mode_id": HORIZONTAL_FREEZE_PATH_MODE_ID,
        "available": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "purpose": "Bundle independent horizontal governance, validation, inspection, handover and read-only stabilization changes without mixing in vertical product pipeline behavior.",
        "allowed_scope": HORIZONTAL_FREEZE_PATH_ALLOWED_SCOPE,
        "excluded_scope": HORIZONTAL_FREEZE_PATH_EXCLUDED_SCOPE,
        "requires_before_patch": [
            "short system-impact analysis",
            "clean branch intent",
            "no hidden runtime dependency between bundled parts",
            "targeted tests for each touched surface",
            "shared fan-in validation before commit or PR",
        ],
    }

def build_project_state_snapshot(root: Path, generated_at: datetime | None = None) -> dict[str, object]:
    generated_at = generated_at or datetime.now(tz=UTC)
    git_state = build_git_state(root)
    documentation_state = build_documentation_state(root)
    next_safe_action = choose_next_safe_action(git_state, documentation_state)

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at_utc": generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "snapshot_scope": "minimal_repo_docs_validation_state",
        "read_only": True,
        "external_requests": False,
        "database_reads": False,
        "database_writes": False,
        "tooling_governance_sequence": TOOLING_GOV_SEQUENCE,
        "horizontal_freeze_path_bundle_mode": build_horizontal_freeze_path_bundle_mode(
            git_state,
            documentation_state,
        ),
        "git": git_state,
        "documentation": documentation_state,
        "validation": build_validation_state(),
        "next_safe_action": next_safe_action,
        "handover_contract_hint": {
            "human_summary_should_include": [
                "validated state",
                "last completed work items",
                "freeze path position",
                "pipeline capability scorecard",
                "open blockers and user decisions",
                "next safe action",
                "required files or exports",
                "rules delta since last handover",
            ]
        },
    }


def render_markdown(snapshot: dict[str, object]) -> str:
    git_state = snapshot["git"]
    documentation_state = snapshot["documentation"]
    validation_state = snapshot["validation"]
    next_safe_action = snapshot["next_safe_action"]
    bundle_mode = snapshot.get("horizontal_freeze_path_bundle_mode") or {}

    changed_files = git_state.get("changed_files") or []
    recent_log = git_state.get("recent_log") or []
    required_validation = validation_state.get("required_before_commit_or_pr") or []

    lines = [
        "# Project State Snapshot",
        "",
        f"Generated: {snapshot['generated_at_utc']}",
        f"Schema: `{snapshot['schema_version']}`",
        "",
        "## Safety boundary",
        "",
        f"- Read-only: `{snapshot['read_only']}`",
        f"- External requests: `{snapshot['external_requests']}`",
        f"- Database reads: `{snapshot['database_reads']}`",
        f"- Database writes: `{snapshot['database_writes']}`",
        "",
        "## Horizontal Freeze-Path Bundle Mode",
        "",
        f"- Mode ID: `{bundle_mode.get('mode_id')}`",
        f"- Available: `{bundle_mode.get('available')}`",
        f"- Blocked reasons: `{', '.join(bundle_mode.get('blocked_reasons') or []) or 'none'}`",
        "",
        "### Allowed scope",
        "",
        *[f"- {item}" for item in bundle_mode.get("allowed_scope") or []],
        "",
        "### Excluded scope",
        "",
        *[f"- {item}" for item in bundle_mode.get("excluded_scope") or []],
        "",
        "## Git state",
        "",
        f"- Branch: `{git_state.get('branch')}`",
        f"- Head: `{git_state.get('head')}`",
        f"- Dirty: `{git_state.get('is_dirty')}`",
        "",
        "### Changed files",
        "",
    ]
    if changed_files:
        lines.extend(f"- `{path}`" for path in changed_files)
    else:
        lines.append("- none")

    lines.extend(["", "### Recent log", ""])
    if recent_log:
        lines.extend(f"- `{entry}`" for entry in recent_log)
    else:
        lines.append("- unavailable")

    lines.extend(
        [
            "",
            "## Documentation architecture",
            "",
            f"- Status: `{documentation_state['architecture_status']}`",
            f"- Issue count: `{documentation_state['issue_count']}`",
            "",
            "## Validation contract",
            "",
            f"- Latest validation known to snapshot: `{validation_state['latest_validation_known_to_snapshot']}`",
            f"- Reason: {validation_state['reason']}",
            "",
            "Required before commit or PR:",
            "",
        ]
    )
    lines.extend(f"- `{command}`" for command in required_validation)

    lines.extend(
        [
            "",
            "## Next safe action",
            "",
            f"- Action: `{next_safe_action['action']}`",
            f"- Reason: {next_safe_action['reason']}",
            f"- Requires user decision: `{next_safe_action['requires_user_decision']}`",
            "",
            "## TOOLING/GOV sequence",
            "",
        ]
    )
    lines.extend(f"{index}. {item}" for index, item in enumerate(snapshot["tooling_governance_sequence"], start=1))
    lines.append("")
    return "\n".join(lines)


def write_snapshot_reports(snapshot: dict[str, object], output_dir: Path, label: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in label).strip("_")
    if not safe_label:
        safe_label = "project_state_snapshot"
    json_path = output_dir / f"{safe_label}.json"
    markdown_path = output_dir / f"{safe_label}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(snapshot), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a minimal read-only project state snapshot.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--output-dir", default="exports", help="Output directory for JSON/Markdown reports.")
    parser.add_argument("--label", default=None, help="Report file label. Defaults to state001a_project_state_snapshot_<timestamp>.")
    parser.add_argument("--json", action="store_true", help="Print snapshot JSON to stdout.")
    parser.add_argument("--write-report", action="store_true", help="Write JSON and Markdown reports to output-dir.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    generated_at = datetime.now(tz=UTC)
    snapshot = build_project_state_snapshot(root, generated_at=generated_at)

    if args.json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))

    if args.write_report:
        default_label = "state001a_project_state_snapshot_" + generated_at.strftime("%Y%m%d_%H%M%S")
        json_path, markdown_path = write_snapshot_reports(
            snapshot=snapshot,
            output_dir=(root / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir),
            label=args.label or default_label,
        )
        print(f"state_json_report_written: {json_path}")
        print(f"state_markdown_report_written: {markdown_path}")

    if not args.json and not args.write_report:
        print(render_markdown(snapshot))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
