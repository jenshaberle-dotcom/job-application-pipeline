from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_root_readme_has_project_motivation_and_design_language() -> None:
    text = _read("README.md")

    assert "## Why this project exists" in text
    assert "Deep Ocean / Search Intelligence" in text
    assert "false negatives" in text
    assert "This is a portfolio project" in text


def test_readme_preserves_architecture_contract_anchors() -> None:
    text = _read("README.md")

    assert "ARCH-001-SAFETY-SECURITY-STATE" in text
    assert "docs/reference/governance/governance_foundation.md" in text
    assert "docs/reference/governance/documentation_drift_baseline.md" in text
    assert "docs/archive/planning/eo002b_candidate_reprocessing_url_finder_validation.md" in text


def test_system_diagrams_include_current_control_surface_and_learning_loops() -> None:
    text = _read("docs/current/system-diagrams.md")

    assert "End-to-end Search Intelligence control surface" in text
    assert "Learning and repair loops" in text
    assert "Origin URL Detective" in text
    assert "Promotion Gatekeeper" in text
    assert text.count("```mermaid") >= 5


def test_architecture_document_status_covers_all_architecture_markdown_files() -> None:
    status = _read("docs/archive/documentation-rebaseline/architecture_document_status.md")
    architecture_files = sorted(
        path.name for path in (ROOT / "docs" / "architecture").glob("*.md")
    )

    missing = [name for name in architecture_files if f"`{name}`" not in status]

    assert not missing


def test_legacy_search_intelligence_docs_are_not_primary_current_truth() -> None:
    for rel_path in [
        "docs/reference/search-intelligence/architecture.md",
        "docs/reference/search-intelligence/current_state.md",
        "docs/archive/legacy/historical_terminology.md",
    ]:
        text = _read(rel_path)
        assert "DOC-001G note" in text
        assert "not the primary Current Truth entry point" in text or "not a primary Current Truth entry point" in text
