from __future__ import annotations

from pathlib import Path

from scripts.inspect_documentation_rebaseline import collect_documentation_rebaseline


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_documentation_rebaseline_classifies_adr_without_status(tmp_path: Path) -> None:
    _write(tmp_path / "docs/decisions/adr/001_old_decision.md", "# ADR 001\n\nDecision text.\n")

    report = collect_documentation_rebaseline(tmp_path)

    assert report.counts["adr_files"] == 1
    assert report.counts["adr_needs_rebaseline"] == 1
    assert report.adr_status_counts["needs_status_review"] == 1


def test_documentation_rebaseline_reads_adr_status_section(tmp_path: Path) -> None:
    _write(tmp_path / "docs/decisions/adr/002_status_section.md", "# ADR 002\n\n## Status\n\nAccepted\n")

    report = collect_documentation_rebaseline(tmp_path)

    assert report.adr_status_counts["current_or_accepted"] == 1


def test_documentation_rebaseline_treats_planning_as_historical_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "docs/archive/planning/example.md", "# Build note\n")

    report = collect_documentation_rebaseline(tmp_path)

    assert report.classification_counts["archive_or_historical_candidate"] == 1
    assert report.items[0].classification == "archive_or_historical_candidate"


def test_documentation_rebaseline_excludes_exported_project_state_from_docs_inventory(tmp_path: Path) -> None:
    _write(tmp_path / "exports/project_state/handover_delta.md", "# Handover\n")

    report = collect_documentation_rebaseline(tmp_path)

    assert report.counts["markdown_files"] == 0
    assert "handover_context_not_current_truth" not in report.classification_counts


def test_documentation_rebaseline_marks_architecture_as_current_truth_candidate(tmp_path: Path) -> None:
    _write(tmp_path / "docs/current/architecture.md", "# Current system\n")

    report = collect_documentation_rebaseline(tmp_path)

    assert report.classification_counts["current_truth_candidate"] == 1
    assert report.items[0].classification == "current_truth_candidate"


def test_documentation_rebaseline_excludes_exports(tmp_path: Path) -> None:
    _write(tmp_path / "exports/report.md", "# Runtime report\n")
    _write(tmp_path / "docs/current/architecture.md", "# Current system\n")

    report = collect_documentation_rebaseline(tmp_path)

    assert report.counts["markdown_files"] == 1
    assert report.items[0].path == "docs/current/architecture.md"
