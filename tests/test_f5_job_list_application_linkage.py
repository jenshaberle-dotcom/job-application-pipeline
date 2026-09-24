from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "frontend" / "control-center" / "src" / "OperatorWorkspace.tsx"
TRACKING = ROOT / "frontend" / "control-center" / "src" / "F5ApplicationTracking.tsx"
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


def test_all_jobs_pending_evidence_is_not_a_warning_storm() -> None:
    source = _text(WORKSPACE)
    styles = _text(STYLES)

    assert 'return "pending"' in source
    assert 'normalized.includes("stale")' in source
    assert 'normalized.includes("required")' in source
    assert 'className="ow-gate-state"' in source
    assert ".ow-status.pending" in styles


def test_unlinked_application_status_is_explicitly_unknown_not_negative() -> None:
    source = _text(WORKSPACE)

    assert ">Ungeklärt</span>" in source
    assert "nicht gleichbedeutend mit 'nicht beworben'" in source


def test_job_application_navigation_is_internal_persistent_state_not_event_bridge() -> None:
    source = _text(WORKSPACE)

    assert "selectedJobId" in source
    assert "selectedApplicationId" in source
    assert "setSelectedApplicationId(applicationId)" in source
    assert "setSelectedJobId(silverJobId)" in source
    assert "focusApplicationId={selectedApplicationId}" in source
    assert "onOpenJob={openJob}" in source
    assert "onSelectApplication={setSelectedApplicationId}" in source
    assert "onOpenApplication={openApplication}" in source
    assert "product-v1:focus-tracked-application" not in source


def test_linkage_is_bidirectional_inside_application() -> None:
    source = _text(WORKSPACE)
    tracking = _text(TRACKING)

    assert "<F5ApplicationTracking" in source
    assert "onOpenJob?: (silverJobId: number) => void" in tracking
    assert "projectedJobByApplicationId" in tracking
    assert "application.silver_job_id ?? projectedJobByApplicationId.get" in tracking
    assert "In All jobs öffnen ↔" in tracking
    assert "onOpenJob(linkedJobId)" in tracking


def test_application_status_cell_is_a_direct_read_only_drilldown() -> None:
    source = _text(WORKSPACE)
    styles = _text(STYLES)

    assert "ow-application-status linked" in source
    assert "event.stopPropagation()" in source
    assert "Klicken, um die Bewerbung zu öffnen." in source
    assert ".ow-application-status.linked" in styles
    assert "record_operator_confirmed_submission" not in source


def test_applied_job_row_has_distinct_green_application_state() -> None:
    source = _text(WORKSPACE)
    styles = _text(STYLES)

    assert "application-active" in source
    assert '[\"applied\", \"reply\", \"interview\", \"offer\"]' in source
    assert "application-closed" in source
    assert ".ow-job-list > button.application-active" in styles
    assert ".ow-job-list > button.application-active.selected" in styles
    assert "var(--ow-green)" in styles



def test_job_detail_preserves_1_0_79_application_navigation_affordances() -> None:
    source = _text(WORKSPACE)

    assert ">Open original ↗</a>" in source
    assert "<OpenApplicationButton silverJobId={job.silver_job_id}" in source
    assert 'disabled={liveCheck.status === "checking"}' in source
    assert ">Open Applications</button>" in source
    assert "hasPersistedActiveLifecycle(job)" in source
    assert "demo_live_verified" in source


def test_progressed_application_never_offers_prepare_application_again() -> None:
    source = _text(WORKSPACE)

    assert "const canPrepareApplication" in source
    assert 'stage == null || stage === "prepared"' in source
    assert "canPrepareApplication(applicationStage)" in source
    assert "buildApplicationByJobId(payload)" in source
    assert "canPrepareApplication(applicationByJobId.get(job.silver_job_id)?.effective_stage)" in source
    assert "isAppliedStage" in source
    for stage in ("applied", "reply", "interview", "offer", "closed"):
        assert stage in source
