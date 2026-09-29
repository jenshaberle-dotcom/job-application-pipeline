from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATOR = ROOT / "frontend" / "control-center" / "src" / "OperatorWorkspace.tsx"
REVIEW = ROOT / "frontend" / "control-center" / "src" / "JobReviewLabelControls.tsx"
SERVICE = ROOT / "src" / "search_intelligence" / "product_v1_service.py"
SERVER = ROOT / "scripts" / "product_v1_control_center_base.py"
LAUNCHER = ROOT / "scripts" / "run_product_v1_live_demo.py"
PROGRAM = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "Program.cs"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_all_jobs_uses_separate_affinity_preview_not_candidate_fit() -> None:
    operator = read(OPERATOR)
    review = read(REVIEW)
    service = read(SERVICE)
    server = read(SERVER)

    assert "affinity_preview_score?: number | null;" in operator
    assert "function affinityDisplayScore(job: Job)" in operator
    assert 'PD-052 Affinity preview · not ranking authority' in operator
    assert "affinityDisplayScore(job)" in operator
    assert "job.overall_quality_score" not in operator[operator.index("function affinityDisplayScore"):operator.index("function candidateFitText")]

    assert "affinity_preview_score?: number | null;" in review
    assert "PD-052 preview from the current assessment; not ranking authority." in review

    assert 'enriched["affinity_preview_score"] = row.get("affinity_preview_score")' in service
    assert '"affinity_preview_is_not_ranking_authority": True' in service
    assert "assessment.overall_quality_score AS affinity_preview_score" in server


def test_ivv_demo_connector_is_materialized_without_recurring_authority() -> None:
    launcher = read(LAUNCHER)
    server = read(SERVER)

    assert '"scripts.run_generic_origin_demo_profile"' in launcher
    assert '"--company-key",' in launcher
    assert '"ivv",' in launcher
    assert '"DEMO-GENERIC-ORIGIN-PROFILE-001"' in launcher
    assert "JAP_DEMO_CONNECTOR=READY source=generic_origin:ivv recurring=false" in launcher
    assert "_prepare_installed_demo_connectors()" in launcher

    assert "'generic_origin:' || candidate.company_key" in server
    assert "bounded/non-recurring generic-origin profile" in server


def test_local_frontend_is_generation_bound_and_never_cache_persistent() -> None:
    server = read(SERVER)
    program = read(PROGRAM)

    assert 'cache_control="no-store, max-age=0"' in server
    assert "max-age=31536000" not in server
    assert "ProductNavigationUri()" in program
    assert '"?generation="' in program
    assert '"source_sha"' in program


def test_release_version_is_1_2_4() -> None:
    assert VERSION.read_text(encoding="utf-8").strip() == "1.2.4"
