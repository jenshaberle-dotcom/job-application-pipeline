#!/usr/bin/env python3
"""DOC-001J documentation link and repo-path reference check.

The check is intentionally lightweight and repository-local:

- Markdown links must resolve when they point to local files.
- Repo-path references such as ``docs/...`` or ``scripts/...`` in Markdown prose
  must either exist or be classified as an intentional retired/planned path.
- The script does not mutate documentation. ``--write-report`` writes a
  human-readable report to ``exports/`` only.

This protects DOC-001 archive moves from silently breaking navigation while
still allowing historical documents to mention old paths when the reference is
explicitly part of an archive/redirect map.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote


EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "exports",
}

REPO_PATH_PREFIXES = (
    "README.md",
    "docs/",
    "db/",
    "scripts/",
    "src/",
    "tests/",
)

RETIRED_PATH_REFERENCES: dict[str, str] = {
    "docs/diagrams/": "Retired diagram directory; current replacements live under docs/current/ and docs/reference/database/.",
    "docs/diagrams": "Retired diagram directory; current replacements live under docs/current/ and docs/reference/database/.",
    "docs/diagrams/architecture.md": "Historical old path kept only in DOC-001I archive mapping; replacement is docs/current/system-diagrams.md.",
    "docs/diagrams/bronze_data_model.md": "Historical old path kept only in DOC-001I archive mapping; replacement is docs/reference/database/schema_relationships.md.",
}

PLANNED_PATH_REFERENCES: dict[str, str] = {
    "docs/archive/planning/": "Planned or existing archive target for historical planning files.",
    "docs/archive/source-analysis/": "Planned or existing archive target for historical source-analysis files.",
    "docs/archive/source_analysis/": "Pre-DOC-001L underscore spelling; current archive target is docs/archive/source-analysis/.",
}

RETIRED_PATH_PREFIXES: dict[str, str] = {
    "docs/adr/": "Pre-DOC-001L ADR path; current ADRs live under docs/decisions/adr/.",
    "docs/architecture/": "Pre-DOC-001L architecture path; current truth moved to docs/current/ and detailed reference to docs/reference/.",
    "docs/classification/": "Pre-DOC-001L classification path; scoring and gate references live under docs/reference/scoring-and-gates/.",
    "docs/data_sources/": "Pre-DOC-001L source-reference path; current reference lives under docs/reference/sources/.",
    "docs/database/": "Pre-DOC-001L database path; current database reference lives under docs/reference/database/.",
    "docs/design/": "Pre-DOC-001L design path; current product/documentation references live under docs/reference/product/ and docs/reference/documentation/.",
    "docs/development/": "Pre-DOC-001L development path; current guides live under docs/guides/.",
    "docs/governance/": "Pre-DOC-001L governance path; current governance reference lives under docs/reference/governance/ and decisions under docs/decisions/.",
    "docs/observability/": "Pre-DOC-001L observability path; current reference lives under docs/reference/observability/.",
    "docs/operations/": "Pre-DOC-001L operations path; guides live under docs/guides/ and reference under docs/reference/operations/.",
    "docs/relevance/": "Pre-DOC-001L relevance path; current scoring/gate reference lives under docs/reference/scoring-and-gates/.",
    "docs/reviews/": "Pre-DOC-001L review path; historical reviews live under docs/archive/reviews/.",
    "docs/security/": "Pre-DOC-001L security path; current security reference lives under docs/reference/security/.",
    "docs/source_analysis/": "Pre-DOC-001L source-analysis path; historical material lives under docs/archive/source-analysis/.",
    "docs/visualization/": "Pre-DOC-001L visualization path; historical material lives under docs/archive/visualization/.",
}

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
REFERENCE_LINK_RE = re.compile(r"^\s*\[([^\]]+)\]:\s+(\S+)", re.MULTILINE)
REPO_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"((?:README\.md|(?:docs|db|scripts|src|tests)/[A-Za-z0-9_./{}*?<>:-]+))"
    r"(?![A-Za-z0-9_./-])"
)


@dataclass(frozen=True)
class DocumentationReference:
    file_path: str
    line: int
    reference: str
    reference_type: str
    status: str
    note: str


@dataclass(frozen=True)
class DocumentationReferenceReport:
    generated_at: str
    checked_markdown_files: int
    total_references: int
    status_counts: dict[str, int]
    references: list[DocumentationReference]

    @property
    def unresolved_count(self) -> int:
        return self.status_counts.get("missing_reference", 0) + self.status_counts.get(
            "broken_markdown_link", 0
        )


@dataclass(frozen=True)
class DocumentationReferenceExitSummary:
    generated_at: str
    checked_markdown_files: int
    total_references: int
    status_counts: dict[str, int]
    unresolved_count: int
    status: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _is_included_markdown(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return path.suffix.lower() == ".md" and not any(part in EXCLUDED_PARTS for part in rel_parts)


def _line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _strip_markdown_destination(raw: str) -> str:
    destination = raw.strip().strip("<>")
    if not destination:
        return destination
    if " " in destination and not destination.startswith("#"):
        destination = destination.split()[0]
    return destination.strip().rstrip("`.,;)\\]\\\"'")


def _strip_repo_path_reference(raw: str) -> str:
    reference = raw.strip().rstrip("`.,;)\\]\\\"'")
    return reference.split("#", 1)[0]


def _is_external_or_anchor(destination: str) -> bool:
    lowered = destination.lower()
    if destination.startswith("#"):
        return True
    if lowered.startswith(("http://", "https://", "mailto:")):
        return True
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", destination))


def _path_exists(path: Path) -> bool:
    return path.exists()


def _classify_repo_path_reference(root: Path, reference: str) -> tuple[str, str]:
    if any(char in reference for char in "{}*?<>:"):
        return "pattern_reference", "Pattern/example reference; not expected to resolve as a concrete repository path."
    if reference in RETIRED_PATH_REFERENCES:
        return "retired_path_reference", RETIRED_PATH_REFERENCES[reference]
    if reference in PLANNED_PATH_REFERENCES:
        return "planned_path_reference", PLANNED_PATH_REFERENCES[reference]
    if _path_exists(root / reference):
        return "valid_repo_path", "Repository path exists."
    for prefix, note in RETIRED_PATH_PREFIXES.items():
        if reference.startswith(prefix):
            return "retired_path_reference", note
    return "missing_reference", "Repository path reference does not resolve and is not classified as retired or planned."


def _collect_markdown_link_references(root: Path, path: Path, text: str) -> list[DocumentationReference]:
    references: list[DocumentationReference] = []

    matches = list(MARKDOWN_LINK_RE.finditer(text)) + list(REFERENCE_LINK_RE.finditer(text))
    for match in matches:
        raw_destination = match.group(2)
        destination = _strip_markdown_destination(raw_destination)
        if not destination or _is_external_or_anchor(destination):
            continue

        destination_without_anchor = unquote(destination.split("#", 1)[0])
        if not destination_without_anchor:
            continue

        target = (path.parent / destination_without_anchor).resolve()
        status = "valid_markdown_link" if _path_exists(target) else "broken_markdown_link"
        note = "Local Markdown link target exists." if status == "valid_markdown_link" else "Local Markdown link target does not exist."
        references.append(
            DocumentationReference(
                file_path=path.relative_to(root).as_posix(),
                line=_line_number(text, match.start()),
                reference=destination,
                reference_type="markdown_link",
                status=status,
                note=note,
            )
        )

    return references


def _collect_repo_path_references(root: Path, path: Path, text: str) -> list[DocumentationReference]:
    references: list[DocumentationReference] = []

    for match in REPO_PATH_RE.finditer(text):
        reference = _strip_repo_path_reference(match.group(1))
        if not reference or not reference.startswith(REPO_PATH_PREFIXES):
            continue

        status, note = _classify_repo_path_reference(root, reference)
        references.append(
            DocumentationReference(
                file_path=path.relative_to(root).as_posix(),
                line=_line_number(text, match.start()),
                reference=reference,
                reference_type="repo_path_reference",
                status=status,
                note=note,
            )
        )

    return references


def collect_documentation_references(root: Path) -> DocumentationReferenceReport:
    markdown_files = sorted(path for path in root.rglob("*.md") if _is_included_markdown(path, root))

    references: list[DocumentationReference] = []
    seen: set[tuple[str, int, str, str]] = set()

    for path in markdown_files:
        text = _read_text(path)
        for reference in [
            *_collect_markdown_link_references(root, path, text),
            *_collect_repo_path_references(root, path, text),
        ]:
            key = (
                reference.file_path,
                reference.line,
                reference.reference,
                reference.reference_type,
            )
            if key in seen:
                continue
            seen.add(key)
            references.append(reference)

    status_counts = Counter(reference.status for reference in references)
    return DocumentationReferenceReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        checked_markdown_files=len(markdown_files),
        total_references=len(references),
        status_counts=dict(sorted(status_counts.items())),
        references=references,
    )


def render_markdown_report(report: DocumentationReferenceReport) -> str:
    lines = [
        "# DOC-001J Documentation Reference Check",
        "",
        "Status: generated reference-check report",
        f"Generated at: {report.generated_at}",
        "",
        "## Summary",
        "",
        f"- Checked Markdown files: {report.checked_markdown_files}",
        f"- Total local references: {report.total_references}",
        f"- Unresolved references: {report.unresolved_count}",
        "",
        "## Status counts",
        "",
    ]

    for status, count in sorted(report.status_counts.items()):
        lines.append(f"- `{status}`: {count}")

    lines.extend(["", "## Non-valid references", ""])
    non_valid = [
        reference
        for reference in report.references
        if reference.status not in {"valid_markdown_link", "valid_repo_path"}
    ]
    if not non_valid:
        lines.append("No non-valid references found.")
    else:
        for reference in non_valid:
            lines.extend(
                [
                    f"### `{reference.file_path}:{reference.line}`",
                    "",
                    f"- Reference: `{reference.reference}`",
                    f"- Type: `{reference.reference_type}`",
                    f"- Status: `{reference.status}`",
                    f"- Note: {reference.note}",
                    "",
                ]
            )

    lines.extend(
        [
            "## DOC-001J rule",
            "",
            "Before a larger physical archive move, unresolved references must be",
            "either fixed, converted into explicit historical/retired-path mentions,",
            "or represented by a planned archive target that is documented here.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _write_report(root: Path, report: DocumentationReferenceReport) -> Path:
    export_dir = root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = export_dir / f"doc001j_documentation_reference_check_{timestamp}.md"
    path.write_text(render_markdown_report(report), encoding="utf-8")
    return path


def build_exit_summary(report: DocumentationReferenceReport) -> DocumentationReferenceExitSummary:
    status = "pass" if report.unresolved_count == 0 else "fail"
    return DocumentationReferenceExitSummary(
        generated_at=report.generated_at,
        checked_markdown_files=report.checked_markdown_files,
        total_references=report.total_references,
        status_counts=report.status_counts,
        unresolved_count=report.unresolved_count,
        status=status,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check documentation links and repository path references.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current working directory.")
    parser.add_argument("--write-report", action="store_true", help="Write a Markdown report to exports/.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = collect_documentation_references(root)
    summary = build_exit_summary(report)

    if args.write_report:
        report_path = _write_report(root, report)
        print(f"wrote_report={report_path.relative_to(root).as_posix()}")

    if args.json:
        print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    else:
        print(f"DOC-001J documentation reference check: {summary.status}")
        print(f"checked_markdown_files={summary.checked_markdown_files}")
        print(f"total_references={summary.total_references}")
        print(f"unresolved_count={summary.unresolved_count}")
        for status, count in sorted(summary.status_counts.items()):
            print(f"{status}={count}")

    return 0 if summary.unresolved_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
