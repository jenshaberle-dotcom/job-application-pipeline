from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "control-center" / "src" / "App.tsx"
STYLES = ROOT / "frontend" / "control-center" / "src" / "styles.css"


def test_control_center_uses_four_job_first_operator_surfaces() -> None:
    app = APP.read_text(encoding="utf-8")

    assert 'type Tab = "jobs" | "sources" | "approvals" | "operations";' in app
    assert '["jobs", "Jobs"]' in app
    assert '["sources", "Sources"]' in app
    assert '["approvals", "Approvals"]' in app
    assert '["operations", "Operations"]' in app

    # One primary navigation only: the redundant left icon rail is retired.
    assert "icon-rail" not in app
    assert "Quick navigation" not in app


def test_job_surface_exposes_current_jobs_fit_top5_and_source_links_without_fake_cv_match() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "Current active" in app
    assert "Authoritative Top 5" in app
    assert "What should I apply to now?" in app
    assert "job.source_url" in app
    assert "Open original job" in app
    assert "Profile-fit signals" in app
    assert "Profile fit ≠ CV match" in app
    assert "CV-match metric" in app
    assert "Not available" in app
    assert "The UI will not manufacture a shortlist" in app


def test_source_surface_separates_blocker_type_next_action_and_truth_layers() -> None:
    app = APP.read_text(encoding="utf-8")

    for kind in ("TECH", "APPROVAL", "CONFIG", "OBSERVABILITY", "OPERATION"):
        assert kind in app
    assert "Where does it stick?" in app
    assert "Next safe action" in app
    assert "Evidence observed" in app
    assert "Verified truth" in app
    assert "Uncertainty / hypothesis" in app
    assert "Never promoted to truth" in app
    assert "Evidence may support a decision; it never grants authority by itself." in app

    for stage in (
        "Implemented",
        "Validated",
        "Approved",
        "Registered",
        "Activated",
        "Ingested",
    ):
        assert stage in app


def test_approval_surface_counts_only_real_approval_work() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "finalApprovalCount" in app
    assert 'source.current_blocker === "final_approval_incomplete"' in app
    assert "Only actual approval gates appear here" in app
    assert "Technical blockers stay in Sources" in app
    assert "The previous 63-count mixed technical blockers with approval work" in app


def test_control_center_does_not_add_new_mutation_authority() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "onReviewFinalApproval" in app
    assert 'method: "POST"' not in app
    assert "/api/v1/source-connectors/final-approval" not in app

    forbidden_action_names = (
        "approveBuild",
        "activateSource",
        "registerConnector",
        "runIngestion",
        "providerCall",
        "rankingMutation",
        "applicationAction",
    )
    for action_name in forbidden_action_names:
        assert action_name not in app


def test_control_center_styles_expand_real_operator_workspace() -> None:
    styles = STYLES.read_text(encoding="utf-8")

    for selector in (
        ".topbar",
        ".jobs-workspace",
        ".jobs-table",
        ".source-workspace",
        ".approval-focus-grid",
        ".operations-grid",
        ".pipeline-map",
        ".score-breakdown",
    ):
        assert selector in styles

    assert ".icon-rail" not in styles
    for token in ("--cyan:", "--green:", "--amber:", "--violet:", "--danger:"):
        assert token in styles
