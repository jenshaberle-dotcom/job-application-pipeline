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


def test_runtime_launcher_is_unbuffered_and_uses_immutable_runtime_bundle() -> None:
    runner = _text(WSL_RUNNER)
    assert "export PYTHONUNBUFFERED=1" in runner
    assert "runtime-info.json" in runner
    assert "frontend/control-center/dist" in runner
    assert (
        "launcher=(python -u scripts/run_product_v1_live_demo.py "
        "--installed-runtime --reuse-frontend)" in runner
    )
    assert 'export JAP_CONTROL_CENTER_PINNED_SHA="$PINNED_SHA"' in runner
    assert "JAP_WINDOWS_APP_RUNTIME_BUNDLE=" in runner
    assert "JAP_WINDOWS_APP_PINNED_SHA=" in runner
    assert "git fetch" not in runner
    assert "git checkout" not in runner
    assert "npm install" not in runner
    assert "npm ci" not in runner
    assert "npm run build" not in runner


def test_runtime_launcher_binds_to_requirements_pinned_local_oss_site() -> None:
    runner = _text(WSL_RUNNER)
    assert "scripts/ensure_pinned_local_oss_runtime.sh" in runner
    assert '"$RUNTIME_ROOT/requirements.txt"' in runner
    assert '"$PROJECT_ROOT/.runtime/local-oss-sites"' in runner
    assert 'export PYTHONPATH="$LOCAL_OSS_SITE${PYTHONPATH:+:$PYTHONPATH}"' in runner
    assert "python -c 'import extruct, trafilatura, pymupdf'" in runner
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
    assert "detachedDiagnostics" in controller
    assert '" | Runtime: " + detachedDiagnostics' in controller


def test_existing_runtime_is_reused_only_for_exact_installed_source_revision() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    assert '"source_revision"' in controller
    assert "sourceRevision == expectedSha" in controller
    assert "if (endpoint.IsJap)" in controller
    assert "await StopAsync(TimeSpan.FromSeconds(20))" in controller
    assert "Die veraltete JAP Runtime hat Port" in controller


def test_desktop_runtime_control_uses_runtime_bundle_paths_not_update_authority() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    program = _text(PROGRAM)
    assert "wsl.exe" in controller
    assert '"--exec"' in controller
    assert '"bash"' in controller
    assert "config.WslRunner" in controller
    assert "config.RuntimeRoot" in controller
    assert '"launch"' in controller
    assert '"--stop"' in controller
    assert 'launch_mode = "desktop_native_wsl_runtime_bundle_v1"' in controller
    assert "powershell.exe" not in controller.lower()
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


def test_long_lived_wsl_runtime_is_detached_inside_linux_without_prepare_path() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    runner = _text(WSL_RUNNER)
    assert '"launch"' in controller
    assert "runtime.stdout.log" in controller
    assert "runtime.stderr.log" in controller
    assert "cmd.exe" not in controller
    assert '[[ "$ACTION" == "start" || "$ACTION" == "launch" ]]' in runner
    launch = runner.split('if [[ "$ACTION" == "launch" ]]', 1)[1].split(
        '[[ -x "$PROJECT_ROOT/.venv/bin/python" ]]', 1
    )[0]
    assert 'command -v nohup' in launch
    assert 'command -v setsid' in launch
    assert 'nohup setsid bash "$0"' in launch
    assert '>"$DETACHED_STDOUT"' in launch
    assert '2>"$DETACHED_STDERR"' in launch
    assert 'JAP_WINDOWS_APP_DETACHED_HANDOFF=PASS' in launch
    assert '"prepare"' not in runner


def test_current_runtime_release_version() -> None:
    assert _text(VERSION).strip() == "1.1.11"



def test_installed_runtime_shell_scripts_are_repaired_to_lf_before_every_wsl_handoff() -> None:
    controller = _text(RUNTIME_CONTROLLER)
    assert "NormalizeInstalledRuntimeShellScripts(_installRoot, config)" in controller
    assert "NormalizeInstalledRuntimeShellScripts(installRoot, config)" in controller
    assert 'Directory.EnumerateFiles(' in controller
    assert '"*.sh"' in controller
    assert "SearchOption.AllDirectories" in controller
    assert "bytes.Contains((byte)'\\r')" in controller
    assert '.Replace("\\r\\n", "\\n", StringComparison.Ordinal)' in controller
    assert '.Replace("\\r", "\\n", StringComparison.Ordinal)' in controller
    assert "runtime-info.json" in controller
    assert "config.PinnedSha" in controller
