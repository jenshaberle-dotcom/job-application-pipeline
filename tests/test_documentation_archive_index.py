from __future__ import annotations

from pathlib import Path

from scripts.build_documentation_archive_index import (
    classify_historical_doc,
    collect_archive_items,
    write_archive_indexes,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_archive_index_classifies_connector_history() -> None:
    bucket, reason = classify_historical_doc(
        "docs/archive/source-analysis/employer_origin_connector_candidate_agent.md",
        "# Connector Candidate\n",
    )

    assert bucket == "connector_chain_history"
    assert "Connector" in reason


def test_archive_index_collects_planning_items(tmp_path: Path) -> None:
    _write(tmp_path / "docs/archive/planning/detail001.md", "# Detail Discovery\n")

    items = collect_archive_items(tmp_path, [Path("docs/planning")])

    assert len(items) == 1
    assert items[0].path == "docs/archive/planning/detail001.md"
    assert items[0].suggested_bucket == "evidence_gate_history"


def test_archive_index_writes_index_files(tmp_path: Path) -> None:
    _write(tmp_path / "docs/archive/planning/gov001.md", "# GOV 001\n")
    _write(tmp_path / "docs/archive/source-analysis/stepstone.md", "# StepStone\n")

    written = write_archive_indexes(tmp_path)

    written_paths = {path.relative_to(tmp_path).as_posix() for path in written}
    assert "docs/archive/README.md" in written_paths
    assert "docs/archive/planning_archive_index.md" in written_paths
    assert "docs/archive/source_analysis_archive_index.md" in written_paths

    planning_index = (tmp_path / "docs/archive/planning_archive_index.md").read_text(encoding="utf-8")
    assert "docs/archive/planning/gov001.md" in planning_index
    assert "governance_or_rebaseline_build_log" in planning_index
