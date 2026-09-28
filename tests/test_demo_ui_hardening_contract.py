from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "control-center" / "src"


def test_job_review_distinguishes_preliminary_affinity_product_score_and_profile_fit() -> None:
    source = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert "<h3>Affinity</h3>" in source
    assert "Affinity is not authoritative yet. Candidate Fit is evaluated separately above." in source
    assert "Affinity ranking score" in source
    assert "Candidate fit" in source
    assert "Fit evidence" in source
    assert "skills evidence" in source
    assert "requirements evidence" in source
    assert "More fit evidence needed" in source
    assert "authoritative profile fit" not in source
    assert "Affinity" in source


def test_top5_keeps_candidate_fit_separate_from_affinity() -> None:
    source = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")
    css = (FRONTEND / "operator-workspace-v2.css").read_text(encoding="utf-8")

    assert "Only current jobs with verified Candidate Fit and ranking evidence appear here." in source
    assert "Affinity stays visible as a separate preference signal." in source
    assert '<span className="ow-top5-fit">{candidateFitText(job)}</span>' in source
    assert '<span className="ow-top5-affinity"><small>Affinity</small>' in source
    assert "after Candidate Fit and the normal ranking gates are verified" in source
    assert ".ow-top5-fit" in css
    assert ".ow-top5-affinity" in css
    assert 'fetch("/api/v1/product-v1/assessment-cohort"' in source
    assert 'action: "refresh_candidate_fit_and_top5"' in source
    assert 'confirmation: "evaluate_current_jobs"' in source
    assert "Evaluate current jobs" in source
    assert "Candidate Fit &amp; Top 5" in source
    assert "fit_blocker_counts?: Record<string, number>" in source
    assert "Missing fit evidence —" in source
    assert "fitFactorLabel[factor]" in source
    assert ".ow-top5-header-actions" in css


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
        "Employer sources",
        "active_last_run_loaded_count",
        "active_last_run_zero_count",
        "sensor_count",
        "attention_count",
    ):
        assert summary in source
    assert "source.source_role" in source
    assert "Last check" in source
    assert "Jobs found" in source
    assert "Market discovery" in source
    assert "Not connected" in source
    assert "ow-source-summary-strip" in source
    assert "ow-source-group-title" in source
    assert "jobs on last check" in source
    assert "ow-source-row-state" in source
    assert "<small>{source.source_name}</small>" not in source
    assert "No action needed" in source


def test_data_layers_waits_for_workspace_with_mutation_observer() -> None:
    source = (FRONTEND / "DataLayersTab.tsx").read_text(encoding="utf-8")

    assert "new MutationObserver(" in source
    assert "observer.observe(document.body, { childList: true, subtree: true })" in source
    assert "observer?.disconnect()" in source
    assert "attempts < 80" not in source
    assert "window.setTimeout(bindRoots, 50)" not in source


def test_application_workspace_keeps_verified_template_semantics_without_internal_ui_jargon() -> None:
    source = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "template_authority?:" in source
    assert "JAP keeps the PDF layout fixed" in source
    assert "Drafting used the current CV, current cover letter and exact vacancy together." in source
    assert "Document templates" in source
    assert "Document generation is review-first." in source
    assert "F6 template authority" not in source
    assert "PDF remains exact template authority" not in source
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
    assert "Template text needs adjustment" in editor
    assert "disabled={rendering || Boolean(error)}" in editor
    assert "setError(null);" in editor
    assert "The generated review text has already been mapped" in editor
    assert "Open final PDF" in editor
    assert "Download final PDF" in editor
    assert "Download editable Word" in editor
    assert "PDF is the verified layout authority" in editor
    assert "visual identity verified" in editor
    assert "Advanced: manual override (normally not required)" in editor
    assert "exact-template preflighted" in editor
    assert "HUMAN REVIEW REQUIRED" in editor
    assert "No DB write, provider call, application action, submission, or send" in editor
    assert "download={packagePdf.download_filename}" in editor
    assert "application-package-downloads.css" not in workspace + editor + styles
    assert "/api/v1/product-v1/f6-template-export-progress?request_id=" in editor
    assert "request_id: requestId" in editor
    assert "Your application files are being created" in editor
    assert "Local processing · no provider request" in editor
    assert "Progress is based on completed file-generation steps" in editor
    assert ".f6-export-progress-track" in styles



def test_application_drafting_separates_top5_recommendation_from_operator_selection() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert "applicationJobs" in workspace
    assert "productTruth?.job_readiness" in workspace
    assert 'job.lifecycle_status === "active_confirmed"' in workspace
    assert 'job.demo_live_verified === true' not in workspace
    assert 'job.origin_validation_status === "validated"' not in workspace
    assert 'job.hard_filter_status !== "failed"' in workspace
    assert "Selected current job" in workspace
    assert "Selected Top-5 recommendation" in workspace
    assert "Selected current job" in workspace
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

    assert '["all", "All Jobs"]' in operator
    assert '["current", "Current"]' not in operator
    assert "jobs: payload.job_readiness.length" in operator
    assert "Current employer-origin vacancies only." in operator
    assert '"All current"' not in operator


def test_application_workspace_separates_live_vacancy_from_employer_origin_authority() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "Live vacancy verified" in workspace
    assert "Employer source" in workspace
    assert "Verification required" in workspace
    assert "Employer-Origin authority" not in workspace
    assert "Employer-origin verified" not in workspace
    assert "workspace?.workspace?.target?.employer_origin_authorized === true" in workspace


def test_chatgpt_connection_can_start_before_other_context_blockers_clear() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "{codexRequired && !codexReady && <div className=\"demo-blockers\">" in workspace
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
    assert "Application Builder" in workspace
    assert "PRODUCT V1 · APPLICATION" not in workspace
    assert 'aria-label="Application preparation journey"' in workspace
    assert 'import ApplicationWorkspace from "./ApplicationWorkspace";' in main
    assert "<ApplicationWorkspace />" in main
    assert "DemoApplicationWorkspace" not in main



def test_application_workspace_has_explicit_llm_privacy_choice() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert 'type GenerationMode = "codex_quality" | "local_private"' in workspace
    assert "Quality AI — share current CV + current letter + vacancy" in workspace
    assert "Local only — send no CV, letter or vacancy text to an LLM" in workspace
    assert 'generation_mode: generationMode' in workspace
    assert "Prepare locally without LLM" in workspace
    assert 'manualEditingRequired={draft.draft_mode === "local_private_edit"}' in workspace


def test_no_upload_path_offers_provider_free_fillable_word_starter() -> None:
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert "/api/v1/product-v1/application-starter-template" in operator
    assert "Download fillable Word starter" in operator
    assert "sends nothing to an AI provider" in operator
    assert "local fillable Word starter" in operator



def test_application_workspace_shows_live_quality_drafting_progress() -> None:
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "demo-application-workspace.css").read_text(encoding="utf-8")

    assert "/api/v1/product-v1/application-draft-progress?request_id=" in workspace
    assert "request_id: requestId" in workspace
    assert "Your application documents are being created" in workspace
    assert "AI drafting pass" in workspace
    assert "AI drafting ready" in workspace
    assert "Elapsed {draftElapsedLabel}" in workspace
    assert "Progress is based on completed JAP steps" in workspace
    assert "Content checks:" in workspace
    assert 'role="progressbar"' in workspace
    assert ".demo-drafting-progress-track" in styles


def test_portal_tabs_keep_operator_topline_identity_in_sync() -> None:
    data_layers = (FRONTEND / "DataLayersTab.tsx").read_text(encoding="utf-8")
    data_css = (FRONTEND / "data-layers-tab.css").read_text(encoding="utf-8")

    assert 'document.querySelector<HTMLElement>(".ow-topline > div")' in data_layers
    assert '<b className="ow-overlay-topline-title">Data Layers</b>' in data_layers
    assert "body.data-layers-active .ow-topline > div > b:not(.ow-overlay-topline-title)" in data_css
    assert "body.data-layers-active .ow-overlay-topline-title" in data_css


def test_application_tracking_uses_product_copy_and_avoids_duplicate_expanded_stage_badge() -> None:
    source = (FRONTEND / "F5ApplicationTracking.tsx").read_text(encoding="utf-8")

    assert "Application lifecycle · mailbox-assisted" in source
    assert "<h2>Application Tracker</h2>" in source
    assert "F5 · Mailbox Application Tracking" not in source

    expanded = source.split('{expanded && <div className="f5-expanded-body">', 1)[1]
    card_head = expanded.split("<StageStrip", 1)[0]
    assert "f5-stage-badge" not in card_head
    assert "<StageStrip stage={application.effective_stage} />" in expanded



def test_primary_navigation_distinguishes_building_from_tracking_applications() -> None:
    source = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")

    assert '{ id: "application", label: "Application Builder"' in source
    assert '{ id: "applications", label: "Application Tracker"' in source
    nav = source.split("const navItems:", 1)[1].split("];", 1)[0]
    assert 'label: "Application"' not in nav
    assert 'label: "Applications"' not in nav
    assert 'label: "Approvals"' not in nav
    assert 'view === "approvals"' not in source


def test_control_center_user_facing_copy_stays_english() -> None:
    files = sorted(FRONTEND.glob("*.tsx"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    combined = combined.replace("Hornetsecurity_Jens_Haberle_Lebenslauf.pdf", "")
    combined = combined.replace("Hornetsecurity_Jens_Haberle_Anschreiben.pdf", "")

    forbidden = (
        "Bewerbung",
        "Bewerbungen",
        "Bewerbungs",
        "Arbeitgeber",
        "Beworben",
        "Erkannt",
        "Antwort",
        "Angebot",
        "Geschlossen",
        "Prüfen",
        "Fehleintrag",
        "Manuell erfassen",
        "Öffnen",
        "Ungeklärt",
        "Fortschritt basiert",
        "Deine Bewerbungs",
        "Lokale Verarbeitung",
        "Mailbox-Sync nicht aktuell",
    )
    for token in forbidden:
        assert token not in combined, token



def test_demo_user_language_hides_internal_readiness_and_template_terms() -> None:
    operator = (FRONTEND / "OperatorWorkspace.tsx").read_text(encoding="utf-8")
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    tracker = (FRONTEND / "F5ApplicationTracking.tsx").read_text(encoding="utf-8")
    data_layers = (FRONTEND / "DataLayersTab.tsx").read_text(encoding="utf-8")

    assert 'sortHeader("gate", "Candidate Fit")' in operator
    assert "Ready for Top 5" in operator
    assert "Requirements evidence needed" in operator
    assert "Top 5 readiness" in operator
    assert "Affinity ranking score" in operator
    assert "CV source" in operator
    assert "Cover letter source" in operator
    assert "Review-first · no automatic applications" in operator
    assert "Loading current job data…" in operator
    assert "Search setup" in operator
    assert "This source is currently ready to use." in operator
    assert "Search profiles" not in operator
    assert "Only current jobs with verified Candidate Fit and ranking evidence appear here." in operator
    assert "Ready to rank" in operator
    assert "Shown in All Jobs" in operator

    visible_forbidden = (
        "Authoritative Product score",
        "Canonical CV",
        "Canonical letter",
        "Exact authority",
        "Product V1 · review-first",
        "Reading Product V1 truth",
        "Only authoritative rankable jobs",
        "Runtime truth",
        "Review scope current",
    )
    for token in visible_forbidden:
        assert token not in operator

    assert "Employer source" in workspace
    assert "Profile evidence" in workspace
    assert "Source documents" in workspace
    assert "Document templates" in workspace
    assert "Document generation is review-first." in workspace
    assert "Application Builder" in workspace
    assert "AI drafting pass" in workspace
    assert "Content checks:" in workspace
    for token in (
        "Employer-Origin authority",
        "Candidate facts",
        "F6 templates",
        "F6 template authority",
        "F6 is review-first",
        "Operator-selected current job",
        "Provider request",
        "Semantic repairs:",
        "DB writes:",
    ):
        assert token not in workspace

    assert "Silver #{linkedJobId}" not in tracker
    assert "Job #{linkedJobId}" in tracker
    assert "Loading current job data layers…" in data_layers
    assert "Latest job assessment" in data_layers
    assert "completed job assessment" in data_layers
    assert "Product assessment" not in data_layers
    assert "ranking gates" not in data_layers
