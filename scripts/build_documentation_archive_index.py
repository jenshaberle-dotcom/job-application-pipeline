#!/usr/bin/env python3
"""Build DOC-001 archive/deprecation indexes for historical documentation areas.

This script writes documentation index files only. It does not move, delete, or
edit the historical documents themselves.

Default targets:
- docs/archive/planning/
- docs/archive/source-analysis/
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DIRECTORIES = [
    Path("docs/archive/planning"),
    Path("docs/archive/source-analysis"),
]


@dataclass(frozen=True)
class ArchiveIndexItem:
    path: str
    title: str
    line_count: int
    suggested_bucket: str
    reason: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _extract_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()
    return path.stem.replace("_", " ").replace("-", " ").title()


def classify_historical_doc(relative_path: str, text: str) -> tuple[str, str]:
    lower_path = relative_path.lower()
    lower_text = text.lower()

    if lower_path.endswith("/readme.md"):
        return (
            "historical_directory_navigation",
            "Directory README explains historical/reference status for the area.",
        )

    if "doc001" in lower_path or "gov001" in lower_path:
        return (
            "governance_or_rebaseline_build_log",
            "GOV/DOC campaign planning note; keep for traceability, not current architecture truth.",
        )

    if any(marker in lower_path for marker in ("detail", "gate", "stop", "evidence")):
        return (
            "evidence_gate_history",
            "Evidence/gate implementation history; promote only stable rules into Current Truth docs.",
        )

    if any(marker in lower_path for marker in ("connector", "registration", "activation", "approval")):
        return (
            "connector_chain_history",
            "Connector/activation build history; keep for traceability, not as active process doc.",
        )

    if any(marker in lower_path for marker in ("stepstone", "aggregator", "greenhouse", "personio", "source")):
        return (
            "source_strategy_history",
            "Source/sensor analysis history; keep as reference unless promoted into source strategy.",
        )

    if any(marker in lower_path for marker in ("hdi", "enercity", "finanz", "ratiodata", "vhv")):
        return (
            "employer_specific_history",
            "Employer-specific review history; not general current architecture.",
        )

    if any(marker in lower_text for marker in ("historical", "legacy", "superseded", "not current")):
        return (
            "explicit_historical_context",
            "Document already contains historical/legacy language.",
        )

    return (
        "historical_build_note",
        "Historical planning/source-analysis document unless explicitly promoted during DOC-001.",
    )


def _resolve_archive_directory(root: Path, directory: Path) -> Path:
    if (root / directory).exists():
        return root / directory
    aliases = {
        Path("docs/planning"): Path("docs/archive/planning"),
        Path("docs/source_analysis"): Path("docs/archive/source-analysis"),
        Path("docs/source-analysis"): Path("docs/archive/source-analysis"),
    }
    return root / aliases.get(directory, directory)


def collect_archive_items(root: Path, directories: list[Path]) -> list[ArchiveIndexItem]:
    items: list[ArchiveIndexItem] = []

    for directory in directories:
        base = _resolve_archive_directory(root, directory)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            text = _read_text(path)
            rel = path.relative_to(root).as_posix()
            bucket, reason = classify_historical_doc(rel, text)
            items.append(
                ArchiveIndexItem(
                    path=rel,
                    title=_extract_title(path, text),
                    line_count=len(text.splitlines()),
                    suggested_bucket=bucket,
                    reason=reason,
                )
            )

    return items


def render_archive_index(title: str, items: list[ArchiveIndexItem], *, generated_at: str) -> str:
    lines = [
        f"# {title}",
        "",
        "Status: DOC-001 archive/deprecation index",
        f"Generated at: {generated_at}",
        "",
        "## Purpose",
        "",
        "This index keeps historical documentation discoverable while preventing it",
        "from being mistaken for current architecture truth.",
        "",
        "No files are moved or deleted by this index.",
        "",
        "## Buckets",
        "",
    ]

    bucket_names = sorted({item.suggested_bucket for item in items})
    for bucket in bucket_names:
        count = sum(1 for item in items if item.suggested_bucket == bucket)
        lines.append(f"- `{bucket}`: {count}")

    lines.extend(["", "## Items", ""])

    for item in items:
        lines.extend(
            [
                f"### `{item.path}`",
                "",
                f"- Title: {item.title}",
                f"- Suggested bucket: `{item.suggested_bucket}`",
                f"- Lines: {item.line_count}",
                f"- Reason: {item.reason}",
                "- DOC-001 action: Keep as historical/reference unless promoted into Current Truth.",
                "",
            ]
        )

    lines.extend(
        [
            "## Promotion rule",
            "",
            "A historical document becomes current only when its content is rewritten or",
            "promoted into the Current Truth layer, ADR status table, governance docs,",
            "operator runbook, or current architecture/system diagrams.",
            "",
        ]
    )

    return "\n".join(lines)


def write_archive_indexes(root: Path) -> list[Path]:
    generated_at = datetime.now(timezone.utc).isoformat()
    planning_items = collect_archive_items(root, [Path("docs/archive/planning")])
    source_items = collect_archive_items(root, [Path("docs/archive/source-analysis")])

    archive_dir = root / "docs" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    files = {
        archive_dir / "planning_archive_index.md": render_archive_index(
            "Planning Archive Index",
            planning_items,
            generated_at=generated_at,
        ),
        archive_dir / "source_analysis_archive_index.md": render_archive_index(
            "Source Analysis Archive Index",
            source_items,
            generated_at=generated_at,
        ),
        archive_dir / "README.md": _render_archive_readme(
            planning_count=len(planning_items),
            source_analysis_count=len(source_items),
            generated_at=generated_at,
        ),
    }

    for path, content in files.items():
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        written.append(path)

    return written


def _render_archive_readme(*, planning_count: int, source_analysis_count: int, generated_at: str) -> str:
    return f"""# Documentation Archive Index

Status: DOC-001 archive/deprecation navigation
Generated at: {generated_at}

## Purpose

This directory contains archive/deprecation indexes, not moved historical files.

Historical files now live under `docs/archive/`. The indexes make that historical
surface explicit and searchable without pretending it is current architecture.

## Indexes

| Index | Scope | Items |
|---|---|---:|
| `planning_archive_index.md` | `docs/archive/planning/` | {planning_count} |
| `source_analysis_archive_index.md` | `docs/archive/source-analysis/` | {source_analysis_count} |

## Rule

Historical documents remain useful as traceability, but they are not current
architecture truth unless explicitly promoted during DOC-001.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DOC-001 archive/deprecation indexes.")
    parser.add_argument("--check", action="store_true", help="Report what would be written without writing.")
    args = parser.parse_args()

    root = Path.cwd()

    if args.check:
        planning_items = collect_archive_items(root, [Path("docs/archive/planning")])
        source_items = collect_archive_items(root, [Path("docs/archive/source-analysis")])
        print("DOC-001E archive index check")
        print(f"planning_items={len(planning_items)}")
        print(f"source_analysis_items={len(source_items)}")
        return 0

    written = write_archive_indexes(root)
    print("Wrote:")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
