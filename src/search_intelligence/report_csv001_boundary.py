from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Mapping, Sequence

SCHEMA_VERSION = "report_csv001.boundary_check.v1"
WORK_ITEM = "REPORT-CSV-001 Export Boundary Hardening"
REVIEW_OUTPUT_MARKER = "review_output_only_not_pipeline_input"
DEFAULT_SCAN_ROOTS = ("scripts", "src", "tests", "docs")
TEXT_SUFFIXES = {".py", ".md", ".sql", ".txt"}
SKIP_PARTS = {".git", ".venv", "exports", "__pycache__", ".pytest_cache"}
RUNTIME_BOUNDARY_PREFIXES = ("scripts/", "src/")
MARKER_REQUIRED_PREFIXES = ("scripts/", "src/", "docs/")
CSV_READ_PATTERNS = (
    "read_csv",
    "csv.DictReader",
    "csv.reader",
)
CSV_WRITE_PATTERNS = (
    "csv.DictWriter",
    "csv.writer",
    "write_csv",
    "to_csv",
)


@dataclass(frozen=True)
class CsvReference:
    path: str
    line_number: int
    line: str
    kind: str
    marker_present: bool
    export_path_reference: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line_number": self.line_number,
            "line": self.line,
            "kind": self.kind,
            "marker_present": self.marker_present,
            "export_path_reference": self.export_path_reference,
        }


def boundary() -> dict[str, bool | str]:
    return {
        "review_output_only": True,
        "csv_as_pipeline_input_allowed": False,
        "csv_as_gate_input_allowed": False,
        "csv_as_apply_input_allowed": False,
        "exports_csv_read_allowed": False,
        "candidate_creation": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_change": False,
        "bronze_silver_gold_mutation": False,
        "decision_boundary": "csv_export_boundary_audit_not_pipeline_execution",
    }


def build_csv_boundary_report(
    *,
    repo_root: Path,
    scan_roots: Sequence[str | Path] = DEFAULT_SCAN_ROOTS,
    strict_unmarked_exports: bool = False,
    generated_at: str | None = None,
) -> dict[str, object]:
    references = scan_csv_references(repo_root=repo_root, scan_roots=scan_roots)
    disallowed_reads = [
        ref
        for ref in references
        if ref.kind == "read"
        and ref.export_path_reference
        and _is_under_any_prefix(ref.path, RUNTIME_BOUNDARY_PREFIXES)
    ]
    unmarked_export_writes = [
        ref
        for ref in references
        if ref.kind in {"write", "path"}
        and ref.export_path_reference
        and not ref.marker_present
        and _is_under_any_prefix(ref.path, MARKER_REQUIRED_PREFIXES)
    ]
    warning_ids: list[str] = []
    if unmarked_export_writes:
        warning_ids.append("unmarked_csv_export_reference")
    failure_ids: list[str] = []
    if disallowed_reads:
        failure_ids.append("exports_csv_read_reference")
    if strict_unmarked_exports and unmarked_export_writes:
        failure_ids.append("unmarked_csv_export_reference")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": "fail" if failure_ids else ("warning" if warning_ids else "pass"),
        "strict_unmarked_exports": strict_unmarked_exports,
        "failure_ids": failure_ids,
        "warning_ids": warning_ids,
        "summary": {
            "csv_reference_count": len(references),
            "disallowed_export_csv_read_count": len(disallowed_reads),
            "unmarked_export_csv_reference_count": len(unmarked_export_writes),
            "scan_roots": [str(root) for root in scan_roots],
        },
        "safety_boundary": boundary(),
        "disallowed_export_csv_reads": [ref.as_dict() for ref in disallowed_reads],
        "unmarked_export_csv_references": [ref.as_dict() for ref in unmarked_export_writes],
        "all_csv_references": [ref.as_dict() for ref in references],
        "next_action": _next_action(bool(failure_ids), bool(unmarked_export_writes), strict_unmarked_exports),
    }


def scan_csv_references(*, repo_root: Path, scan_roots: Sequence[str | Path]) -> list[CsvReference]:
    refs: list[CsvReference] = []
    for scan_root in scan_roots:
        root = repo_root / Path(scan_root)
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.relative_to(repo_root).parts):
                continue
            refs.extend(_scan_file(repo_root, path))
    return refs


def _is_under_any_prefix(path: str, prefixes: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in prefixes)


def _scan_file(repo_root: Path, path: Path) -> list[CsvReference]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    rel = str(path.relative_to(repo_root))
    refs: list[CsvReference] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if ".csv" not in line and not any(pattern in line for pattern in (*CSV_READ_PATTERNS, *CSV_WRITE_PATTERNS)):
            continue
        stripped = line.strip()
        export_ref = _line_references_export_csv(stripped)
        marker_present = REVIEW_OUTPUT_MARKER in stripped
        if any(pattern in stripped for pattern in CSV_READ_PATTERNS):
            kind = "read"
        elif any(pattern in stripped for pattern in CSV_WRITE_PATTERNS):
            kind = "write"
        else:
            kind = "path"
        refs.append(
            CsvReference(
                path=rel,
                line_number=idx,
                line=stripped,
                kind=kind,
                marker_present=marker_present,
                export_path_reference=export_ref,
            )
        )
    return refs


def _line_references_export_csv(line: str) -> bool:
    normalized = line.replace("\\\\", "/")
    if "exports" not in normalized and "export-dir" not in normalized and "export_dir" not in normalized:
        return False
    return ".csv" in normalized or any(pattern in normalized for pattern in CSV_READ_PATTERNS)


def _next_action(has_failures: bool, has_unmarked_outputs: bool, strict_unmarked_exports: bool) -> str:
    if has_failures:
        return "Remove CSV reads from exports; exports may not be pipeline, gate, apply, or benchmark inputs."
    if has_unmarked_outputs and strict_unmarked_exports:
        return "Rename or manifest CSV review outputs with review_output_only_not_pipeline_input before enabling strict mode."
    if has_unmarked_outputs:
        return "CSV reads are clean; next harden CSV producers by adding review_output_only_not_pipeline_input filename/header/manifest markers."
    return "CSV boundary check passed. Keep CSV exports review-only and never read them back into the pipeline."


def render_markdown(report: Mapping[str, object]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# REPORT-CSV-001 Export Boundary Hardening",
        "",
        f"Generated: `{report.get('generated_at_utc')}`",
        f"Overall status: `{report.get('overall_status')}`",
        "",
        "## Boundary",
        "",
    ]
    safety = report.get("safety_boundary", {})
    if isinstance(safety, Mapping):
        for key, value in safety.items():
            lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- CSV references: `{summary.get('csv_reference_count')}`",
            f"- Disallowed exports CSV reads: `{summary.get('disallowed_export_csv_read_count')}`",
            f"- Unmarked export CSV references: `{summary.get('unmarked_export_csv_reference_count')}`",
            "",
            "## Next action",
            "",
            str(report.get("next_action")),
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(report: Mapping[str, object], export_dir: Path) -> dict[str, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "report_csv001_boundary_check.json"
    md_path = export_dir / "report_csv001_boundary_check.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
