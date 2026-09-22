from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "DesktopLifecycleGuard.cs"
RUNTIME_CONTROLLER = (
    ROOT / "windows" / "JAP.ControlCenter.Desktop" / "ManagedRuntimeController.cs"
)
REAPER = ROOT / "scripts" / "reap_jap_headless_desktop.ps1"
PROOF = ROOT / "scripts" / "prove_jap_headless_desktop_rejection.ps1"
LOCAL_DEPLOY_WORKFLOW = (
    ROOT / ".github" / "workflows" / "jap-windows-control-center-local-deploy.yml"
)
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_noninteractive_desktop_host_is_rejected_before_message_loop() -> None:
    guard = _text(GUARD)
    assert "[ModuleInitializer]" in guard
    assert "if (!Environment.UserInteractive)" in guard
    assert '"noninteractive_start_rejected"' in guard
    assert "Environment.Exit(0)" in guard


def test_unhandled_ui_failure_is_fail_closed_and_cleans_runtime_bounded() -> None:
    guard = _text(GUARD)
    controller = _text(RUNTIME_CONTROLLER)
    assert "Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException)" in guard
    assert "Application.ThreadException" in guard
    assert "AppDomain.CurrentDomain.UnhandledException" in guard
    assert 'FailClosed("ui_thread_exception"' in guard
    assert "StopManagedRuntimeBestEffort()" in guard
    assert "ManagedRuntimeController.StopBestEffortSynchronously" in guard
    assert "TimeSpan.FromSeconds(20)" in guard
    assert "powershell.exe" not in guard.lower()
    assert "Stop-JAP-Control-Center.ps1" not in guard
    assert "-ExecutionPolicy" not in guard
    assert "Bypass" not in guard
    assert "process.WaitForExit" in controller
    assert "process.Kill(entireProcessTree: true)" in controller
    assert "Environment.Exit(1)" in guard
    assert '"desktop-host-lifecycle.log"' in guard


def test_local_runner_deploy_is_manual_recovery_only_after_product_agent_cutover() -> None:
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    trigger_block = workflow.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "push:" not in trigger_block
    assert "workflow_run:" not in trigger_block
    assert "schedule:" not in trigger_block
    assert "Manual recovery/bootstrap JAP Control Center" in workflow


def test_local_deploy_reaps_only_exact_session_zero_managed_desktop() -> None:
    reaper = _text(REAPER)
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert 'JAP-Control-Center\\desktop-host\\JAP.ControlCenter.Desktop.exe' in reaper
    assert 'Get-Process -Name "JAP.ControlCenter.Desktop"' in reaper
    assert "$hostProcess.SessionId -ne 0" in reaper
    assert "StringComparison]::OrdinalIgnoreCase" in reaper
    assert "Stop-Process -Id $pidToReap -Force" in reaper
    assert "$hostProcess.WaitForExit(5000)" in reaper
    assert 'JAP_HEADLESS_DESKTOP_REAP=PASS' in reaper
    assert "Reap exact stale Session-0 JAP desktop host" in workflow
    assert 'Get-Process -Name "JAP.ControlCenter.Desktop"' in workflow
    assert 'JAP-Control-Center\\desktop-host\\JAP.ControlCenter.Desktop.exe' in workflow
    assert "scripts/reap_jap_headless_desktop.ps1" not in workflow


def test_headless_rejection_proof_is_static_only_not_executed_on_workstation() -> None:
    proof = _text(PROOF)
    workflow = _text(LOCAL_DEPLOY_WORKFLOW)
    assert "$current.pinned_sha -ne $ExpectedSha" in proof
    assert "$current.desktop_host_version -ne $ExpectedVersion" in proof
    assert 'JAP_HEADLESS_DESKTOP_PROOF=SKIP' in proof
    assert "$_.SessionId -eq 0" in proof
    assert "Start-Process -FilePath $exe" in proof
    assert "$process.WaitForExit(10000)" in proof
    assert "$process.WaitForExit(10_000)" not in proof
    assert 'noninteractive_start_rejected`tpid=$pidUnderTest' in proof
    assert 'JAP_HEADLESS_DESKTOP_PROOF=PASS' in proof
    assert "Prove installed desktop rejects headless runner launch" not in workflow
    assert "scripts/prove_jap_headless_desktop_rejection.ps1" not in workflow
    assert "-ExecutionPolicy Bypass" not in workflow


def test_zombie_prevention_bumps_immutable_desktop_release() -> None:
    assert _text(VERSION).strip() == "1.0.55"
