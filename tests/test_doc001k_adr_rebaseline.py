from __future__ import annotations

from pathlib import Path

from scripts.check_adr_rebaseline import build_adr_rebaseline_report

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_doc001k_adr_rebaseline_checker_detects_missing_rows(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "adr" / "001_example.md", "# ADR-001\n\n## Status\n\nAccepted\n")
    _write(tmp_path / "docs" / "governance" / "adr_status_table.md", "# ADR Status Table\n")

    report = build_adr_rebaseline_report(tmp_path)

    assert report.status == "fail"
    assert report.missing_table_rows == ["001"]


def test_doc001k_adr_rebaseline_checker_detects_invalid_statuses(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "adr" / "001_example.md", "# ADR-001\n\n## Status\n\nAccepted\n")
    _write(
        tmp_path / "docs" / "governance" / "adr_status_table.md",
        "| ADR | Repository status | DOC-001K status | Action | Current Truth / replacement pointer |\n"
        "|---|---|---|---|---|\n"
        "| ADR-001 | Accepted | Maybe | Review | `docs/example.md` |\n",
    )

    report = build_adr_rebaseline_report(tmp_path)

    assert report.status == "fail"
    assert report.invalid_doc_statuses == ["ADR-001: Maybe"]


def test_doc001k_current_repository_has_complete_adr_status_table() -> None:
    report = build_adr_rebaseline_report(ROOT)

    assert report.status == "pass"
    assert report.adr_file_count == 33
    assert report.table_row_count == 33
    assert report.missing_table_rows == []
    assert report.extra_table_rows == []
    assert report.invalid_doc_statuses == []
    assert report.stale_repository_statuses == []


def test_doc001k_navigation_points_to_adr_status_surface() -> None:
    docs_readme = _read("docs/README.md")
    governance_readme = _read("docs/reference/governance/README.md")
    adr_readme = _read("docs/decisions/adr/README.md")
    adr_plan = _read("docs/decisions/adr_rebaseline_plan.md")

    for text in [docs_readme, governance_readme, adr_readme, adr_plan]:
        assert "docs/decisions/adr_status_table.md" in text or "adr_status_table.md" in text

    status_table = _read("docs/decisions/adr_status_table.md")
    assert "ADR-017" in status_table
    assert "Superseded" in status_table
    assert "ADR-019" in status_table
    assert "Needs rewrite" in status_table
    assert "ADR-020" in status_table
