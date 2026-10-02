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
    assert "docs/current/REENTRY.md" in text


def test_system_diagrams_include_current_control_surface_and_learning_loops() -> None:
    text = _read("docs/current/system-diagrams.md")

    assert "End-to-end Search Intelligence control surface" in text
    assert "Learning and repair loops" in text
    assert "Origin URL Detective" in text
    assert "Promotion Gatekeeper" in text
    assert text.count("```mermaid") >= 5
