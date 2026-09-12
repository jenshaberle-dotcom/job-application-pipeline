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


def test_local_deploy_requires_rcc_reservation_before_self_hosted_execution() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert "runs-on: [self-hosted, Linux, X64, job-pipeline-runtime-linux]" in workflow
    assert 'workflows: ["JAP Windows Desktop Host release"]' in workflow
    assert 'cron: "17 * * * *"' in workflow
    assert "pull_request:" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "reservation_id:" in workflow
    assert "expected_runner:" in workflow
    assert "source_sha:" in workflow
    assert "RCC_RESERVATION_ID: ${{ inputs.reservation_id }}" in workflow
    assert "RCC_EXPECTED_RUNNER: ${{ inputs.expected_runner }}" in workflow
    assert "RCC_SOURCE_SHA: ${{ inputs.source_sha }}" in workflow
    assert "RCC_EXACT_RUNNER_HANDOFF=PASS" in workflow
    assert "RCC_EXACT_SOURCE_HANDOFF=PASS" in workflow
    assert "RCC_RESERVATION_RELEASE_REQUIRED=TRUE" in workflow
    assert "Apply-JAP-Control-Center-Update.ps1" in workflow


def test_local_deploy_proves_handoff_and_source_before_first_local_effect() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    handoff = workflow.index("Prove RCC reservation and exact runner handoff before effects")
    checkout = workflow.index("Check out exact reserved source")
    source = workflow.index("Prove exact reserved source before local effects")
    reaper = workflow.index("Reap exact stale Session-0 JAP desktop host")
    stage = workflow.index("Prove local Windows interop and stage update fail-closed")
    assert handoff < checkout < source < reaper < stage
    assert 'if [[ "$RUNNER_NAME" != "$RCC_EXPECTED_RUNNER" ]]' in workflow
    assert 'ref: ${{ inputs.source_sha }}' in workflow
    assert 'test "$actual_source" = "$RCC_SOURCE_SHA"' in workflow
    assert "always() && steps.handoff.outputs.verified == 'true'" in workflow


def test_local_runner_stages_latest_direct_update_and_auto_applies_when_closed() -> None:
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
    assert 'JAP_LOCAL_DEPLOY=AUTO_APPLY_CLOSED' in script
    assert 'JAP_LOCAL_DEPLOY=AUTO_APPLY_PASS' in script
    assert 'JAP_LOCAL_DEPLOY=AWAITING_GUI_CONSENT' in script
    assert '-HostPid 0' in script


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
