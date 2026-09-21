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


def test_local_deploy_preserves_automatic_compatibility_path_until_rcc_cutover() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert "runs-on: [self-hosted, Linux, X64, job-pipeline-runtime-linux]" in workflow
    assert 'workflows: ["JAP Windows Desktop Host release"]' in workflow
    assert 'cron: "17 * * * *"' in workflow
    assert "pull_request:" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert "github.event_name != 'workflow_run'" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "Resolve exact released deploy source" in workflow
    assert "getLatestRelease" in workflow
    assert "release_workflow_run" in workflow
    assert "latest_published_release" in workflow
    assert "JAP_LOCAL_DEPLOY_ADMISSION=BLUE_FACADE" in workflow
    assert "JAP_LOCAL_DEPLOY_RCC_CUTOVER_PENDING=FALSE" in workflow


def test_reserved_dispatch_keeps_exact_rcc_handoff_contract() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert "reservation_id:" in workflow
    assert "expected_runner:" in workflow
    assert "default: rcc-general-linux-01--jap" in workflow
    assert "source_sha:" in workflow
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "RCC_RESERVATION_ID: ${{ inputs.reservation_id }}" in workflow
    assert "RCC_EXPECTED_RUNNER: ${{ inputs.expected_runner }}" in workflow
    assert "RCC_SOURCE_SHA: ${{ inputs.source_sha }}" in workflow
    assert "RCC_EXACT_RUNNER_HANDOFF=PASS" in workflow
    assert 'if [[ "$RUNNER_NAME" != "$RCC_EXPECTED_RUNNER" ]]' in workflow
    assert "RCC_RESERVATION_RELEASE_REQUIRED=TRUE" in workflow


def test_control_plane_is_separate_from_immutable_released_product_source() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert "Check out current deploy control plane" in workflow
    assert "Check out exact released product source" in workflow
    assert "path: control-plane" in workflow
    assert "path: released-source" in workflow
    assert 'ref: ${{ github.sha }}' in workflow
    assert 'ref: ${{ steps.source.outputs.sha }}' in workflow
    assert "JAP_DEPLOY_CONTROL_PLANE=PASS" in workflow
    assert "JAP_EXACT_RELEASE_SOURCE_HANDOFF=PASS" in workflow
    assert 'JAP_DEPLOY_SOURCE_ROOT: ${{ github.workspace }}/released-source' in workflow
    assert "bash control-plane/scripts/deploy_jap_windows_control_center_local.sh" in workflow


def test_deploy_must_prove_exact_release_installed_not_merely_deferred() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    deploy = workflow.index("Prove local Windows interop and stage update fail-closed")
    installed = workflow.index("Require exact released version to be installed")
    runtime_smoke = workflow.index("Prove installed runtime handoff without GUI")
    assert deploy < installed < runtime_smoke
    assert "Prove installed desktop rejects headless runner launch" not in workflow
    assert 'test "${installed[0]}" = "$EXPECTED_SOURCE_SHA"' in workflow
    assert 'test "${installed[1]}" = "$expected_version"' in workflow
    assert "JAP_LOCAL_DEPLOY_INSTALLED_RELEASE=PASS" in workflow


def test_installed_release_probe_stays_inside_yaml_run_block() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert "mapfile -t installed < <(python3 -c" in workflow
    assert "python3 - \"$current_json\" <<'PY'" not in workflow
    assert "\nimport json\n" not in workflow


def test_local_runner_can_receive_release_root_from_current_control_plane() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'CONTROL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"' in script
    assert 'ROOT="${JAP_DEPLOY_SOURCE_ROOT:-$CONTROL_ROOT}"' in script
    assert 'SOURCE_SHA="$(git -C "$ROOT" rev-parse HEAD)"' in script
    assert 'DESKTOP_VERSION="$(tr -d' in script


def test_local_runner_stages_latest_direct_update_and_auto_applies_when_closed() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'EXPECTED_REPOSITORY_ID="1230805345"' in script
    assert 'ROUTING_LABEL="job-pipeline-runtime-linux"' in script
    assert 'EXPECTED_RUNNER="rcc-general-linux-01--jap"' in script
    assert 'LEGACY_WARM_RUNNER="job-pipeline-runtime-warm-01-linux"' in script
    assert "JAP_LOCAL_DEPLOY_RUNNER_ADMISSION=PASS" in script
    assert 'UPDATE_MODE="gui_prompt_latest_direct_v1"' in script
    assert 'PENDING_SCHEMA="job_application_pipeline.windows_pending_update.v1"' in script
    assert 'policy": "latest_direct"' in script
    assert 'JAP_LOCAL_DEPLOY=STAGED' in script
    assert 'pending-update.json' in script
    assert 'sha256sum "$ARCHIVE"' in script
    assert 'STABLE_APPLIER="$INSTALL_ROOT/Apply-JAP-Control-Center-Update.ps1"' in script
    assert 'cp "$CONTROL_ROOT/Apply-JAP-Control-Center-Update.ps1" "$STABLE_APPLIER"' in script
    assert 'WINDOWS_APPLIER="$(wslpath -w "$STABLE_APPLIER")"' in script
    assert 'JAP_LOCAL_DEPLOY=AUTO_APPLY_CLOSED' in script
    assert 'JAP_LOCAL_DEPLOY=AUTO_APPLY_PASS' in script
    assert 'JAP_LOCAL_DEPLOY=AWAITING_GUI_CONSENT' in script
    assert '-ExecutionPolicy RemoteSigned' in script
    assert '-ExecutionPolicy Bypass' not in script
    assert 'STAGE_TMP/source' not in script
    assert '"source_root"' not in script
    assert 'STAGE_ROOT/source/Apply-JAP-Control-Center-Update.ps1' not in script
    assert '-HostPid 0' in script


def test_local_runner_requires_exact_release_and_ancestor_of_current_main() -> None:
    script = _text(LOCAL_DEPLOY)
    assert 'git ls-remote "$READ_ONLY_FETCH_URL" refs/heads/main' in script
    assert 'git -C "$ROOT" merge-base --is-ancestor "$SOURCE_SHA" "$FETCHED_MAIN"' in script
    assert 'release_source_not_ancestor_of_main' in script
    assert 'JAP_LOCAL_DEPLOY_MAIN_AHEAD=TRUE' in script
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


def test_desktop_host_probe_avoids_powershell_script_execution() -> None:
    script = _text(LOCAL_DEPLOY)

    assert 'tasklist.exe /FI "IMAGENAME eq JAP.ControlCenter.Desktop.exe"' in script
    assert "JAP_LOCAL_DEPLOY_DESKTOP_HOST_COUNT=" in script
    assert '[[ "$process_count" =~ ^[0-9]+$ ]]' in script
    assert "if (( process_count > 0 )); then" in script
    assert "Get-Process -Name" not in script


def test_local_deploy_proves_exact_installed_runtime_handoff_and_cleanup() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)

    assert "Prove installed runtime handoff without GUI" in workflow
    assert '-File "$launcher_windows"' in workflow
    assert "-NoBrowser" in workflow
    assert "timeout 90s powershell.exe" in workflow
    assert "-ExecutionPolicy RemoteSigned" in workflow
    assert "-ExecutionPolicy Bypass" not in workflow
    assert "released-source/scripts/reap_jap_headless_desktop.ps1" not in workflow
    assert "released-source/scripts/prove_jap_headless_desktop_rejection.ps1" not in workflow
    assert "http://127.0.0.1:8780/app-info.json" in workflow
    assert 'test "$runtime_sha" = "$EXPECTED_SOURCE_SHA"' in workflow
    assert "JAP_INSTALLED_RUNTIME_SMOKE=PASS" in workflow
    assert '-File "$stopper_windows"' in workflow
    assert "JAP_INSTALLED_RUNTIME_STOP=PASS" in workflow
    assert "trap cleanup_runtime EXIT" in workflow
