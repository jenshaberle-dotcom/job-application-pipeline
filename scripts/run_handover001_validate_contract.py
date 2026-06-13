#!/usr/bin/env python3
"""Validate the HANDOVER-001A Standard Chat Handover Contract.

The validator is intentionally small and read-only. It checks that the
documentation contract contains the minimum anchors needed for efficient chat
handover without becoming a broader engineering operating system.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT_PATH = Path("docs/reference/governance/workflow/handover001_standard_chat_handover_contract.md")

REQUIRED_ANCHORS = {
    "required_new_chat_artifacts": [
        "## Required new-chat artifacts",
        "State JSON",
        "Handover ZIP",
    ],
    "optional_markdown": [
        "## Optional human-readable artifact",
        "source of truth",
    ],
    "new_chat_opening": [
        "## New chat opening template",
        "3-6 sentences",
    ],
    "source_of_truth_order": [
        "## Source of truth order",
        "User-provided current terminal output",
        "Latest State JSON",
        "Latest INSPECT report",
    ],
    "zip_contents": [
        "## Required content in a handover ZIP",
        "latest State JSON",
        "latest INSPECT JSON",
    ],
    "machine_readable_expectations": [
        "## Machine-readable handover expectations",
        "schema version",
        "exact or non-exact repo-state flag",
        "recommended next work item",
    ],
    "minimal_restart_payload": [
        "## Minimal restart payload",
        "minimal_restart_payload",
        "required_new_chat_artifacts",
        "requires_explicit_approval_before_external_or_product_action",
    ],
    "freeze_path_bundle_mode": [
        "## Freeze-path bundle mode",
        "horizontal governance, validation, inspection, handover",
        "read-only",
        "stabilization",
        "must not be mixed with product execution",
    ],
    "anti_patterns": [
        "## Anti-patterns",
        "repeating the entire project history",
        "large terminal output directly into chat",
    ],
    "safety_boundary": [
        "## Safety boundary",
        "write to the database",
        "mutate pipeline data",
    ],
    "future_tooling_boundary": [
        "## Relationship to future tooling",
        "MCP-001",
        "does not implement a project state server",
    ],
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def default_output_dir(stamp: str) -> Path:
    return Path("exports") / f"handover001_contract_validation_{stamp}"


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "external_requests": False,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
    }


def read_contract(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_missing_anchors(text: str) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}

    for group_name, anchors in REQUIRED_ANCHORS.items():
        group_missing = [anchor for anchor in anchors if anchor not in text]
        if group_missing:
            missing[group_name] = group_missing

    return missing


def validate_contract(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "handover001.contract_validation.v1",
            "generated_at_utc": iso_now(),
            "contract_path": str(path),
            "status": "fail",
            "missing_anchor_groups": {
                "contract_file": [str(path)],
            },
            "safety_boundary": safety_boundary(),
        }

    text = read_contract(path)
    missing = find_missing_anchors(text)
    status = "pass" if not missing else "fail"

    return {
        "schema_version": "handover001.contract_validation.v1",
        "generated_at_utc": iso_now(),
        "contract_path": str(path),
        "status": status,
        "missing_anchor_groups": missing,
        "safety_boundary": safety_boundary(),
    }


def render_markdown_result(result: dict[str, Any]) -> str:
    lines = [
        "# HANDOVER-001A Contract Validation",
        "",
        f"Generated: `{result['generated_at_utc']}`",
        f"Contract path: `{result['contract_path']}`",
        f"Status: `{result['status']}`",
        "",
        "## Safety boundary",
        "",
    ]

    for key, value in result["safety_boundary"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Missing anchors", ""])

    missing = result["missing_anchor_groups"]
    if not missing:
        lines.append("- none")
    else:
        for group_name, anchors in missing.items():
            lines.append(f"- `{group_name}`")
            for anchor in anchors:
                lines.append(f"  - `{anchor}`")

    lines.append("")
    return "\n".join(lines)


def write_report(result: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    json_path = output_dir / f"handover001_contract_validation_{stamp}.json"
    markdown_path = output_dir / f"handover001_contract_validation_{stamp}.md"

    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_result(result), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the HANDOVER-001A Standard Chat Handover Contract."
    )
    parser.add_argument(
        "--contract-path",
        default=str(DEFAULT_CONTRACT_PATH),
        help="Path to the HANDOVER-001A contract markdown file.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for JSON/Markdown validation reports. Defaults to a run-scoped folder under exports/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    stamp = utc_timestamp()
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir(stamp)
    result = validate_contract(Path(args.contract_path))
    written = write_report(result, output_dir)

    print("# HANDOVER-001A Contract Validation")
    print(f"status={result['status']}")
    print(f"json={written['json']}")
    print(f"markdown={written['markdown']}")

    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
