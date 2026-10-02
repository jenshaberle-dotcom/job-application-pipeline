from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_governance_foundation_documents_required_checks() -> None:
    text = read("docs/reference/governance/governance_foundation.md")

    for phrase in [
        "System Impact Check",
        "Project Drift Index",
        "Lessons Learned Check",
        "White Whale Backlog",
        "Conversation Health Check",
        "Reflection Pass",
        "Documentation as Product Surface",
    ]:
        assert phrase in text

    assert "Discovery" in text
    assert "Bronze" in text
    assert "Silver" in text
    assert "Gold" in text


def test_documentation_drift_baseline_distinguishes_repository_and_runtime_evidence() -> None:
    text = read("docs/reference/governance/documentation_drift_baseline.md")

    assert "Operationally validated" in text
    assert "Fresh identified live runtime/data evidence" in text
    assert "A test pass is not live coverage/Top 5" in text


def test_readme_and_roadmap_link_current_governance() -> None:
    readme = read("README.md")
    roadmap = read("docs/planning/active/roadmap.md")

    assert "docs/reference/governance/governance_foundation.md" in readme
    assert "docs/reference/governance/documentation_drift_baseline.md" in readme
    assert "docs/current/REENTRY.md" in readme
    assert "DOC-001 Governance Foundation Gate" in roadmap
    assert "DOC-002 Documentation Drift Baseline" in roadmap
    assert "RCC execution" in roadmap
