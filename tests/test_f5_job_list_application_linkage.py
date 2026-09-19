from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "frontend" / "control-center" / "src" / "OperatorWorkspace.tsx"
STYLES = ROOT / "frontend" / "control-center" / "src" / "operator-workspace-v2.css"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_all_jobs_reuses_f5_effective_stage_by_silver_job_identity() -> None:
    source = _text(WORKSPACE)

    assert "application_tracking?:" in source
    assert "applicationByJobId" in source
    assert "application.silver_job_id" in source
    assert "application.effective_stage" in source
    assert '["applied", "Beworben"]' in source
    assert 'if (filter === "applied")' in source
    assert "isAppliedStage(application.effective_stage)" in source
    assert "<span>Application</span>" in source
    assert 'onOpenApplications={() => onNavigate("applications")}' in source
    assert ">Open Applications</button>" in source


def test_job_list_application_marker_uses_existing_f5_read_model_only() -> None:
    source = _text(WORKSPACE)
    styles = _text(STYLES)

    assert "applicationStageLabel" in source
    assert "ow-application-status" in source
    assert "record_operator_confirmed_submission" not in source
    assert ".ow-application-status" in styles


def test_all_jobs_accepts_exact_read_only_projected_linkage_without_persisting() -> None:
    source = _text(WORKSPACE)

    assert "job_linkage?:" in source
    assert "job_linkage?.exact_matches" in source
    assert 'linkage_status: "exact_projected"' in source
    assert "DB-Link noch nicht persistiert" in source
    assert "database_writes" in source
