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
        "Needs attention",
        "Delivering jobs",
        "Active · no jobs",
        "Market discovery",
        "Setup pending",
        "Not connected",
    ):
        assert label in workspace
    assert '"Coverage targets"' not in workspace
    assert "Market discovery runtime mismatch" in workspace
    assert "pipeline.source_connector_overview.v5" in workspace
    assert "verified_discovery_evidence_count" in workspace
    assert ".ow-source-tabs button.active" in css
    assert ".ow-source-group-title" in css


def test_linked_active_application_marks_full_job_row_green() -> None:
    workspace = _text(WORKSPACE)
    css = _text(CSS)

    assert '["applied", "reply", "interview", "offer"].includes(linkedApplication.effective_stage)' in workspace
    assert 'applicationActive ? "application-active" : ""' in workspace
    assert ".ow-job-list > button.application-active" in css
    assert "var(--ow-green)" in css


def test_demo_warnings_have_visible_remediation_paths() -> None:
    workspace = _text(WORKSPACE)
    data_layers = (
        ROOT / "frontend" / "control-center" / "src" / "DataLayersTab.tsx"
    ).read_text(encoding="utf-8")

    assert "Review tracker →" in workspace
    assert "Review current jobs blocking the shortlist →" in workspace
    assert '"needs_assessment"' in workspace
    assert "Review jobs needing assessment →" in data_layers
    assert 'new CustomEvent("jap:navigate"' in data_layers
