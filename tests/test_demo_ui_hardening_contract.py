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
        "grid-template-columns: 74px 96px minmax(270px, 1fr) "
        "145px 96px 118px 138px"
    ) in css


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


def test_data_layers_uses_bounded_mount_wait_not_mutation_observer() -> None:
    source = (FRONTEND / "DataLayersTab.tsx").read_text(encoding="utf-8")

    assert "attempts < 80" in source
    assert "window.setTimeout(bindRoots, 50)" in source
    assert "MutationObserver" not in source


def test_application_workspace_exposes_four_files_plus_zip_download() -> None:
    source = (FRONTEND / "DemoApplicationWorkspace.tsx").read_text(encoding="utf-8")

    assert "draftFiles.length >= 4" in source
    assert 'key === "cv_docx"' in source
    assert 'key === "cv_pdf"' in source
    assert 'key === "letter_docx"' in source
    assert 'key === "letter_pdf"' in source
    assert 'key === "application_zip"' in source
    assert "Everything · ZIP" in source
    assert "downloadDraftFile" in source
