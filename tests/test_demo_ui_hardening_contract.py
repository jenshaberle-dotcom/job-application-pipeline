from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "control-center" / "src"


def test_job_review_distinguishes_preliminary_affinity_product_score_and_profile_fit() -> None:
    source = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert "Role affinity · preliminary" in source
    assert "Detail check required" in source
    assert "authoritative Product score" in source
    assert "Profile Fit coverage" in source
    assert "Profile Fit decision" in source
    assert "authoritative profile fit" not in source
    assert "Affinity" in source


def test_every_job_table_heading_is_a_sort_control_and_gate_stays_in_grid() -> None:
    source = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")
    css = (FRONTEND / "operator-demo-hardening.css").read_text(encoding="utf-8")

    for column in ("fit", "review", "job", "location", "published", "observed", "gate"):
        assert f'sortHeader("{column}"' in source
    assert (
        "grid-template-columns: 62px 88px minmax(240px, 1fr) "
        "128px 90px 116px 124px 98px"
    ) in css
    assert "<span>Application</span>" in source


def test_ba_internal_reference_is_never_opened_as_browser_scheme() -> None:
    source = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert 'raw.startsWith("ba://")' in source
    assert "https://www.arbeitsagentur.de/jobsuche/jobdetail/" in source
    assert "href={job.source_url}" not in source


def test_sources_separate_delivery_zero_yield_sensors_and_attention() -> None:
    source = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    for group in (
        "Needs attention",
        "Delivering now",
        "Active, 0 current jobs",
        "Market sensors",
        "Pending",
        "Not implemented",
    ):
        assert group in source
    for summary in (
        "Employer origins",
        "active_last_run_loaded_count",
        "active_last_run_zero_count",
        "sensor_count",
        "attention_count",
    ):
        assert summary in source
    assert "source.source_role" in source
    assert "Latest run" in source
    assert "Latest load" in source
    assert "ow-source-summary-strip" in source
    assert "ow-source-group-title" in source


def test_data_layers_waits_for_workspace_with_mutation_observer() -> None:
    source = (FRONTEND / "DataLayersTab.tsx").read_text(encoding="utf-8")

    assert "new MutationObserver(" in source
    assert "observer.observe(document.body, { childList: true, subtree: true })" in source
    assert "observer?.disconnect()" in source
    assert "attempts < 80" not in source
    assert "window.setTimeout(bindRoots, 50)" not in source


def test_application_workspace_is_f6_template_authoritative_and_has_no_legacy_download_renderer() -> None:
    source = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "F6 template authority" in source
    assert "Legacy generic DOCX/A4 export has been removed" in source
    assert "template_bound_renderer_pending" not in source
    assert "downloadDraftFile" not in source
    assert 'key === "cv_docx"' not in source
    assert 'key === "application_zip"' not in source
    assert "application-package-downloads.css" not in source



def test_f6_c_review_surface_edits_only_declared_zones_and_exports_locally() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    editor = (FRONTEND / "F6TemplateReviewEditor.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "f6-template-review-editor.css").read_text(encoding="utf-8")

    assert 'import F6TemplateReviewEditor from "./F6TemplateReviewEditor";' in workspace
    assert "<F6TemplateReviewEditor" in workspace
    assert "source_manifest_sha256" in workspace
    assert "/api/v1/product-v1/f6-template-review" in editor
    assert "/api/v1/product-v1/f6-template-export" in editor
    assert "render_f6_review_package" in editor
    assert "One finished PDF instead of zone-by-zone assembly" in editor
    assert "Create finished application PDF" in editor
    assert "The generated review text has already been mapped" in editor
    assert "Open final PDF" in editor
    assert "Download final PDF" in editor
    assert "visual identity verified" in editor
    assert "Advanced: adjust individual template text zones" in editor
    assert "HUMAN REVIEW REQUIRED" in editor
    assert "No DB write, provider call, application action, submission, or send" in editor
    assert "download={packagePdf.download_filename}" in editor
    assert "application-package-downloads.css" not in workspace + editor + styles



def test_application_drafting_separates_top5_recommendation_from_operator_selection() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert "applicationJobs" in workspace
    assert "productTruth?.job_readiness" in workspace
    assert 'job.lifecycle_status === "active_confirmed"' in workspace
    assert 'job.demo_live_verified === true' not in workspace
    assert 'job.origin_validation_status === "validated"' not in workspace
    assert 'job.hard_filter_status !== "failed"' in workspace
    assert "Operator-selected current job" in workspace
    assert "Selected Top-5 recommendation" in workspace
    assert "Operator-selected current job" in workspace
    assert 'detail?.silverJobId' in workspace
    assert "The job you selected stays the application target" in workspace
    assert 'aria-label="Change application target"' in workspace
    assert 'aria-label="Search application target jobs"' in workspace
    assert "Showing the 10 highest-Affinity selectable jobs" in workspace

    assert "silverJobId?: number" in operator
    assert '{ detail: silverJobId ? { silverJobId } : {} }' in operator
    assert 'hasPersistedActiveLifecycle(job) && job.hard_filter_status !== "failed"' in operator
    assert "Explicit current-job selection" in operator
    assert "Ready for review drafting" in operator
    assert "rankable && <OpenApplicationButton" not in operator



def test_f6_navigation_uses_exact_live_revalidation_not_arbitrary_age() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")
    backend = (ROOT / "scripts" / "product_v1_application_workspace_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "hasPersistedActiveLifecycle(job)" in operator
    assert "<OpenApplicationButton silverJobId={job.silver_job_id}" in operator
    assert 'disabled={liveCheck.status === "checking"}' in operator
    assert 'job.demo_live_verified === true' not in workspace
    assert "revalidate_selected_vacancy(" in backend
    assert "evaluate_demo_live_scope(" not in backend
    assert "current vacancy is no longer available" in backend
    assert "current vacancy could not be verified" in backend


def test_f6_live_revalidation_is_explicit_post_not_workspace_get_side_effect() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    runtime = (ROOT / "scripts" / "product_v1_application_workspace_runtime.py").read_text(
        encoding="utf-8"
    )
    server = (ROOT / "scripts" / "run_product_v1_demo_control_center.py").read_text(
        encoding="utf-8"
    )
    quality = (
        ROOT / "scripts" / "product_v1_application_workspace_runtime_quality.py"
    ).read_text(encoding="utf-8")

    assert '"/api/v1/product-v1/application-workspace/revalidate"' in workspace
    assert 'action: "revalidate_selected_vacancy"' in workspace
    assert 'method: "POST"' in workspace
    assert "APPLICATION_WORKSPACE_REVALIDATE_PATH" in server
    assert "parse_application_revalidation_action_payload" in server
    assert "def revalidate_application_target(" in runtime
    assert "def require_live_application_target(" in runtime

    load_section = runtime.split("def load_application_workspace(", 1)[1].split(
        "def application_workspace_payload(", 1
    )[0]
    assert "revalidate_selected_vacancy(" not in load_section
    assert "require_live_application_target(silver_job_id)" in quality


def test_selected_job_is_exact_live_revalidated_and_closed_truth_refreshes_ui() -> None:
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert '"/api/v1/product-v1/application-workspace/revalidate"' in operator
    assert 'action: "revalidate_selected_vacancy"' in operator
    assert 'method: "POST"' in operator
    assert 'if (status === "closed")' in operator
    assert "await refresh().catch(() => undefined)" in operator
    assert "Live availability" in operator


def test_all_jobs_is_the_current_employer_origin_review_scope() -> None:
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert '["all", "All jobs"]' in operator
    assert '["current", "Current"]' not in operator
    assert "jobs: payload.job_readiness.length" in operator
    assert "Current employer-origin vacancies only." in operator
    assert '"All current"' not in operator


def test_application_workspace_separates_live_vacancy_from_employer_origin_authority() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "Live vacancy verified" in workspace
    assert "Employer-Origin authority" in workspace
    assert "Employer-origin verified" not in workspace
    assert "workspace?.workspace?.target?.employer_origin_authorized === true" in workspace


def test_chatgpt_connection_can_start_before_other_context_blockers_clear() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "{!codexReady && <div className=\"demo-blockers\">" in workspace
    assert "generationReady && !codexReady" not in workspace
    assert "Connect ChatGPT" in workspace


def test_completed_chatgpt_login_reconciles_runtime_status_in_separate_effect() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert 'if (codexLogin?.status !== "completed") return;' in workspace
    assert 'if (payload.status === "completed") {' not in workspace
    assert workspace.count(
        'readJson<CodexStatusPayload>("/api/v1/product-v1/codex-status")'
    ) >= 2


def test_application_workspace_excludes_jobs_already_applied_or_further_progressed() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert 'type ApplicationStage = "prepared" | "applied" | "reply" | "interview" | "offer" | "closed"' in workspace
    assert "applicationStageByJobId" in workspace
    assert "canPrepareApplication" in workspace
    assert 'return stage == null || stage === "prepared"' in workspace
    assert "canPrepareApplication(applicationStages.get(job.silver_job_id))" in workspace
    assert "const requestedJob = requestedId > 0" in workspace
    assert "setSelectedId(requestedJob.silver_job_id)" in workspace
    assert "|| applicationJobs[0] || null" not in workspace

    assert "canPrepareApplication(applicationStage)" in operator
    assert "buildApplicationByJobId" in operator
    assert "canPrepareApplication(applicationByJobId.get(job.silver_job_id)?.effective_stage)" in operator



def test_application_workspace_exact_target_has_single_event_owner_and_no_long_sidebar() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    main = (FRONTEND / "main.tsx").read_text(encoding="utf-8")
    css = (FRONTEND / "demo-application-workspace.css").read_text(encoding="utf-8")
    finish_css = (FRONTEND / "product-finish-ux.css").read_text(encoding="utf-8")

    assert 'window.addEventListener("product-v1:open-application-workspace", openRequestedTarget)' in workspace
    assert "setSelectedId(requestedJob.silver_job_id)" in workspace
    assert "selectedJob = useMemo" in workspace
    assert "|| applicationJobs[0]" not in workspace
    assert "Change job" in workspace
    assert "chooserJobs" in workspace
    assert "slice(0, 10)" in workspace
    assert "demo-job-chooser" in workspace
    assert "demo-job-sidebar" not in workspace
    assert "demo-application-launcher" not in workspace
    assert "ApplicationWorkspaceEventBridge" not in main
    assert "demo-application-launcher" not in css
    assert "ApplicationWorkspaceEventBridge" not in finish_css



def test_active_application_workspace_has_product_identity_not_demo001_branding() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    main = (FRONTEND / "main.tsx").read_text(encoding="utf-8")

    assert "DEMO-001" not in workspace
    assert "DemoApplicationWorkspace" not in workspace
    assert "PRODUCT V1 · APPLICATION" in workspace
    assert 'aria-label="Application preparation journey"' in workspace
    assert 'import ApplicationWorkspace from "./ApplicationWorkspace";' in main
    assert "<ApplicationWorkspace />" in main
    assert "DemoApplicationWorkspace" not in main
