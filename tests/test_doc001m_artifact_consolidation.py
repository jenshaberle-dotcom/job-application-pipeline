from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def line_count(path: str) -> int:
    return len(read(path).splitlines())


def test_doc001m_current_truth_and_active_planning_stay_lean() -> None:
    assert line_count("README.md") <= 105
    assert line_count("docs/current/architecture.md") <= 120
    assert line_count("docs/planning/active/roadmap.md") <= 90


def test_doc001m_runbook_uses_single_canonical_workflow_source() -> None:
    runbook = read("docs/guides/operator-runbook.md")
    workflow = read("docs/guides/development-workflow.md")

    assert "development-workflow.md" in runbook
    assert "PR_NUMBER=\"$(gh pr view --json number --jq '.number')\"" in workflow
    assert "gh pr merge --squash --delete-branch" not in runbook
    assert "manual `<PR_NUMBER>` replacement" in runbook


def test_doc001m_root_readme_keeps_planning_and_archive_separate() -> None:
    text = read("README.md")

    assert "| `docs/planning/` | Active planning only. |" in text
    assert "| `docs/archive/` | Historical documentation and replaced artifacts. |" in text
    assert "| `docs/archive/planning/` | Active planning only." not in text


def test_doc001m_reference_navigation_lists_existing_reference_areas_only() -> None:
    text = read("docs/reference/README.md")

    assert "- `database/`" in text
    assert "- `search-intelligence/`" in text
    assert "- `architecture/`" not in text
