from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "DesktopLifecycleGuard.cs"
RUNTIME_CONTROLLER = (
    ROOT / "windows" / "JAP.ControlCenter.Desktop" / "ManagedRuntimeController.cs"
)
REAPER = ROOT / "scripts" / "reap_jap_headless_desktop.ps1"
PROOF = ROOT / "scripts" / "prove_jap_headless_desktop_rejection.ps1"
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


def test_current_desktop_lifecycle_release_version() -> None:
    assert _text(VERSION).strip() == "1.1.14"
