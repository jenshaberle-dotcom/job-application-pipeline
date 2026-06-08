#!/usr/bin/env python3
"""Create the standard workflow chat handover export.

This helper is intentionally read-only with respect to project state:
- runs existing validation/reporting commands
- refuses to create a final handover if validation fails
- refuses if the git worktree is dirty
- writes JSON/Markdown/ZIP export artifacts under exports/

Usage:
    python scripts/create_standard_workflow_handover.py
"""

from __future__ import annotations

import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
EXPORTS = ROOT / "exports"
EXPORTS.mkdir(exist_ok=True)

STAMP = datetime.now().strftime("%Y%m%d-%H%M")
BASE = f"efficient_handover_standard_workflow_{STAMP}"
JSON_PATH = EXPORTS / f"{BASE}.json"
MD_PATH = EXPORTS / f"{BASE}.md"
ZIP_PATH = EXPORTS / f"{BASE}.zip"

EXPECTED_ITEMS = {
    "STATE-001A",
    "INSPECT-001A",
    "HANDOVER-001A",
    "RULES-001A",
    "VALIDATE-001A",
    "NEXT-001A",
}



MINIMAL_RESTART_PAYLOAD_SCHEMA_VERSION = "chatlevel.minimal_restart_payload.v1"

def run(command: list[str], *, required: bool = True) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if required and completed.returncode != 0:
        raise SystemExit(
            f"FAILED: {' '.join(command)}\n"
            f"exit={completed.returncode}\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}"
        )
    return result


def latest(pattern: str) -> Path | None:
    matches = sorted(EXPORTS.glob(pattern), key=lambda p: p.stat().st_mtime)
    return matches[-1] if matches else None


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def git_text(args: list[str]) -> str:
    return run(["git", *args])["stdout"]


def validate_report_is_green(validate_report: dict[str, Any]) -> None:
    if validate_report.get("overall_status") != "pass":
        raise SystemExit("Refusing handover: VALIDATE-001 commit profile is not pass.")
    if validate_report.get("required_failure_count") != 0:
        raise SystemExit("Refusing handover: VALIDATE-001 has required failures.")


def collect_git_state() -> dict[str, Any]:
    status_short = git_text(["status", "--short"])
    return {
        "branch": git_text(["branch", "--show-current"]),
        "head": git_text(["log", "-1", "--oneline", "--decorate"]),
        "dirty": bool(status_short),
        "status_short": status_short,
        "recent_log": git_text(["log", "--oneline", "-5"]).splitlines(),
    }


def build_minimal_restart_payload(
    *,
    git: dict[str, Any],
    completed_work_items: list[str],
    recommended_next: list[str],
    next_report: dict[str, Any],
    validate_report: dict[str, Any],
    rules_path: str,
) -> dict[str, Any]:
    """Build the compact machine-readable payload for the next chat.

    This payload is intentionally small and duplicates only the fields needed to
    restart safely without reading a long narrative handover first.
    """

    return {
        "schema_version": MINIMAL_RESTART_PAYLOAD_SCHEMA_VERSION,
        "required_new_chat_artifacts": [
            "handover_json",
            "handover_zip",
        ],
        "optional_new_chat_artifacts": [
            "handover_markdown",
        ],
        "exact_repo_snapshot": True,
        "repo": {
            "branch": git.get("branch"),
            "head": git.get("head"),
            "dirty": git.get("dirty"),
        },
        "completed_work_items": completed_work_items,
        "validation": {
            "profile": validate_report.get("profile"),
            "overall_status": validate_report.get("overall_status"),
            "required_failure_count": validate_report.get("required_failure_count"),
            "optional_warning_count": validate_report.get("optional_warning_count"),
        },
        "standard_workflow_completion": next_report.get("standard_workflow_completion", {}),
        "horizontal_freeze_path_bundle_mode": next_report.get("horizontal_freeze_path_bundle_mode", {}),
        "next_safe_action": next_report.get("next_safe_action"),
        "recommended_next": recommended_next,
        "rules_pointer": rules_path,
        "safety_boundary": {
            "read_repo_state_first": True,
            "requires_system_impact_analysis_before_patch": True,
            "requires_explicit_approval_before_external_or_product_action": True,
            "no_database_writes": True,
            "no_scheduler_activation": True,
            "no_candidate_gate_connector_or_bronze_silver_gold_mutation": True,
        },
    }


def build_handover(next_report: dict[str, Any], validate_report: dict[str, Any]) -> dict[str, Any]:
    tooling_items = next_report.get("tooling_governance_status", [])
    completed_work_items = [
        item["item_id"]
        for item in tooling_items
        if item.get("required_for_standard_workflow") is True
        and item.get("status") == "present_in_head"
    ]

    missing = sorted(EXPECTED_ITEMS - set(completed_work_items))
    if missing:
        raise SystemExit(f"Refusing handover: missing completed workflow items: {missing}")

    git = collect_git_state()
    if git["dirty"]:
        raise SystemExit("Refusing handover: git worktree is dirty.")

    validate_report_is_green(validate_report)

    rules_report = read_json(latest("rules001_index_validation_*.json"))
    inspect_report = read_json(latest("inspect001_repo_db_docs_bundle_*.json"))
    handover_contract_report = read_json(latest("handover001_contract_validation_*.json"))

    rules_path = rules_report.get(
        "rules_path",
        "docs/reference/governance/workflow/rules001_project_rules_index.md",
    )

    recommended_next = next_report.get("product_return_candidates") or [
        "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review"
    ]

    minimal_restart_payload = build_minimal_restart_payload(
        git=git,
        completed_work_items=completed_work_items,
        recommended_next=recommended_next,
        next_report=next_report,
        validate_report=validate_report,
        rules_path=rules_path,
    )

    return {
        "schema_version": "chatlevel.efficient_handover_standard_workflow.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "standard_workflow_handover_generated_from_next001_validate001",
        "exact_repo_snapshot": True,
        "git": git,
        "completed_work_items": completed_work_items,
        "standard_workflow_completion": next_report.get("standard_workflow_completion", {}),
        "horizontal_freeze_path_bundle_mode": next_report.get("horizontal_freeze_path_bundle_mode", {}),
        "minimal_restart_payload": minimal_restart_payload,
        "validation": {
            "validate001_commit": {
                "path": str(latest("validate001_unified_validation_*.json").relative_to(ROOT)),
                "overall_status": validate_report.get("overall_status"),
                "required_failure_count": validate_report.get("required_failure_count"),
                "optional_warning_count": validate_report.get("optional_warning_count"),
                "profile": validate_report.get("profile"),
            },
            "next001_report": {
                "path": str(latest("next001_next_safe_action_report_*.json").relative_to(ROOT)),
                "next_safe_action": next_report.get("next_safe_action"),
                "workflow_completion": next_report.get("standard_workflow_completion", {}),
            },
            "inspect001": {
                "path": str(latest("inspect001_repo_db_docs_bundle_*.json").relative_to(ROOT)),
                "overall_status": inspect_report.get("overall_status"),
            },
            "handover001_contract": {
                "path": str(latest("handover001_contract_validation_*.json").relative_to(ROOT)),
                "status": handover_contract_report.get("status"),
            },
            "rules001_index": {
                "path": str(latest("rules001_index_validation_*.json").relative_to(ROOT)),
                "status": rules_report.get("status"),
            },
        },
        "recommended_next": recommended_next,
        "rules_pointer": {
            "active_rules_and_backlog_boundaries": rules_path,
            "workflow_reference_dir": "docs/reference/governance/workflow/",
            "mcp001_status": "backlog_only_do_not_build_unless_explicitly_promoted",
        },
        "next_chat_opening": (
            "We continue after the standard workflow foundation. "
            "STATE-001A, INSPECT-001A, HANDOVER-001A, RULES-001A, "
            "VALIDATE-001A and NEXT-001A are implemented, tested, merged and cleaned up. "
            "I uploaded the latest standard workflow handover ZIP/JSON. "
            "Please read those first. The minimal_restart_payload contains the compact restart boundary. "
            "Before any patch, provide a short system-impact analysis. "
            "Do not run external/product actions without explicit approval. "
            "The next recommended product work item is SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review."
        ),
        "safety_notes": [
            "Repo/docs are source of truth for active rules and backlog boundaries.",
            "Workflow governance reference docs live under docs/reference/governance/workflow/.",
            "Use python scripts/run_validate001_unified_validation.py --profile commit before commit/PR.",
            "Use python scripts/run_next001_next_safe_action_report.py before chat transition or next work selection.",
            "MCP-001 remains backlog-only unless explicitly promoted.",
            "Do not run external/product actions such as SENSOR-001E without explicit approval.",
        ],
    }


def write_handover_files(handover: dict[str, Any]) -> None:
    JSON_PATH.write_text(json.dumps(handover, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    completed_work_items = handover["completed_work_items"]
    workflow_completion = handover.get("standard_workflow_completion", {})
    validate_summary = handover.get("validation", {}).get("validate001_commit", {})
    recommended_next = handover["recommended_next"]
    rules_path = handover["rules_pointer"]["active_rules_and_backlog_boundaries"]
    minimal_payload = handover.get("minimal_restart_payload", {})
    freeze_mode = handover.get("horizontal_freeze_path_bundle_mode", {})
    next_safe_action = minimal_payload.get("next_safe_action") or {}
    git = handover["git"]

    markdown = f"""# Efficient Handover — Standard Workflow

Generated: `{handover["generated_at_utc"]}`

## Current repo state

- Branch: `{git["branch"]}`
- Head: `{git["head"]}`
- Dirty: `{git["dirty"]}`

## Completed standard workflow foundation

{chr(10).join(f"- {item}: completed" for item in completed_work_items)}

## Standard workflow completion

- Present in HEAD: `{workflow_completion.get("present_in_head_count")}` / `{workflow_completion.get("required_count")}`
- Percent in HEAD: `{workflow_completion.get("percent_in_head")}`

## Validation summary

- VALIDATE-001 profile: `{validate_summary.get("profile")}`
- VALIDATE-001 overall status: `{validate_summary.get("overall_status")}`
- Required failures: `{validate_summary.get("required_failure_count")}`
- Optional warnings: `{validate_summary.get("optional_warning_count")}`

## Minimal restart payload

- Schema: `{minimal_payload.get("schema_version")}`
- Required uploads: `{", ".join(minimal_payload.get('required_new_chat_artifacts') or [])}`
- Next action: `{next_safe_action.get("action")}`
- Workstream: `{next_safe_action.get("workstream")}`
- Product/external action approval required: `{minimal_payload.get("safety_boundary", {}).get("requires_explicit_approval_before_external_or_product_action")}`

## Horizontal Freeze-Path Bundle Mode

- Mode ID: `{freeze_mode.get("mode_id")}`
- Available: `{freeze_mode.get("available")}`
- Blocked reasons: `{", ".join(freeze_mode.get('blocked_reasons') or []) or "none"}`
- Boundary: read-only governance/tooling stabilization only; no product execution without explicit approval.

## Next recommended work

{chr(10).join(f"- {item}" for item in recommended_next)}

## Rules and workflow references

- Active rules/backlog boundaries: `{rules_path}`
- Workflow reference directory: `docs/reference/governance/workflow/`
- MCP-001: backlog-only unless explicitly promoted

## Next chat opening

{handover["next_chat_opening"]}
"""
    MD_PATH.write_text(markdown, encoding="utf-8")


def write_zip() -> None:
    include_paths = [
        JSON_PATH,
        MD_PATH,
        latest("next001_next_safe_action_report_*.json"),
        latest("next001_next_safe_action_report_*.md"),
        latest("validate001_unified_validation_*.json"),
        latest("validate001_unified_validation_*.md"),
        latest("inspect001_repo_db_docs_bundle_*.json"),
        latest("inspect001_repo_db_docs_bundle_*.md"),
        latest("handover001_contract_validation_*.json"),
        latest("handover001_contract_validation_*.md"),
        latest("rules001_index_validation_*.json"),
        latest("rules001_index_validation_*.md"),
        ROOT / "docs/reference/governance/workflow/rules001_project_rules_index.md",
        ROOT / "docs/reference/governance/workflow/next001_next_safe_action_report.md",
        ROOT / "docs/reference/governance/workflow/validate001_unified_validation_command.md",
        ROOT / "docs/reference/governance/workflow/handover001_standard_chat_handover_contract.md",
    ]

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        seen: set[Path] = set()
        for path in include_paths:
            if path is None:
                continue
            resolved = path.resolve()
            if not resolved.exists() or resolved in seen:
                continue
            seen.add(resolved)
            archive.write(resolved, resolved.relative_to(ROOT).as_posix())


def main() -> None:
    print("=== Preflight validation ===")
    run(["python", "scripts/run_project_state_snapshot.py"])
    run(["python", "scripts/run_inspect001_repo_db_docs_bundle.py"])
    run(["python", "scripts/run_handover001_validate_contract.py"])
    run(["python", "scripts/run_rules001_validate_index.py"])
    run(["python", "scripts/run_validate001_unified_validation.py", "--profile", "commit"])
    run(["python", "scripts/run_next001_next_safe_action_report.py"])

    next_report = read_json(latest("next001_next_safe_action_report_*.json"))
    validate_report = read_json(latest("validate001_unified_validation_*.json"))

    print("=== Create handover ===")
    handover = build_handover(next_report, validate_report)
    write_handover_files(handover)

    print("=== Refresh NEXT-001 after handover exists ===")
    run(["python", "scripts/run_next001_next_safe_action_report.py"])
    next_report = read_json(latest("next001_next_safe_action_report_*.json"))
    validate_report = read_json(latest("validate001_unified_validation_*.json"))

    handover = build_handover(next_report, validate_report)
    write_handover_files(handover)
    write_zip()

    print()
    print("# Efficient handover standard workflow")
    print(f"json={JSON_PATH}")
    print(f"markdown={MD_PATH}")
    print(f"zip={ZIP_PATH}")
    print(f"head={handover['git']['head']}")
    print(f"dirty={handover['git']['dirty']}")
    print(f"completed_work_items={','.join(handover['completed_work_items'])}")
    print(f"recommended_next={'; '.join(handover['recommended_next'])}")
    print(f"validate001_status={handover['validation']['validate001_commit']['overall_status']}")
    print(f"workflow_percent={handover['standard_workflow_completion'].get('percent_in_head')}")
    print("Windows paths:")
    print(r"\\wsl.localhost\Ubuntu" + str(JSON_PATH).replace("/", "\\"))
    print(r"\\wsl.localhost\Ubuntu" + str(ZIP_PATH).replace("/", "\\"))


if __name__ == "__main__":
    main()
