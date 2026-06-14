#!/usr/bin/env python3
"""Validate the RULES-001 Project Rules Index.

The validator is intentionally small and read-only. It checks that the compact
rules index contains active repo-truth, safety, MCP and workflow anchors.
Retired generated chat-continuation artifacts are explicitly not active rule
anchors.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RULES_PATH = Path("docs/reference/governance/workflow/rules001_project_rules_index.md")

REQUIRED_ANCHORS = {
    "purpose": [
        "## Source-of-truth order",
        "Current project truth",
        "Git working tree and committed repository files",
    ],
    "retired_artifacts": [
        "The following are not project truth",
        "retired generated chat-continuation artifacts",
        "NEXT reports",
        "retired restart ZIPs",
    ],
    "chat_continuation": [
        "## Chat continuation rule",
        "Retired chat-continuation artifacts remain abolished as a steering mechanism",
        "fresh full repository ZIP export",
        "MCP-backed repo/DB state inspection replaces full-ZIP review",
    ],
    "mcp_externalization": [
        "## MCP-001 externalization rule",
        "external Engineering Agent Control Plane project",
        "first target and integration consumer",
    ],
    "level5": [
        "## Level-5 action rule",
        "decision flight",
        "policy approval",
        "backup or rollback plan",
        "cost estimate",
    ],
    "chief_agent": [
        "## Chief Agent rule",
        "never be the root of truth, policy or recovery",
    ],
    "local_first_cost": [
        "## Local-first cost rule",
        "compact evidence packets",
        "full-repository dumps or secrets",
    ],
    "export_boundary": [
        "## Export boundary rule",
        "review_output_only_not_pipeline_input",
        "source of truth",
    ],
    "unknown_state": [
        "## Unknown-state rule",
        "unknown",
        "needs_inspection",
    ],
}


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "external_requests": False,
        "database_reads": False,
        "database_writes": False,
        "pipeline_mutation": False,
    }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_output_dir(stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Path("exports") / f"rules001_index_validation_{stamp}"


def validate_rules_index(path: Path = DEFAULT_RULES_PATH) -> dict[str, Any]:
    missing_anchor_groups: dict[str, list[str]] = {}

    if not path.exists():
        missing_anchor_groups["rules_file"] = [str(path)]
        content = ""
    else:
        content = path.read_text(encoding="utf-8")

    for group, anchors in REQUIRED_ANCHORS.items():
        missing = [anchor for anchor in anchors if anchor not in content]
        if missing:
            missing_anchor_groups[group] = missing

    status = "pass" if not missing_anchor_groups else "fail"
    return {
        "schema_version": "rules001.index_validation.v1",
        "generated_at_utc": iso_now(),
        "rules_path": str(path),
        "status": status,
        "missing_anchor_groups": missing_anchor_groups,
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
        "## Missing anchors",
        "",
    ]
    if not result["missing_anchor_groups"]:
        lines.append("None.")
    else:
        for group, anchors in result["missing_anchor_groups"].items():
            lines.append(f"### `{group}`")
            lines.extend(f"- `{anchor}`" for anchor in anchors)
            lines.append("")
    return "\n".join(lines) + "\n"


def write_report(result: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "rules001_index_validation.json"
    markdown_path = output_dir / "rules001_index_validation.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown_result(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RULES-001 project rules index.")
    parser.add_argument("--rules-path", default=str(DEFAULT_RULES_PATH))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_rules_index(Path(args.rules_path))
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir()
    written = write_report(result, output_dir)
    print("# RULES-001A Index Validation")
    print(f"status={result['status']}")
    print(f"json={written['json']}")
    print(f"markdown={written['markdown']}")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
