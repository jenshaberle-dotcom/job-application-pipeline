from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "DesktopLifecycleGuard.cs"
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
    assert "Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException)" in guard
    assert "Application.ThreadException" in guard
    assert "AppDomain.CurrentDomain.UnhandledException" in guard
    assert 'FailClosed("ui_thread_exception"' in guard
    assert "StopManagedRuntimeBestEffort()" in guard
    assert '"Stop-JAP-Control-Center.ps1"' in guard
    assert "process.WaitForExit(20_000)" in guard
    assert "process.Kill(entireProcessTree: true)" in guard
    assert "Environment.Exit(1)" in guard
    assert '"desktop-host-lifecycle.log"' in guard


def test_zombie_prevention_bumps_immutable_desktop_release() -> None:
    assert _text(VERSION).strip() == "1.0.14"
