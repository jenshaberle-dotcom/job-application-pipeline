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
    assert "Apply-JAP-Control-Center-Update.ps1" in workflow


def test_local_runner_stages_latest_direct_update_instead_of_silent_install() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'EXPECTED_REPOSITORY_ID="1230805345"' in script
    assert 'EXPECTED_RUNNER="job-pipeline-runtime-linux"' in script
    assert 'UPDATE_MODE="gui_prompt_latest_direct_v1"' in script
    assert 'PENDING_SCHEMA="job_application_pipeline.windows_pending_update.v1"' in script
    assert 'policy": "latest_direct"' in script
    assert 'JAP_LOCAL_DEPLOY=STAGED' in script
    assert 'pending-update.json' in script
    assert 'desktop_archive' in script
    assert 'desktop_checksum' in script
    assert 'sha256sum "$ARCHIVE"' in script
    assert 'JAP_LOCAL_DEPLOY=APPLY' not in script


def test_local_runner_requires_release_tag_to_point_at_exact_source() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'git ls-remote "$READ_ONLY_FETCH_URL" refs/heads/main' in script
    assert 'source_not_current_main' in script
    assert 'git ls-remote "$READ_ONLY_FETCH_URL" "refs/tags/${DESKTOP_TAG}"' in script
    assert 'release_not_for_source' in script
    assert 'desktop_release_asset_unavailable' in script


def test_local_runner_bootstraps_gui_update_mode_once_and_only_when_closed() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'bootstrap_requires_closed_app' in script
    assert 'JAP_LOCAL_DEPLOY=BOOTSTRAP' in script
    assert 'bash "$ROOT/scripts/install_jap_windows_control_center.sh" --no-start' in script
    assert 'JAP_LOCAL_DEPLOY=BOOTSTRAP_PASS' in script
    assert 'bootstrap_update_mode_missing' in script
    assert 'bootstrap_compatibility_line_missing' in script


def test_local_runner_is_installed_identity_and_compatibility_fail_closed() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'installed_repository_id_mismatch' in script
    assert 'installed_repository_name_mismatch' in script
    assert 'installed_schema_mismatch' in script
    assert 'installed_compatibility_line_unsupported' in script
    assert 'compatibility_policy_mismatch' in script
    assert 'installer_schema_mismatch' in script
    assert 'snooze_contract_mismatch' in script
