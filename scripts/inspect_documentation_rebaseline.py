#!/usr/bin/env python3
"""DOC-001A read-only documentation rebaseline inventory.

This script inventories repository documentation and classifies files for the
DOC-001 rebaseline campaign. It does not mutate repository documentation.
When --write-report is used, it writes human-readable reports to exports/.

Intentional exclusions:
- exports/: runtime/report artifacts, not maintained documentation
- .venv/.git/__pycache__: local/tooling artifacts
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


CURRENT_TRUTH_PATH_MARKERS = (
    "docs/current/",
)

REFERENCE_PATH_MARKERS = (
    "docs/reference/",
    "docs/decisions/",
    "docs/guides/",
)

HISTORICAL_PATH_MARKERS = (
    "docs/archive/planning/",
    "docs/archive/source-analysis/",
    "docs/archive/reviews/",
    "docs/archive/visualization/",
    "docs/archive/legacy/",
    "docs/archive/documentation-rebaseline/",
)

HANDOVER_PATH_MARKERS = (
    "exports/project_state/",
)

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "exports",
}


@dataclass(frozen=True)
class DocumentationInventoryItem:
    path: str
    line_count: int
    classification: str
    reason: str
    adr_status: str | None = None
    contains_current_truth_language: bool = False
    contains_historical_language: bool = False


@dataclass(frozen=True)
class DocumentationRebaselineReport:
    generated_at: str
    campaign: str
    boundary: dict[str, bool]
    counts: dict[str, int]
    classification_counts: dict[str, int]
    adr_status_counts: dict[str, int]
    items: list[DocumentationInventoryItem]
    priority_actions: list[str]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _contains_current_truth_language(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in (
            "current truth",
            "current architecture",
            "current system",
            "status: current",
            "status: accepted",
            "source of truth",
            "active architecture contract",
        )
    )


def _contains_historical_language(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in (
            "historical",
            "archived",
            "superseded",
            "legacy",
            "not current",
            "build log",
        )
    )


def _detect_adr_status(path: str, text: str) -> str | None:
    if not path.startswith("docs/decisions/adr/") or not path.endswith(".md"):
        return None
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith("status:"):
            status = stripped.split(":", 1)[1].strip()
            return _normalize_adr_status(status)
        if stripped == "## status":
            for candidate in lines[idx + 1 : idx + 6]:
                value = candidate.strip().lower()
                if value and not value.startswith("---"):
                    return _normalize_adr_status(value)
            return "needs_status_review"
    return "needs_status_review"


def _normalize_adr_status(status: str) -> str:
    if status in {"current", "accepted"}:
        return "current_or_accepted"
    if status == "superseded":
        return "superseded"
    if status in {"historical", "archived"}:
        return "historical_or_archived"
    if status in {"needs rewrite", "needs_rewrite"}:
        return "needs_rewrite"
    return "has_unclassified_status"


def classify_document(path: str, text: str) -> tuple[str, str, str | None]:
    lower_path = path.lower()
    adr_status = _detect_adr_status(lower_path, text)

    if lower_path == "readme.md":
        return (
            "current_truth_candidate",
            "README is a primary entry point and must be reconciled during DOC-001.",
            adr_status,
        )

    if lower_path.startswith("docs/decisions/adr/"):
        if adr_status == "needs_status_review":
            return (
                "adr_needs_rebaseline",
                "ADR file needs explicit DOC-001 status classification.",
                adr_status,
            )
        return (
            "adr_review_candidate",
            "ADR file needs Current / Superseded / Historical / Needs rewrite confirmation.",
            adr_status,
        )

    if lower_path.startswith(HANDOVER_PATH_MARKERS):
        return (
            "handover_context_not_current_truth",
            "Project-state handover context is useful but must not become current architecture truth.",
            adr_status,
        )

    if lower_path.startswith(HISTORICAL_PATH_MARKERS):
        return (
            "archive_or_historical_candidate",
            "Planning and source-analysis docs are likely historical build logs unless promoted into Current Truth.",
            adr_status,
        )

    if lower_path.startswith(CURRENT_TRUTH_PATH_MARKERS):
        return (
            "current_truth_candidate",
            "Architecture/governance/security docs are candidates for the reduced Current Truth documentation layer.",
            adr_status,
        )

    if lower_path.startswith(REFERENCE_PATH_MARKERS):
        return (
            "reference_candidate",
            "Reference docs may remain useful but must not contradict the Current Truth layer.",
            adr_status,
        )

    if lower_path.startswith("docs/"):
        return (
            "needs_doc001_review",
            "Documentation file is outside the primary DOC-001 buckets and needs explicit review.",
            adr_status,
        )

    return (
        "non_docs_markdown_review",
        "Markdown outside docs may be an entry point or auxiliary artifact.",
        adr_status,
    )


def _is_included_markdown(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return not any(part in EXCLUDED_PARTS for part in rel_parts)


def collect_documentation_rebaseline(root: Path) -> DocumentationRebaselineReport:
    markdown_files = sorted(
        p
        for p in root.rglob("*.md")
        if _is_included_markdown(p, root)
    )

    items: list[DocumentationInventoryItem] = []
    for path in markdown_files:
        rel = path.relative_to(root).as_posix()
        text = _read_text(path)
        classification, reason, adr_status = classify_document(rel, text)
        items.append(
            DocumentationInventoryItem(
                path=rel,
                line_count=len(text.splitlines()),
                classification=classification,
                reason=reason,
                adr_status=adr_status,
                contains_current_truth_language=_contains_current_truth_language(text),
                contains_historical_language=_contains_historical_language(text),
            )
        )

    classification_counts = Counter(item.classification for item in items)
    adr_status_counts = Counter(
        item.adr_status for item in items if item.adr_status is not None
    )

    priority_actions = [
        "Create a reduced Current Truth documentation layer before rewriting historical docs.",
        "Run ADR rebaseline: classify ADRs as Current, Superseded, Historical, or Needs rewrite.",
        "Treat docs/archive/planning and docs/archive/source-analysis as historical by default unless promoted.",
        "Rebuild current architecture and system diagrams after GOV-001 closes.",
        "Archive or deprecate misleading docs rather than patching obsolete narratives.",
        "Keep docs/project_state out of current documentation truth and out of accidental commits.",
        "Keep exports/ out of the documentation inventory; exports are runtime/report artifacts.",
    ]

    return DocumentationRebaselineReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        campaign="DOC-001A Documentation Rebaseline Inventory",
        boundary={
            "read_only_inventory": True,
            "no_repo_documentation_mutation": True,
            "no_db_access": True,
            "no_external_network": True,
            "no_pipeline_execution": True,
            "exports_excluded_from_inventory": True,
        },
        counts={
            "markdown_files": len(items),
            "docs_markdown_files": sum(1 for item in items if item.path.startswith("docs/")),
            "adr_files": sum(1 for item in items if item.path.startswith("docs/decisions/adr/")),
            "planning_docs": sum(1 for item in items if item.path.startswith("docs/archive/planning/")),
            "source_analysis_docs": sum(1 for item in items if item.path.startswith("docs/archive/source-analysis/")),
            "current_truth_candidates": classification_counts.get("current_truth_candidate", 0),
            "archive_or_historical_candidates": classification_counts.get("archive_or_historical_candidate", 0),
            "adr_needs_rebaseline": classification_counts.get("adr_needs_rebaseline", 0),
        },
        classification_counts=dict(sorted(classification_counts.items())),
        adr_status_counts=dict(sorted(adr_status_counts.items())),
        items=items,
        priority_actions=priority_actions,
    )


def _write_reports(root: Path, report: DocumentationRebaselineReport, label: str) -> None:
    out_dir = root / "exports" / "doc001_documentation_rebaseline"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{label}_documentation_rebaseline_inventory.json"
    json_path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = out_dir / f"{label}_documentation_rebaseline_inventory.md"
    lines = [
        "# DOC-001A Documentation Rebaseline Inventory",
        "",
        f"Generated at: {report.generated_at}",
        "",
        "## Boundary",
    ]
    for key, value in report.boundary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Counts"])
    for key, value in report.counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Classification counts"])
    for key, value in report.classification_counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## ADR status counts"])
    for key, value in report.adr_status_counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Priority actions"])
    for action in report.priority_actions:
        lines.append(f"- {action}")
    lines.extend(["", "## Items"])
    for item in report.items:
        adr = f" | adr_status={item.adr_status}" if item.adr_status else ""
        flags = []
        if item.contains_current_truth_language:
            flags.append("current-truth-language")
        if item.contains_historical_language:
            flags.append("historical-language")
        flag_text = f" | flags={','.join(flags)}" if flags else ""
        lines.append(f"- {item.path} | {item.classification}{adr}{flag_text} | lines={item.line_count}")

    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print("Wrote:")
    print(json_path)
    print(md_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect documentation for DOC-001 rebaseline.")
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout.")
    parser.add_argument("--write-report", action="store_true", help="Write JSON and Markdown reports to exports/.")
    parser.add_argument("--label", default="doc001a", help="Report label.")
    args = parser.parse_args()

    root = Path.cwd()
    report = collect_documentation_rebaseline(root)

    if args.write_report:
        _write_reports(root, report, args.label)

    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print("DOC-001A documentation rebaseline inventory")
        for key, value in report.counts.items():
            print(f"{key}={value}")
        print("classification_counts=" + json.dumps(report.classification_counts, ensure_ascii=False))
        print("adr_status_counts=" + json.dumps(report.adr_status_counts, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
