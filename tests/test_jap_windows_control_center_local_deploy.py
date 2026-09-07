from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_WRAPPER = ROOT / "scripts" / "install_jap_windows_control_center.sh"
LOCAL_DEPLOY = ROOT / "scripts" / "deploy_jap_windows_control_center_local.sh"
LOCAL_DEPLOY_WORKFLOW = (
    ROOT / ".github" / "workflows" / "jap-windows-control-center-local-deploy.yml"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_install_wrapper_supports_noninteractive_no_start_mode() -> None:
    text = _text(INSTALL_WRAPPER)
    assert "--no-start" in text
    assert "args+=(-NoStart)" in text
    assert "--no-shortcuts" in text
    assert "unknown_argument" in text


def test_local_deploy_is_bound_to_the_existing_jap_warm_runner() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert "runs-on: [self-hosted, Linux, X64, job-pipeline-runtime-linux]" in workflow
    assert 'workflows: ["JAP Windows Desktop Host release"]' in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert 'cron: "17 * * * *"' in workflow
    assert "pull_request:" not in workflow
    assert "cancel-in-progress: false" in workflow


def test_local_deploy_reuses_the_verified_installer_and_never_starts_the_app() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'EXPECTED_REPOSITORY_ID="1230805345"' in script
    assert 'EXPECTED_RUNNER="job-pipeline-runtime-linux"' in script
    assert 'JAP_LOCAL_DEPLOY=BLOCKED' in script
    assert 'JAP_LOCAL_DEPLOY=DEFERRED' in script
    assert 'desktop_host_running' in script
    assert 'desktop_release_unavailable' in script
    assert 'bash "$ROOT/scripts/install_jap_windows_control_center.sh" --no-start' in script
    assert 'JAP_LOCAL_DEPLOY=PASS' in script


def test_local_deploy_is_exact_main_and_installed_identity_fail_closed() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'git ls-remote "$READ_ONLY_FETCH_URL" refs/heads/main' in script
    assert 'source_not_current_main' in script
    assert 'installed_repository_id_mismatch' in script
    assert 'installed_repository_name_mismatch' in script
    assert 'deployed_main_sha_mismatch' in script
    assert 'deployed_desktop_version_mismatch' in script
