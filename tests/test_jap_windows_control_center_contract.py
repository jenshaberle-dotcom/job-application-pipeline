from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "JAP-Control-Center.ps1"
INSTALLER = ROOT / "install-jap-control-center.ps1"
UPDATER = ROOT / "Update-JAP-Control-Center.ps1"
STOPPER = ROOT / "Stop-JAP-Control-Center.ps1"
WSL_RUNNER = ROOT / "scripts" / "run_jap_windows_control_center.sh"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_windows_app_entrypoints_are_present() -> None:
    for path in (LAUNCHER, INSTALLER, UPDATER, STOPPER, WSL_RUNNER):
        assert path.is_file(), path


def test_installer_is_per_user_and_creates_operator_shortcuts() -> None:
    text = _text(INSTALLER)
    assert 'Join-Path $env:LOCALAPPDATA "JAP-Control-Center"' in text
    assert "WScript.Shell" in text
    assert "JAP Control Center.lnk" in text
    assert "Update JAP Control Center.lnk" in text
    assert "Stop JAP Control Center.lnk" in text
    assert "$ExpectedRepositoryId = 1230805345" in text
    assert "$Port = 8780" in text


def test_windows_install_does_not_copy_private_runtime_state() -> None:
    text = _text(INSTALLER)
    forbidden_copy_targets = (
        'Copy-Item -Force "$PSScriptRoot\\.env"',
        'Copy-Item -Force "$PSScriptRoot\\private_application_sources"',
        "POSTGRES_PASSWORD=",
    )
    for forbidden in forbidden_copy_targets:
        assert forbidden not in text
    assert 'secrets_location = "wsl_project_env_only"' in text
    assert (
        'private_documents_location = "wsl_project_private_application_sources_only"'
        in text
    )


def test_wsl_runner_reuses_canonical_runtime_and_exact_pinned_code() -> None:
    text = _text(WSL_RUNNER)
    assert 'source "$PROJECT_ROOT/.venv/bin/activate"' in text
    assert 'source "$PROJECT_ROOT/.env"' in text
    assert (
        'export PRODUCT_V1_PRIVATE_DOCUMENT_ROOT="$PROJECT_ROOT/private_application_sources"'
        in text
    )
    assert 'git -C "$PROJECT_ROOT" worktree add --detach' in text
    assert '[[ "$(git -C "$MANAGED_WORKTREE" rev-parse HEAD)" == "$PINNED_SHA" ]]' in text
    assert 'scripts/run_product_v1_live_demo.py' in text
    assert 'PRODUCT_V1_UI_HOST="127.0.0.1"' in text
    assert 'PRODUCT_V1_UI_PORT="8780"' in text


def test_launcher_is_loopback_fail_closed_and_has_no_implicit_update() -> None:
    text = _text(LAUNCHER)
    assert 'http://127.0.0.1:$port/' in text
    assert "DeepOceanProductV1/" in text
    assert "Test-LoopbackPort" in text
    assert "Refusing to start another runtime" in text
    assert "git fetch" not in text
    assert "Update-JAP-Control-Center.ps1" not in text


def test_windows_path_translation_bypasses_default_linux_shell() -> None:
    launcher = _text(LAUNCHER)
    stopper = _text(STOPPER)
    assert "--exec wslpath -u $RunnerPath" in launcher
    assert "--exec wslpath -u $RunnerPath" in stopper
    assert "-- wslpath -u $RunnerPath" not in launcher
    assert "-- wslpath -u $RunnerPath" not in stopper
    assert "--exec bash" in launcher
    assert '"--exec",' in stopper


def test_install_and_update_fetch_main_over_https_not_ssh_origin() -> None:
    installer = _text(INSTALLER)
    updater = _text(UPDATER)
    for text in (installer, updater):
        assert "https://github.com/$ExpectedOrigin.git" in text
        assert '"fetch", "--no-tags", $ReadOnlyFetchUrl, "main"' in text
        assert '"rev-parse", "FETCH_HEAD"' in text
        assert '"fetch", "origin", "main"' not in text
    assert 'update_authority = "explicit_github_https_main"' in installer
    assert "FETCH_TRANSPORT=https" in installer
    assert "FETCH_TRANSPORT=https" in updater


def test_managed_runner_has_https_recovery_for_missing_pinned_commit() -> None:
    text = _text(WSL_RUNNER)
    assert "READ_ONLY_FETCH_URL='https://github.com/jenshaberle-dotcom/job-application-pipeline.git'" in text
    assert 'fetch --no-tags "$READ_ONLY_FETCH_URL" main' in text
    assert "fetch origin main" not in text
    assert "github_https_fetch_failed" in text


def test_stop_path_is_managed_pid_only() -> None:
    windows = _text(STOPPER)
    runner = _text(WSL_RUNNER)
    assert "--stop" in windows
    assert "managed_pid" in runner
    assert '"/proc/$pid/cmdline"' in runner
    assert "scripts/run_product_v1_live_demo.py" in runner
    assert 'kill "$pid"' in runner
    assert "pkill" not in runner
    assert "killall" not in runner


def test_powershell_does_not_use_bash_line_continuations() -> None:
    for path in (LAUNCHER, INSTALLER, UPDATER, STOPPER):
        lines = _text(path).splitlines()
        assert not any(line.rstrip().endswith("\\") for line in lines), path
