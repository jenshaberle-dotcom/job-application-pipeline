from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "control-center" / "src" / "App.tsx"
STYLES = ROOT / "frontend" / "control-center" / "src" / "styles.css"


def test_control_center_uses_four_operator_first_surfaces() -> None:
    app = APP.read_text(encoding="utf-8")

    assert 'type Tab = "overview" | "candidates" | "approvals" | "operations";' in app
    assert '["overview", "Overview"]' in app
    assert '["candidates", "Candidates"]' in app
    assert '["approvals", "Approvals"]' in app
    assert '["operations", "Operations"]' in app

    # The previous implementation surfaces must not return as primary navigation.
    assert '["sources", "Sources & Connectors"]' not in app
    assert '["waves", "StepStone Waves"]' not in app
    assert '["top-jobs", "Top 5"]' not in app
    assert '["applications", "Applications"]' not in app


def test_control_center_keeps_evidence_truth_uncertainty_and_next_action_separate() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "Evidence observed" in app
    assert "Verified truth" in app
    assert "Uncertainty / hypothesis" in app
    assert "Never promoted to truth" in app
    assert "Next safe action" in app
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


def test_control_center_does_not_fake_unprojected_metrics_or_new_actions() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "It does not invent unprojected candidate stages." in app
    assert "without invented telemetry" in app
    assert 'source.current_blocker === "final_approval_incomplete"' in app
    assert "onReviewFinalApproval" in app

    # App itself is presentation/readmodel orchestration only. The one reviewed
    # final-approval POST remains isolated in FinalApprovalReviewDialog.
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


def test_control_center_styles_cover_target_operator_layouts() -> None:
    styles = STYLES.read_text(encoding="utf-8")

    for selector in (
        ".topbar",
        ".candidate-workspace",
        ".approval-layout",
        ".operations-grid",
        ".truth-model-grid",
        ".pipeline-map",
        ".next-safe-card",
    ):
        assert selector in styles

    for token in ("--cyan:", "--green:", "--amber:", "--violet:", "--danger:"):
        assert token in styles
