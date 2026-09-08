from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "JAP-Control-Center.ps1"
WSL_RUNNER = ROOT / "scripts" / "run_jap_windows_control_center.sh"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_launcher_is_unbuffered_and_uses_installed_fast_start() -> None:
    runner = _text(WSL_RUNNER)
    assert "export PYTHONUNBUFFERED=1" in runner
    assert "launcher=(python -u scripts/run_product_v1_live_demo.py --installed-runtime)" in runner
    assert 'export JAP_CONTROL_CENTER_PINNED_SHA="$PINNED_SHA"' in runner
    assert "JAP_WINDOWS_APP_PYTHON_UNBUFFERED=1" in runner
    assert "JAP_WINDOWS_APP_PINNED_SHA=" in runner


def test_powershell_readiness_deadline_finishes_inside_desktop_hard_timeout() -> None:
    launcher = _text(LAUNCHER)
    assert "$readinessDeadline = [DateTime]::UtcNow.AddSeconds(75)" in launcher
    assert "while ([DateTime]::UtcNow -lt $readinessDeadline)" in launcher
    assert "Get-Content $stdoutLog -Tail 12" in launcher
    assert "Get-Content $stderrLog -Tail 12" in launcher
    assert "Last endpoint error" in launcher
    assert "attempt -lt 240" not in launcher


def test_existing_runtime_is_reused_only_for_exact_installed_source_revision() -> None:
    launcher = _text(LAUNCHER)
    assert "/app-info.json" in launcher
    assert "source_revision" in launcher
    assert "$sourceRevision -eq $expected" in launcher
    assert "JAP_CONTROL_CENTER_RUNTIME=STALE" in launcher
    assert "& $StopperPath -InstallRoot $InstallRoot" in launcher
    assert "The stale managed JAP runtime did not release port" in launcher


def test_long_lived_wsl_runtime_is_detached_from_powershell_redirected_pipes() -> None:
    launcher = _text(LAUNCHER)
    assert '$starterName = "jap-runtime-detached.cmd"' in launcher
    assert 'start "" /b "{0}" {1} 1>"{2}" 2>"{3}"' in launcher
    assert 'FilePath = $env:ComSpec' in launcher
    assert 'WorkingDirectory = $LogRoot' in launcher
    assert 'launch_mode = "cmd_start_detached"' in launcher
    assert 'RedirectStandardOutput = $stdoutLog' not in launcher
    assert 'RedirectStandardError = $stderrLog' not in launcher
    assert "$process.WaitForExit(10000)" in launcher


def test_runtime_diagnostic_release_bumps_immutable_desktop_version() -> None:
    assert _text(VERSION).strip() == "1.0.12"
