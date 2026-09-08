from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "JAP-Control-Center.ps1"
WSL_RUNNER = ROOT / "scripts" / "run_jap_windows_control_center.sh"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_launcher_is_unbuffered_for_live_phase_diagnostics() -> None:
    runner = _text(WSL_RUNNER)
    assert "export PYTHONUNBUFFERED=1" in runner
    assert "launcher=(python -u scripts/run_product_v1_live_demo.py)" in runner
    assert "JAP_WINDOWS_APP_PYTHON_UNBUFFERED=1" in runner


def test_powershell_readiness_deadline_finishes_inside_desktop_hard_timeout() -> None:
    launcher = _text(LAUNCHER)
    assert "$readinessDeadline = [DateTime]::UtcNow.AddSeconds(75)" in launcher
    assert "while ([DateTime]::UtcNow -lt $readinessDeadline)" in launcher
    assert "Get-Content $stdoutLog -Tail 16" in launcher
    assert "Get-Content $stderrLog -Tail 16" in launcher
    assert "Last endpoint error" in launcher
    assert "attempt -lt 240" not in launcher


def test_runtime_diagnostic_release_bumps_immutable_desktop_version() -> None:
    assert _text(VERSION).strip() == "1.0.7"
