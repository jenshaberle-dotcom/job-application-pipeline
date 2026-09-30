from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OPERATOR = ROOT / "frontend" / "control-center" / "src" / "OperatorWorkspace.tsx"
REVIEW = ROOT / "frontend" / "control-center" / "src" / "JobReviewLabelControls.tsx"
SERVICE = ROOT / "src" / "search_intelligence" / "product_v1_service.py"
SERVER = ROOT / "scripts" / "product_v1_control_center_base.py"
LAUNCHER = ROOT / "scripts" / "run_jap_control_center_runtime.py"
PROGRAM = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "Program.cs"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_all_jobs_keeps_affinity_and_candidate_fit_separate() -> None:
    operator = read(OPERATOR)
    review = read(REVIEW)
    service = read(SERVICE)
    server = read(SERVER)

    assert "affinity_preview_score?: number | null;" in operator
    assert "function affinityDisplayScore(job: Job)" in operator
    assert "affinityDisplayScore(job)" in operator
    assert "candidate_fit_score?: number | null;" in operator
    assert "Candidate Fit" in operator

    assert "affinity_preview_score?: number | null;" in review
    assert "Candidate Fit" in review

    assert 'enriched["affinity_preview_score"] = row.get("affinity_preview_score")' in service
    assert '"affinity_preview_is_not_ranking_authority": True' in service
    assert "assessment.overall_quality_score AS affinity_preview_score" in server


def test_installed_runtime_has_no_demo_connector_startup_side_effect() -> None:
    launcher = read(LAUNCHER)

    assert "run_generic_origin_demo_profile" not in launcher
    assert "JAP_DEMO_CONNECTOR" not in launcher
    assert "_prepare_installed_demo_connectors" not in launcher
    assert "no_connector_activation,no_ingestion,no_auto_submit,no_send" in launcher
    assert '"assessment_cohort_policy": "bounded_current_product_truth"' in launcher


def test_local_frontend_is_generation_bound_and_never_cache_persistent() -> None:
    server = read(SERVER)
    program = read(PROGRAM)

    assert 'cache_control="no-store, max-age=0"' in server
    assert "max-age=31536000" not in server
    assert "ProductNavigationUri()" in program
    assert '"?generation="' in program
    assert '"source_sha"' in program


def test_release_version_is_semver() -> None:
    version = VERSION.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
