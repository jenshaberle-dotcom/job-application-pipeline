from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ALLOWED_DOC_STATUSES = {"Current", "Superseded", "Historical", "Needs rewrite"}
ADR_FILE_RE = re.compile(r"^(?P<number>\d{3})_.*\.md$")
TABLE_ROW_RE = re.compile(r"^\|\s*ADR-(?P<number>\d{3})\s*\|")


@dataclass(frozen=True)
class AdrFile:
    number: str
    path: str
    repository_status: str


@dataclass(frozen=True)
class AdrStatusRow:
    number: str
    repository_status: str
    doc_status: str
    action: str
    pointer: str


@dataclass(frozen=True)
class AdrRebaselineReport:
    status: str
    adr_file_count: int
    table_row_count: int
    missing_table_rows: list[str]
    extra_table_rows: list[str]
    invalid_doc_statuses: list[str]
    stale_repository_statuses: list[str]

    @property
    def issue_count(self) -> int:
        return (
            len(self.missing_table_rows)
            + len(self.extra_table_rows)
            + len(self.invalid_doc_statuses)
            + len(self.stale_repository_statuses)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "adr_file_count": self.adr_file_count,
            "table_row_count": self.table_row_count,
            "missing_table_rows": self.missing_table_rows,
            "extra_table_rows": self.extra_table_rows,
            "invalid_doc_statuses": self.invalid_doc_statuses,
            "stale_repository_statuses": self.stale_repository_statuses,
            "issue_count": self.issue_count,
        }


def _extract_repository_status(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Status:"):
            return stripped.removeprefix("Status:").strip()
        if stripped == "## Status":
            for next_line in lines[index + 1 :]:
                if next_line.strip():
                    return next_line.strip()
    return ""


def collect_adr_files(root: Path) -> list[AdrFile]:
    adr_dir = root / "docs" / "adr"
    files: list[AdrFile] = []
    for path in sorted(adr_dir.glob("[0-9]*.md")):
        match = ADR_FILE_RE.match(path.name)
        if not match:
            continue
        files.append(
            AdrFile(
                number=match.group("number"),
                path=path.relative_to(root).as_posix(),
                repository_status=_extract_repository_status(path.read_text(encoding="utf-8")),
            )
        )
    return files


def parse_adr_status_table(root: Path) -> list[AdrStatusRow]:
    table_path = root / "docs" / "governance" / "adr_status_table.md"
    if not table_path.exists():
        return []

    rows: list[AdrStatusRow] = []
    for line in table_path.read_text(encoding="utf-8").splitlines():
        if not TABLE_ROW_RE.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        number = cells[0].removeprefix("ADR-").strip()
        rows.append(
            AdrStatusRow(
                number=number,
                repository_status=cells[1],
                doc_status=cells[2],
                action=cells[3],
                pointer=cells[4],
            )
        )
    return rows


def build_adr_rebaseline_report(root: Path) -> AdrRebaselineReport:
    adr_files = collect_adr_files(root)
    rows = parse_adr_status_table(root)

    file_numbers = {adr.number for adr in adr_files}
    row_numbers = {row.number for row in rows}
    file_status_by_number = {adr.number: adr.repository_status for adr in adr_files}

    missing_table_rows = sorted(file_numbers - row_numbers)
    extra_table_rows = sorted(row_numbers - file_numbers)
    invalid_doc_statuses = sorted(
        f"ADR-{row.number}: {row.doc_status}" for row in rows if row.doc_status not in ALLOWED_DOC_STATUSES
    )
    stale_repository_statuses = sorted(
        f"ADR-{row.number}: table={row.repository_status} file={file_status_by_number.get(row.number, '<missing>')}"
        for row in rows
        if row.number in file_status_by_number and row.repository_status != file_status_by_number[row.number]
    )

    issue_count = (
        len(missing_table_rows)
        + len(extra_table_rows)
        + len(invalid_doc_statuses)
        + len(stale_repository_statuses)
    )

    return AdrRebaselineReport(
        status="pass" if issue_count == 0 else "fail",
        adr_file_count=len(adr_files),
        table_row_count=len(rows),
        missing_table_rows=missing_table_rows,
        extra_table_rows=extra_table_rows,
        invalid_doc_statuses=invalid_doc_statuses,
        stale_repository_statuses=stale_repository_statuses,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check ADR rebaseline status table coverage.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args()

    report = build_adr_rebaseline_report(Path(args.root).resolve())
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"status={report.status}")
        print(f"adr_file_count={report.adr_file_count}")
        print(f"table_row_count={report.table_row_count}")
        print(f"issue_count={report.issue_count}")
        for key, values in report.to_dict().items():
            if isinstance(values, list) and values:
                print(f"{key}:")
                for value in values:
                    print(f"- {value}")
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
