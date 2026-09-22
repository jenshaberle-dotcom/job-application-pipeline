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
    assert (
        "launcher=(python -u scripts/run_product_v1_live_demo.py "
        "--installed-runtime --reuse-frontend)" in runner
    )
    start = runner.split("# Reuse the canonical private runtime environment.", 1)[1]
    assert "--prepare-frontend-only" not in start
    assert "npm install" not in start
    assert "npm ci" not in start
    assert 'export JAP_CONTROL_CENTER_PINNED_SHA="$PINNED_SHA"' in runner
    assert "JAP_WINDOWS_APP_PYTHON_UNBUFFERED=1" in runner
    assert "JAP_WINDOWS_APP_PINNED_SHA=" in runner


def test_runtime_launcher_binds_to_requirements_pinned_local_oss_site() -> None:
    runner = _text(WSL_RUNNER)
    assert "scripts/ensure_pinned_local_oss_runtime.sh" in runner
    assert '"$MANAGED_WORKTREE/requirements.txt"' in runner
    assert '"$PROJECT_ROOT/.runtime/local-oss-sites"' in runner
    assert 'export PYTHONPATH="$LOCAL_OSS_SITE${PYTHONPATH:+:$PYTHONPATH}"' in runner
    assert "python -c 'import extruct, trafilatura'" in runner
    assert "pinned_local_oss_runtime_import_failed" in runner
    assert "JAP_WINDOWS_APP_LOCAL_OSS_SITE=" in runner


def test_powershell_readiness_deadline_finishes_inside_desktop_hard_timeout() -> None:
    launcher = _text(LAUNCHER)
    assert "$readinessDeadline = [DateTime]::UtcNow.AddSeconds(75)" in launcher
    assert "while ([DateTime]::UtcNow -lt $readinessDeadline)" in launcher
    assert "--exec tail -n 12 $stdoutLinux" in launcher
    assert "--exec tail -n 12 $stderrLinux" in launcher
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


def test_long_lived_wsl_runtime_is_detached_inside_linux_without_cmd_handoff() -> None:
    launcher = _text(LAUNCHER)
    runner = _text(WSL_RUNNER)

    assert '$stdoutLinux = "$stateRootLinux/runtime.stdout.log"' in launcher
    assert '$stderrLinux = "$stateRootLinux/runtime.stderr.log"' in launcher
    assert "--exec wslpath" not in launcher
    assert '"launch"' in launcher
    assert '& $wsl.Source @wslArgumentVector' in launcher
    assert 'launch_mode = "wsl_nohup_setsid"' in launcher
    assert "jap-runtime-detached.cmd" not in launcher
    assert 'FilePath = $env:ComSpec' not in launcher
    assert 'start "" /b' not in launcher
    assert 'RedirectStandardOutput = $stdoutLog' not in launcher
    assert 'RedirectStandardError = $stderrLog' not in launcher

    assert '[[ "$ACTION" == "start" || "$ACTION" == "prepare" || "$ACTION" == "launch" ]]' in runner
    launch = runner.split('if [[ "$ACTION" == "launch" ]]', 1)[1].split(
        '[[ -d "$PROJECT_ROOT/.git" ]]', 1
    )[0]
    assert 'command -v nohup' in launch
    assert 'command -v setsid' in launch
    assert 'nohup setsid bash "$0"' in launch
    assert '>"$DETACHED_STDOUT"' in launch
    assert '2>"$DETACHED_STDERR"' in launch
    assert 'JAP_WINDOWS_APP_DETACHED_HANDOFF=PASS' in launch


def test_runtime_diagnostic_release_bumps_immutable_desktop_version() -> None:
    assert _text(VERSION).strip() == "1.0.52"
