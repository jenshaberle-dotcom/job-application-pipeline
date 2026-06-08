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


def test_documentation_drift_baseline_marks_wave_search_as_unvalidated() -> None:
    text = read("docs/reference/governance/documentation_drift_baseline.md")

    assert "PDI-3" in text
    assert "Wave Search Intelligence" in text
    assert "not yet operationally proven" in text
    assert "EO-002B Candidate Reprocessing & URL Finder Validation" in text


def test_search_intelligence_current_state_contains_operational_snapshot() -> None:
    text = read("docs/reference/search-intelligence/current_state.md")

    assert "Current Operational Snapshot" in text
    assert "Market Sensors" in text
    assert "Candidate Promotion / Türsteher" in text
    assert "URL Finder" in text
    assert "Evidence Gates" in text
    assert "Built but operationally unvalidated" in text


def test_readme_and_roadmap_link_governance_and_eo002b() -> None:
    readme = read("README.md")
    roadmap = read("docs/planning/active/roadmap.md")

    assert "docs/reference/governance/governance_foundation.md" in readme
    assert "docs/reference/governance/documentation_drift_baseline.md" in readme
    assert "eo002b_candidate_reprocessing_url_finder_validation.md" in readme
    assert "DOC-001 Governance Foundation Gate" in roadmap
    assert "DOC-002 Documentation Drift Baseline" in roadmap
    assert "EO-002B Candidate Reprocessing & URL Finder Validation" in roadmap


def test_eo002b_plan_defines_guest_list_metrics_and_non_goals() -> None:
    text = read("docs/archive/planning/eo002b_candidate_reprocessing_url_finder_validation.md")

    for phrase in [
        "controlled guest-list approach",
        "Selected URL",
        "Alternative URLs",
        "Rejected URLs",
        "Confidence",
        "Gate stop",
        "A-Tier",
        "B-Tier",
        "C-Tier",
        "Hannover Rück",
    ]:
        assert phrase in text

    assert "does not" in text
    assert "rewrite the Türsteher directly" in text
