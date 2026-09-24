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
    source = (FRONTEND / "DemoApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "F6 template authority" in source
    assert "Legacy generic DOCX/A4 export has been removed" in source
    assert "template_bound_renderer_pending" not in source
    assert "downloadDraftFile" not in source
    assert 'key === "cv_docx"' not in source
    assert 'key === "application_zip"' not in source
    assert "application-package-downloads.css" not in source



def test_f6_c_review_surface_edits_only_declared_zones_and_exports_locally() -> None:
    workspace = (FRONTEND / "DemoApplicationWorkspace.tsx").read_text(encoding="utf-8")
    editor = (FRONTEND / "F6TemplateReviewEditor.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "f6-template-review-editor.css").read_text(encoding="utf-8")

    assert 'import F6TemplateReviewEditor from "./F6TemplateReviewEditor";' in workspace
    assert "<F6TemplateReviewEditor" in workspace
    assert "source_manifest_sha256" in workspace
    assert "/api/v1/product-v1/f6-template-review" in editor
    assert "/api/v1/product-v1/f6-template-export" in editor
    assert "render_f6_review_package" in editor
    assert "Apply draft suggestions to zones" in editor
    assert "Render local PDFs" in editor
    assert "Outside-zone identity PASS" in editor
    assert "HUMAN REVIEW REQUIRED" in editor
    assert "No automatic submit/send authority" in editor
    assert "download={item.download_filename}" in editor
    assert "application-package-downloads.css" not in workspace + editor + styles
