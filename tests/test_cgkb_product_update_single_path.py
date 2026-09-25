from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_routine_update_is_product_local_and_has_single_authority() -> None:
    agent = read("windows/JAP.ControlCenter.Desktop/ProductUpdateAgent.cs")
    coordinator = read("windows/JAP.ControlCenter.Desktop/UpdateCoordinator.cs")
    assert "product_local_update_agent_v2" in agent
    assert "job_application_pipeline.windows_product_update.v2" in agent
    assert "jap-winapp-product-v" in agent
    assert "JAP-Control-Center-Runtime.zip" in agent
    assert "desktop-staged" in agent
    assert "runtime-staged" in agent
    assert "apply-helper" in agent
    assert "ZipFile.ExtractToDirectory" in agent
    assert "pending_published" in agent
    assert "MinimumDirectVersion = new(1, 0, 65)" in agent
    assert "Staged WSL runtime bridge contains CR bytes." in agent
    assert "Staged local OSS provisioner contains CR bytes." in agent

    assert "accepted-update.json" in coordinator
    assert "pending.ApplyHelperExecutable" in coordinator
    assert "--apply-update" in coordinator
    assert "CopyDirectory(" not in coordinator
    assert "powershell.exe" not in coordinator.lower()
    assert "wsl.exe" not in coordinator.lower()
    assert "git " not in coordinator.lower()
    assert "installedVersion >= new Version(1, 0, 65)" in coordinator


def test_update_operation_is_cross_process_singleflight_per_installation() -> None:
    operation = read("windows/JAP.ControlCenter.Desktop/ProductUpdateOperation.cs")
    agent = read("windows/JAP.ControlCenter.Desktop/ProductUpdateAgent.cs")
    applier = read("windows/JAP.ControlCenter.Desktop/ProductUpdateApplier.cs")

    assert 'Local\\JAP.ControlCenter.ProductUpdateOperation.' in operation
    assert "CreateOperationMutex" in operation
    assert "TryAcquire" in operation
    assert "catch (AbandonedMutexException)" in operation

    assert "ProductUpdateOperation.CreateOperationMutex(installRoot)" in agent
    assert "TimeSpan.Zero" in agent
    assert '"stage_skipped"' in agent
    assert '"reason=update_operation_in_progress"' in agent

    assert "ProductUpdateOperation.CreateOperationMutex(installRoot)" in applier
    assert "TimeSpan.FromSeconds(60)" in applier
    assert '"apply_lock_recovered"' in applier


def test_update_handoff_blocks_unowned_desktop_start_before_runtime_access() -> None:
    operation = read("windows/JAP.ControlCenter.Desktop/ProductUpdateOperation.cs")
    coordinator = read("windows/JAP.ControlCenter.Desktop/UpdateCoordinator.cs")
    program = read("windows/JAP.ControlCenter.Desktop/Program.cs")
    applier = read("windows/JAP.ControlCenter.Desktop/ProductUpdateApplier.cs")

    assert '"update-handoff.json"' in operation
    assert '"JAP_UPDATE_HANDOFF_TOKEN"' in operation
    assert "RandomNumberGenerator.GetBytes(32)" in operation
    assert "CryptographicOperations.FixedTimeEquals" in operation
    assert "ProductUpdateOperation.BeginHandoff(" in coordinator
    assert "ProductUpdateOperation.AttachRestartToken(startInfo, handoffToken)" in coordinator
    assert "ProductUpdateOperation.ClearHandoff(_installRoot)" in coordinator

    guard = program.index("ProductUpdateOperation.HasActiveHandoff(installRoot)")
    app_run = program.index("Application.Run(new UpdateAwareApplicationContext())")
    assert guard < app_run
    assert "ProductUpdateOperation.RestartTokenMatches(" in program

    assert "ProductUpdateOperation.RestartTokenMatches(installRoot, handoffToken)" in applier
    assert "StartProductWithHandoff(" in applier
    assert "ProductUpdateOperation.ClearHandoff(installRoot)" in applier


def test_target_desktop_stage_supplies_the_isolated_apply_helper() -> None:
    agent = read("windows/JAP.ControlCenter.Desktop/ProductUpdateAgent.cs")

    assert "CopyDirectory(desktopStage, helperRoot);" in agent
    assert "CopyDirectory(AppContext.BaseDirectory, helperRoot);" not in agent


def test_failed_cutover_restores_components_independently_before_metadata() -> None:
    applier = read("windows/JAP.ControlCenter.Desktop/ProductUpdateApplier.cs")

    assert "desktopBackedUp = true" in applier
    assert "runtimeBackedUp = true" in applier
    assert "StopLiveDesktopPeers(desktopLive, logPath)" in applier
    assert "DeleteDirectoryWithRetry(" in applier
    assert '"rollback_component_failed"' in applier
    assert "VerifyDesktopStage(desktopLive, previousSha, previousVersion)" in applier
    assert "VerifyRuntimeStage(runtimeLive, previousSha, previousVersion)" in applier
    assert '"rollback_generation_verified"' in applier
    assert '"rollback_incomplete_handoff_retained"' in applier

    verify_desktop = applier.index(
        "VerifyDesktopStage(desktopLive, previousSha, previousVersion)"
    )
    verify_runtime = applier.index(
        "VerifyRuntimeStage(runtimeLive, previousSha, previousVersion)"
    )
    restore_metadata = applier.index('var temporary = currentPath + ".rollback.tmp"')
    assert verify_desktop < restore_metadata
    assert verify_runtime < restore_metadata



def test_download_stream_is_closed_before_checksum_reopens_temporary_archive() -> None:
    agent = read("windows/JAP.ControlCenter.Desktop/ProductUpdateAgent.cs")

    assert "await DownloadArchiveAsync(client, archiveUrl, temporaryArchive);" in agent
    helper_start = agent.index("private static async Task DownloadArchiveAsync(")
    helper_end = agent.index("private static void ExtractFresh", helper_start)
    helper = agent[helper_start:helper_end]

    assert "FileShare.None" in helper
    assert "await using (var destination = new FileStream(" in helper
    assert "ComputeFileSha256" not in helper

    prepare_start = agent.index("private static async Task<string> PrepareArchiveAsync(")
    prepare_end = agent.index("private static async Task DownloadArchiveAsync(", prepare_start)
    prepare = agent[prepare_start:prepare_end]
    assert prepare.index(
        "await DownloadArchiveAsync(client, archiveUrl, temporaryArchive);"
    ) < prepare.index("ProductUpdateIntegrity.ComputeFileSha256(temporaryArchive)")


def test_post_consent_applier_has_no_discovery_download_or_extraction_authority() -> None:
    applier = read("windows/JAP.ControlCenter.Desktop/ProductUpdateApplier.cs")
    assert "desktop_stage" in applier
    assert "runtime_stage" in applier
    assert "ComputeDirectorySha256" in applier
    assert 'MoveDirectoryWithRetry(desktopStage, desktopLive, logPath, "desktop_stage_to_live")' in applier
    assert 'MoveDirectoryWithRetry(runtimeStage, runtimeLive, logPath, "runtime_stage_to_live")' in applier
    assert 'MoveDirectoryWithRetry(desktopLive, desktopBackup, logPath, "desktop_live_to_backup")' in applier
    assert 'MoveDirectoryWithRetry(runtimeLive, runtimeBackup, logPath, "runtime_live_to_backup")' in applier
    assert "IsTransientMoveFailure" in applier
    assert "IsTransientSharingViolation" in applier
    assert "UnauthorizedAccessException" in applier
    assert "nativeCode is 5 or 32 or 33" in applier
    assert "MoveRetryWindow = TimeSpan.FromSeconds(45)" in applier
    assert '"move_retry"' in applier
    assert '"move_retry_recovered"' in applier
    assert '"delete_retry"' in applier
    assert '"delete_retry_recovered"' in applier
    assert '"host_exit_wait_complete"' in applier
    assert '"restart_verify_complete"' in applier
    assert '"cutover_live_verified"' in applier
    assert "Live desktop tree integrity mismatch after cutover." in applier
    assert "Live runtime tree integrity mismatch after cutover." in applier
    assert "Staged runtime shell script contains CR bytes:" in applier
    assert "VerifyRestartedProduct" in applier
    assert "source_revision" in applier
    assert "runtime_verified" in applier
    assert "desktopBackup" in applier
    assert "runtimeBackup" in applier
    assert "previousCurrentJson" in applier
    for forbidden in (
        "ZipFile.ExtractToDirectory",
        "HttpClient.GetAsync",
        "github.com/repos",
        "git fetch",
        "git checkout",
        "powershell.exe",
        "wsl.exe",
        "npm ",
    ):
        assert forbidden.lower() not in applier.lower()


def test_failed_update_does_not_reprompt_same_target_immediately() -> None:
    applier = read("windows/JAP.ControlCenter.Desktop/ProductUpdateApplier.cs")
    coordinator = read("windows/JAP.ControlCenter.Desktop/UpdateCoordinator.cs")

    assert "FailureRetryDelay = TimeSpan.FromMinutes(10)" in applier
    assert "WriteFailureSnooze(" in applier
    assert '"apply_failed_retry_cooldown"' in applier
    assert "TryDelete(snoozePath);" in applier

    assert "FailureRetryDelay = TimeSpan.FromMinutes(10)" in coordinator
    assert "snoozeMatchesPending" in coordinator
    assert "if (snoozeMatchesPending && snooze!.SnoozeUntilUtc > now)" in coordinator
    assert "WriteFailureCooldown(" in coordinator
    assert '"apply_failed_retry_cooldown"' in coordinator
    assert "Derselbe Update-Stand wird für" in coordinator
    assert "Ein neuerer Stand bleibt sofort zulässig." in coordinator


def test_release_generation_contains_both_immutable_product_assets() -> None:
    workflow = read(".github/workflows/jap-windows-desktop-host-release.yml")
    assert "jap-winapp-product-v$Version" in workflow
    assert "JAP-Control-Center-Desktop-win-x64.zip" in workflow
    assert "JAP-Control-Center-Runtime.zip" in workflow
    assert "runtime-info.json" in workflow
    assert "cgkb_product_local_v1" in workflow
    assert "--target $env:GITHUB_SHA" in workflow
    assert "jap-winapp-desktop-v$Version" not in workflow
    assert '$Body = $Body.Replace("`r`n", "`n").Replace("`r", "`n")' in workflow
    assert "Runtime shell script still contains CR bytes" in workflow
    assert "Runtime release ZIP contains CR bytes" in workflow


def test_legacy_routine_update_surfaces_are_physically_absent() -> None:
    forbidden = [
        "Update-" + "JAP-Control-Center.ps1",
        "Apply-" + "JAP-Control-Center-Update.ps1",
        "scripts/deploy_" + "jap_windows_control_center_local.sh",
        ".github/workflows/jap-windows-control-center-" + "local-deploy.yml",
        "tests/test_jap_windows_control_center_" + "local_deploy.py",
        "tests/test_jap_windows_control_center_" + "update_flow.py",
        "JAP-" + "Control-Center.ps1",
    ]
    for relative in forbidden:
        assert not (ROOT / relative).exists(), f"legacy authority surface returned: {relative}"


def test_active_update_authority_does_not_reference_retired_routine_paths() -> None:
    active = [
        ".github/workflows/jap-windows-control-center-contract.yml",
        ".github/workflows/jap-windows-desktop-host-release.yml",
        "windows/JAP.ControlCenter.Desktop/ProductUpdateAgent.cs",
        "windows/JAP.ControlCenter.Desktop/ProductUpdateApplier.cs",
        "windows/JAP.ControlCenter.Desktop/UpdateCoordinator.cs",
        "windows/JAP.ControlCenter.Desktop/ManagedRuntimeController.cs",
        "scripts/run_jap_windows_control_center.sh",
    ]
    forbidden = [
        "Apply-" + "JAP-Control-Center-Update.ps1",
        "Update-" + "JAP-Control-Center.ps1",
        "deploy_" + "jap_windows_control_center_local.sh",
        "jap-windows-control-center-" + "local-deploy.yml",
        "managed_worktree",
        "wsl_installed_runner_path",
        "local_runner_staged_gui_prompt",
    ]
    for relative in active:
        body = read(relative)
        for token in forbidden:
            assert token not in body, f"{token} returned in {relative}"


def test_bootstrap_is_explicit_bridge_not_routine_update_authority() -> None:
    installer = read("install-jap-control-center.ps1")
    compatibility = read("windows/JAP.ControlCenter.Desktop/UPDATE_COMPATIBILITY.json")
    assert "JAP_CONTROL_CENTER_BOOTSTRAP_BRIDGE=PASS" in installer
    assert "CGKB product-local bootstrap requires version 1.0.65 or newer." in installer
    assert 'update_authority = "product_local_update_agent_v2"' in installer
    assert 'update_generation = $UpdateGeneration' in installer
    assert '"bootstrap_bridge_from": "pre-1.0.65"' in compatibility
    assert '"minimum_direct_version": "1.0.65"' in compatibility
    assert '"installer_schema": "job_application_pipeline.windows_control_center_install.v3"' in compatibility



def test_single_instance_guard_uses_mutex_ownership_not_named_object_existence() -> None:
    program = read("windows/JAP.ControlCenter.Desktop/Program.cs")

    assert "new Mutex(initiallyOwned: false, MutexName)" in program
    assert "mutex.WaitOne(0, false)" in program
    assert "catch (AbandonedMutexException)" in program
    assert "mutex.ReleaseMutex()" in program
    assert "out var createdNew" not in program



def test_single_instance_guard_reactivates_or_waits_instead_of_false_already_open_popup() -> None:
    program = read("windows/JAP.ControlCenter.Desktop/Program.cs")

    assert "TryActivateExistingVisibleWindow" in program
    assert "NativeMethods.IsWindowVisible" in program
    assert "NativeMethods.ShowWindowAsync" in program
    assert "NativeMethods.SetForegroundWindow" in program
    assert "LifecycleHandoffTimeout = TimeSpan.FromSeconds(25)" in program
    assert "mutex.WaitOne(LifecycleHandoffTimeout, false)" in program
    assert "IsProductUpdateHandoffInProgress" in program
    assert "accepted-update.json" in program
    assert "UpdateHandoffProbeTimeout = TimeSpan.FromSeconds(8)" in program
    assert "JAP Control Center ist bereits geöffnet." not in program
    assert "wird gerade aktualisiert und startet anschließend automatisch neu" in program
    assert "wird gerade beendet oder neu gestartet" in program
