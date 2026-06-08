#!/usr/bin/env python3
"""Validate the RULES-001A Project Rules Index.

The validator is intentionally small and read-only. It checks that the compact
rules index contains the active-rule anchors needed for safe handover and
implementation work.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RULES_PATH = Path("docs/reference/rules001_project_rules_index.md")

REQUIRED_ANCHORS = {
    "purpose": [
        "## Purpose",
        "active rules",
        "workflow and architecture mistakes",
    ],
    "source_of_truth_order": [
        "## Rule source-of-truth order",
        "Current repository files and tests",
        "STATE-001 project state snapshot",
        "HANDOVER-001 chat handover contract",
    ],
    "architecture_and_safety": [
        "## Architecture and safety rules",
        "system-impact check",
        "Employer-specific fixes must improve generic pipeline capability",
        "Defensive, bounded acquisition is mandatory",
    ],
    "workflow": [
        "## Workflow rules",
        "Do not commit directly on `main`",
        "Full `pytest -q` is required before commit and PR",
        "Prefer file artifacts or checked patch files over large chat Here-Docs",
    ],
    "state_and_handover": [
        "## State and handover rules",
        "State JSON plus Handover ZIP",
        "5-10 percent",
        "Current validation output outranks older summaries",
    ],
    "documentation_and_governance": [
        "## Documentation and governance rules",
        "So wenig wie möglich, so viel wie nötig",
        "ADRs should be classified",
        "lessons-learned or recurrence-guard check",
    ],
    "product_and_ui": [
        "## Product and UI rules",
        "Ocean Deep / Deep Ocean Intelligence",
        "approval-safe and auditable",
        "derived lifecycle status from true runtime health",
    ],
    "search_intelligence": [
        "## Search Intelligence rules",
        "False-negative discovery is a first-class concern",
        "feed-forward known-company suppression",
        "travel-requirement extraction",
    ],
    "backlog_boundaries": [
        "## Backlog boundary rules",
        "VALIDATE-001 Unified Validation Command",
        "NEXT-001 Next Safe Action Report",
        "MCP-001 Project State Server, read-only-first",
    ],
    "backlog_file_escalation": [
        "## Backlog file escalation rule",
        "Create a dedicated planning, architecture, or ADR file only when",
        "premature documentation operating system",
    ],
    "white_whale": [
        "## White-Whale rule",
        "White-Whale Backlog",
        "Nicht jeder Wal muss heute gefangen werden",
    ],
    "safety_boundary": [
        "## Safety boundary",
        "write to the database",
        "mutate pipeline data",
    ],
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "external_requests": False,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
    }


def read_rules(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_missing_anchors(text: str) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}

    for group_name, anchors in REQUIRED_ANCHORS.items():
        group_missing = [anchor for anchor in anchors if anchor not in text]
        if group_missing:
            missing[group_name] = group_missing

    return missing


def validate_rules_index(path: Path = DEFAULT_RULES_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "rules001.index_validation.v1",
            "generated_at_utc": iso_now(),
            "rules_path": str(path),
            "status": "fail",
            "missing_anchor_groups": {
                "rules_file": [str(path)],
            },
            "safety_boundary": safety_boundary(),
        }

    text = read_rules(path)
    missing = find_missing_anchors(text)
    status = "pass" if not missing else "fail"

    return {
        "schema_version": "rules001.index_validation.v1",
        "generated_at_utc": iso_now(),
        "rules_path": str(path),
        "status": status,
        "missing_anchor_groups": missing,
        "safety_boundary": safety_boundary(),
    }


def render_markdown_result(result: dict[str, Any]) -> str:
    lines = [
        "# RULES-001A Index Validation",
        "",
        f"Generated: `{result['generated_at_utc']}`",
        f"Rules path: `{result['rules_path']}`",
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

    json_path = output_dir / f"rules001_index_validation_{stamp}.json"
    markdown_path = output_dir / f"rules001_index_validation_{stamp}.md"

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
        description="Validate the RULES-001A Project Rules Index."
    )
    parser.add_argument(
        "--rules-path",
        default=str(DEFAULT_RULES_PATH),
        help="Path to the RULES-001A markdown file.",
    )
    parser.add_argument(
        "--output-dir",
        default="exports",
        help="Directory for JSON/Markdown validation reports.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = validate_rules_index(Path(args.rules_path))
    written = write_report(result, Path(args.output_dir))

    print("# RULES-001A Index Validation")
    print(f"status={result['status']}")
    print(f"json={written['json']}")
    print(f"markdown={written['markdown']}")

    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
