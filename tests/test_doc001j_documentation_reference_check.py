from __future__ import annotations

from pathlib import Path

from scripts.check_documentation_references import collect_documentation_references


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_doc001j_reference_checker_detects_unresolved_repo_paths(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "README.md", "# Docs\n\nSee `docs/missing.md`.\n")

    report = collect_documentation_references(tmp_path)

    assert report.unresolved_count == 1
    assert report.status_counts["missing_reference"] == 1


def test_doc001j_reference_checker_accepts_valid_links_and_retired_archive_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "README.md",
        "# Docs\n\n[Architecture](architecture/system_diagrams.md)\n\n"
        "Current path: `docs/architecture/system_diagrams.md`.\n"
        "Old path: `docs/diagrams/architecture.md`.\n"
        "Future target: `docs/archive/planning/`.\n",
    )
    _write(tmp_path / "docs" / "architecture" / "system_diagrams.md", "# System diagrams\n")

    report = collect_documentation_references(tmp_path)

    assert report.unresolved_count == 0
    assert report.status_counts["valid_markdown_link"] == 1
    assert report.status_counts["valid_repo_path"] == 1
    assert report.status_counts["retired_path_reference"] == 1
    assert report.status_counts["planned_path_reference"] == 1


def test_doc001j_current_repository_has_no_unresolved_documentation_references() -> None:
    report = collect_documentation_references(ROOT)

    assert report.unresolved_count == 0
    assert report.status_counts.get("broken_markdown_link", 0) == 0
    assert report.status_counts.get("missing_reference", 0) == 0


def test_doc001j_planning_log_and_archive_controls_explain_the_guard() -> None:
    planning = _read("docs/planning/doc001j_link_reference_check.md")
    archive_status = _read("docs/archive/documentation_path_status.md")
    docs_readme = _read("docs/README.md")

    for text in [planning, archive_status, docs_readme]:
        assert "scripts/check_documentation_references.py" in text

    assert "unresolved_count=0" in planning
    assert "No mass archive move" in planning
