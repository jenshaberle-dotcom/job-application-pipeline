from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "frontend" / "control-center" / "src" / "OperatorWorkspace.tsx"
CSS = ROOT / "frontend" / "control-center" / "src" / "operator-workspace-v2.css"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sources_inventory_is_clustered_into_counted_tabs() -> None:
    workspace = _text(WORKSPACE)
    css = _text(CSS)

    assert 'type SourceTab = "All" | SourceGroup;' in workspace
    assert 'className="ow-source-tabs"' in workspace
    assert 'aria-label="Source groups"' in workspace
    for label in (
        "Attention",
        "Delivering",
        "Active · 0 jobs",
        "Sensors",
        "Pending",
        "Not implemented",
    ):
        assert label in workspace
    assert ".ow-source-tabs button.active" in css
    assert ".ow-source-group-title" in css


def test_linked_active_application_marks_full_job_row_green() -> None:
    workspace = _text(WORKSPACE)
    css = _text(CSS)

    assert '["applied", "reply", "interview", "offer"].includes(linkedApplication.effective_stage)' in workspace
    assert 'applicationActive ? "application-active" : ""' in workspace
    assert ".ow-job-list > button.application-active" in css
    assert "var(--ow-green)" in css
