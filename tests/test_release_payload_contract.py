from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "jap-windows-desktop-host-release.yml"
LAUNCHER = ROOT / "scripts" / "run_product_v1_live_demo.py"
AGENT = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "ProductUpdateAgent.cs"
APPLIER = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "ProductUpdateApplier.cs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_workflow_double_proves_candidate_fit_payload() -> None:
    workflow = _read(WORKFLOW).replace("\\", "/")

    assert "JAP_RUNTIME_FEATURE_PAYLOAD_PASS1=PASS" in workflow
    assert "JAP_RUNTIME_FEATURE_PAYLOAD_PASS2=PASS" in workflow
    assert "JAP_DESKTOP_PAYLOAD_PASS2=PASS" in workflow
    assert "runtime-feature-contract.json" in workflow
    assert "job_application_pipeline.runtime_feature_contract.v1" in workflow
    assert 'candidate_fit_scope = "job_skills_vs_cv_skills"' in workflow
    assert 'demo_cohort_policy = "frozen_runtime_identity"' in workflow
    assert "candidate_fit_required_count = 10" in workflow
    assert "affinity_required_count = 10" in workflow
    assert "combined_score_authority = $false" in workflow
    assert 'static_cache_control = "no-store,max-age=0"' in workflow
    assert 'frontend_generation_binding = "source_sha"' in workflow

    for path in (
        "src/search_intelligence/product_v1_candidate_fit.py",
        "src/search_intelligence/product_v1_service.py",
        "scripts/product_v1_control_center_base.py",
        "scripts/run_product_v1_assessment_cohort.py",
        "scripts/product_v1_assessment_actions.py",
        "scripts/run_product_v1_live_demo.py",
    ):
        assert path in workflow


def test_installed_runtime_fails_closed_on_payload_contract_drift() -> None:
    launcher = _read(LAUNCHER)

    assert "REQUIRED_INSTALLED_FEATURES" in launcher
    assert '"candidate_fit_scope": "job_skills_vs_cv_skills"' in launcher
    assert '"demo_cohort_policy": "frozen_runtime_identity"' in launcher
    assert '"candidate_fit_required_count": 10' in launcher
    assert '"affinity_required_count": 10' in launcher
    assert '"combined_score_authority": False' in launcher
    assert '"static_cache_control": "no-store,max-age=0"' in launcher
    assert '"frontend_generation_binding": "source_sha"' in launcher
    assert "_verify_installed_runtime_feature_contract(frontend_dist)" in launcher
    assert "DEMO_START_BLOCKED=runtime_feature_contract:" in launcher
    assert "JAP_RUNTIME_FEATURE_CONTRACT=PASS" in launcher


def test_update_stage_and_cutover_both_verify_feature_contract() -> None:
    for path in (AGENT, APPLIER):
        source = _read(path)

        assert "VerifyRuntimeFeatureContract(stage, sourceSha, version);" in source
        assert "runtime-feature-contract.json" in source
        assert "job_application_pipeline.runtime_feature_contract.v1" in source
        assert "job_skills_vs_cv_skills" in source
        assert "frozen_runtime_identity" in source
        assert "candidate_fit_required_count" in source
        assert "affinity_required_count" in source
        assert "combined_score_authority" in source
        assert "critical_files" in source
        assert "ComputeFileSha256(candidate)" in source


def test_windows_release_is_hard_blocked_by_full_linux_validation() -> None:
    workflow = _read(WORKFLOW)

    assert "validate-release:" in workflow
    assert "name: Full Linux product validation" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m ruff check . --select E4,E7,E9,F --ignore E402" in workflow
    assert "npm run build --prefix frontend/control-center" in workflow
    assert "build-release:" in workflow
    assert "needs: validate-release" in workflow


def test_runtime_feature_contract_is_bom_safe_end_to_end() -> None:
    workflow = _read(WORKFLOW)
    launcher = _read(LAUNCHER)

    assert 'read_text(encoding="utf-8-sig")' in launcher
    assert '[System.Text.UTF8Encoding]::new($false)' in workflow
    assert 'Set-Content -Encoding UTF8 (Join-Path $Runtime "runtime-feature-contract.json")' not in workflow
