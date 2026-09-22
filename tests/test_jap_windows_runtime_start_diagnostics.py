from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CONTROLLER = (
    ROOT / "windows" / "JAP.ControlCenter.Desktop" / "ManagedRuntimeController.cs"
)
PROGRAM = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "Program.cs"
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


def test_native_runtime_readiness_finishes_inside_desktop_hard_timeout() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    assert "Math.Clamp(timeout.TotalSeconds - 10, 5, 75)" in controller
    assert "DateTimeOffset.UtcNow.AddSeconds(readinessBudgetSeconds)" in controller
    assert '/app-info.json' in controller
    assert "ReadLinuxTailAsync" in controller
    assert '"tail",' in controller
    assert '"12",' in controller
    assert "Letzter Endpoint-Fehler" in controller


def test_existing_runtime_is_reused_only_for_exact_installed_source_revision() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    assert '"source_revision"' in controller
    assert "sourceRevision == expectedSha" in controller
    assert "if (endpoint.IsJap)" in controller
    assert "await StopAsync(TimeSpan.FromSeconds(20))" in controller
    assert "Die veraltete JAP Runtime hat Port" in controller


def test_desktop_runtime_control_no_longer_depends_on_powershell_launchers() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    program = _text(PROGRAM)
    assert "wsl.exe" in controller
    assert '"--exec"' in controller
    assert '"bash"' in controller
    assert "config.WslRunner" in controller
    assert '"launch"' in controller
    assert '"--stop"' in controller
    assert 'launch_mode = "desktop_native_wsl_v1"' in controller
    assert "powershell.exe" not in controller.lower()
    assert "JAP-Control-Center.ps1" not in program
    assert "Stop-JAP-Control-Center.ps1" not in program
    assert "-ExecutionPolicy" not in program
    assert "Bypass" not in program


def test_desktop_recovers_docker_desktop_and_exact_postgres_container_before_product_runtime() -> None:
    controller = _text(RUNTIME_CONTROLLER)

    assert "DatabasePort = 5432" in controller
    assert 'DockerContainerName = "job_pipeline_postgres"' in controller
    assert "EnsureDatabaseRuntimeAsync(config)" in controller
    assert '"Docker Desktop.exe"' in controller
    assert 'UseShellExecute = true' in controller
    assert '"docker",' in controller
    assert '"info"' in controller
    assert '"start"' in controller
    assert "DockerContainerName" in controller
    assert "Docker Desktop wurde nicht rechtzeitig bereit" in controller
    assert "JAP PostgreSQL wurde auf Port" in controller
    assert "powershell.exe" not in controller.lower()
    assert "sudo" not in controller.lower()


def test_long_lived_wsl_runtime_is_detached_inside_linux_without_cmd_handoff() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    runner = _text(WSL_RUNNER)

    assert '"launch"' in controller
    assert "runtime.stdout.log" in controller
    assert "runtime.stderr.log" in controller
    assert "cmd.exe" not in controller
    assert "FileName = $env:ComSpec" not in controller

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
    assert _text(VERSION).strip() == "1.0.58"
