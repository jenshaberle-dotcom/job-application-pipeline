from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = ROOT / ".gitignore"
LAUNCHER = ROOT / "JAP-Control-Center.ps1"
INSTALLER = ROOT / "install-jap-control-center.ps1"
UPDATER = ROOT / "Update-JAP-Control-Center.ps1"
STOPPER = ROOT / "Stop-JAP-Control-Center.ps1"
APPLIER = ROOT / "Apply-JAP-Control-Center-Update.ps1"
WSL_INSTALLER = ROOT / "scripts" / "install_jap_windows_control_center.sh"
WSL_RUNNER = ROOT / "scripts" / "run_jap_windows_control_center.sh"
ICON_GENERATOR = ROOT / "scripts" / "generate_jap_control_center_icon.py"
DESKTOP_ROOT = ROOT / "windows" / "JAP.ControlCenter.Desktop"
DESKTOP_PROJECT = DESKTOP_ROOT / "JAP.ControlCenter.Desktop.csproj"
DESKTOP_PROGRAM = DESKTOP_ROOT / "Program.cs"
DESKTOP_VERSION = DESKTOP_ROOT / "VERSION"
DESKTOP_COMPATIBILITY = DESKTOP_ROOT / "UPDATE_COMPATIBILITY.json"
DESKTOP_RELEASE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "jap-windows-desktop-host-release.yml"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_windows_app_entrypoints_are_present() -> None:
    for path in (
        LAUNCHER,
        INSTALLER,
        UPDATER,
        STOPPER,
        APPLIER,
        WSL_INSTALLER,
        WSL_RUNNER,
        ICON_GENERATOR,
        DESKTOP_PROJECT,
        DESKTOP_PROGRAM,
        DESKTOP_VERSION,
        DESKTOP_COMPATIBILITY,
        DESKTOP_RELEASE_WORKFLOW,
    ):
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
    assert (
        '[[ "$(git -C "$MANAGED_WORKTREE" rev-parse HEAD)" == "$PINNED_SHA" ]]'
        in text
    )
    assert "scripts/run_product_v1_live_demo.py" in text
    assert 'PRODUCT_V1_UI_HOST="127.0.0.1"' in text
    assert 'PRODUCT_V1_UI_PORT="8780"' in text
    assert 'export JAP_CONTROL_CENTER_PINNED_SHA="$PINNED_SHA"' in text


def test_launcher_is_loopback_fail_closed_and_has_no_implicit_update() -> None:
    text = _text(LAUNCHER)
    assert 'http://127.0.0.1:$port/' in text
    assert "DeepOceanProductV1/" in text
    assert "Test-LoopbackPort" in text
    assert "Refusing to start another runtime" in text
    assert "git fetch" not in text
    assert "Update-JAP-Control-Center.ps1" not in text


def test_installer_precomputes_linux_runner_path_inside_wsl() -> None:
    shell = _text(WSL_INSTALLER)
    installer = _text(INSTALLER)
    assert 'WINDOWS_LOCALAPPDATA="$(powershell.exe -NoProfile -Command' in shell
    assert 'WSL_LOCALAPPDATA="$(wslpath -u "$WINDOWS_LOCALAPPDATA")"' in shell
    assert (
        'WSL_INSTALLED_RUNNER="$WSL_LOCALAPPDATA/JAP-Control-Center/'
        'run-jap-control-center-wsl.sh"' in shell
    )
    assert '-WslInstalledRunnerPath "$WSL_INSTALLED_RUNNER"' in shell
    assert '[string]$WslInstalledRunnerPath' in installer
    assert 'wsl_installed_runner_path = $WslInstalledRunnerPath' in installer
    assert 'WSL_INSTALLED_RUNNER=$WslInstalledRunnerPath' in installer


def test_windows_runtime_never_translates_windows_path_with_wslpath() -> None:
    launcher = _text(LAUNCHER)
    stopper = _text(STOPPER)
    for text in (launcher, stopper):
        assert "wslpath" not in text
        assert "wsl_installed_runner_path" in text
        assert "StartsWith('/')" in text
    assert '"--exec",' in launcher
    assert '"--exec",' in stopper


def test_launcher_proves_direct_wsl_identity_before_background_start() -> None:
    text = _text(LAUNCHER)
    assert '& $wsl.Source -d $distro --exec test -f $linuxRunner' in text
    assert "Installed JAP WSL distribution/runner proof failed" in text


def test_launcher_uses_tokenized_startprocess_arguments_without_embedded_quotes() -> None:
    text = _text(LAUNCHER)
    assert "$argumentVector = @(" in text
    assert "ArgumentList = $argumentVector" in text
    assert "$argumentLine = (" not in text
    assert "'-d \"{0}\" --exec bash" not in text
    assert "contains whitespace" in text


def test_launcher_surfaces_stdout_when_wsl_reports_runtime_failure_there() -> None:
    text = _text(LAUNCHER)
    assert '$stdoutTail = ""' in text
    assert "Get-Content $stdoutLog -Tail 12" in text
    assert "did not become ready: $stdoutTail" in text


def test_installer_fetches_main_over_https_and_manual_updater_cannot_bypass_release() -> None:
    installer = _text(INSTALLER)
    updater = _text(UPDATER)
    assert "https://github.com/$ExpectedOrigin.git" in installer
    assert '"fetch", "--no-tags", $ReadOnlyFetchUrl, "main"' in installer
    assert '"rev-parse", "FETCH_HEAD"' in installer
    assert '"fetch", "origin", "main"' not in installer
    assert 'update_authority = "local_runner_staged_gui_prompt"' in installer
    assert "FETCH_TRANSPORT=https" in installer
    assert "git fetch" not in updater
    assert "pinned_sha =" not in updater
    assert 'ExpectedUpdateMode = "gui_prompt_latest_direct_v1"' in updater


def test_managed_runner_has_https_recovery_for_missing_pinned_commit() -> None:
    text = _text(WSL_RUNNER)
    assert (
        "READ_ONLY_FETCH_URL='https://github.com/"
        "jenshaberle-dotcom/job-application-pipeline.git'" in text
    )
    assert 'fetch --no-tags "$READ_ONLY_FETCH_URL" main' in text
    assert "fetch origin main" not in text
    assert "github_https_fetch_failed" in text


def test_managed_runner_selects_native_linux_node22_not_windows_npm() -> None:
    text = _text(WSL_RUNNER)
    assert "activate_native_node_runtime" in text
    assert 'export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"' in text
    assert 'source "$NVM_DIR/nvm.sh"' in text
    assert "nvm use --silent 22" in text
    assert '[[ "$node_path" != /mnt/* && "$npm_path" != /mnt/* ]]' in text
    assert "native_node22_runtime_unavailable" in text
    assert "JAP_WINDOWS_APP_NODE_VERSION=" in text
    assert "JAP_WINDOWS_APP_NPM=" in text


def test_generated_frontend_state_is_source_bound_before_reuse() -> None:
    ignore = _text(GITIGNORE)
    runner = _text(WSL_RUNNER)
    dependency_reset = 'rm -rf -- "$FRONTEND_NODE_MODULES"'
    dist_reset = 'rm -rf -- "$FRONTEND_DIST"'
    cleanliness = 'git -C "$MANAGED_WORKTREE" status --porcelain'

    assert "frontend/control-center/node_modules/" in ignore
    assert (
        'FRONTEND_NODE_MODULES="${FRONTEND_ROOT}/node_modules"' in runner
    )
    assert 'FRONTEND_BUILD_SHA_FILE="${FRONTEND_DIST}/.jap-source-sha"' in runner
    assert dependency_reset in runner
    assert "JAP_WINDOWS_APP_FRONTEND_DEPENDENCIES=RESET" in runner
    assert runner.index(dependency_reset) < runner.index(cleanliness)
    assert dist_reset in runner
    assert "JAP_WINDOWS_APP_FRONTEND_DIST=RESET" in runner
    assert 'frontend_build_sha" == "$PINNED_SHA"' in runner
    assert "launcher=(python -u scripts/run_product_v1_live_demo.py --installed-runtime)" in runner
    assert "launcher+=(--reuse-frontend)" in runner


def test_desktop_host_is_self_contained_webview2_window() -> None:
    project = _text(DESKTOP_PROJECT)
    program = _text(DESKTOP_PROGRAM)
    assert "<OutputType>WinExe</OutputType>" in project
    assert "<UseWindowsForms>true</UseWindowsForms>" in project
    assert "<SelfContained>true</SelfContained>" in project
    assert 'PackageReference Include="Microsoft.Web.WebView2"' in project
    assert 'new("http://127.0.0.1:8780/")' in program
    assert "CoreWebView2" in program
    assert "MutexName" in program
    assert "Width = 1440" in program
    assert "MinimumSize = new Size(1180, 720)" in program
    assert '"-NoBrowser"' in program
    assert "RuntimeStartTimeout" in program
    assert 'Path.Combine(_installRoot, "Stop-JAP-Control-Center.ps1")' in program


def test_desktop_host_keeps_product_navigation_local_and_externalizes_links() -> None:
    program = _text(DESKTOP_PROGRAM)
    assert 'uri.Host == "127.0.0.1"' in program
    assert "uri.Port == 8780" in program
    assert "core.NavigationStarting += OnNavigationStarting" in program
    assert "core.NewWindowRequested += OnNewWindowRequested" in program
    assert "e.Cancel = true" in program
    assert "e.Handled = true" in program
    assert "UseShellExecute = true" in program


def test_installer_adopts_checksum_verified_immutable_desktop_release() -> None:
    installer = _text(INSTALLER)
    version = _text(DESKTOP_VERSION).strip()
    assert version.count(".") == 2
    assert 'tag = "jap-winapp-desktop-v$Version"' in installer
    assert "releases/download/$tag" in installer
    assert "Get-FileHash $zip -Algorithm SHA256" in installer
    assert "Expand-Archive -Path $zip" in installer
    assert 'desktop_host = "webview2_winforms"' in installer
    assert "desktop_host_sha256 = $desktopHost.sha256" in installer
    assert 'New-AppShortcut (Join-Path $desktop "JAP Control Center.lnk")' in installer
    assert "$DesktopHostExe \"\" \"$DesktopHostExe,0\"" in installer
    assert "Start-Process -FilePath $DesktopHostExe" in installer


def test_desktop_host_release_is_built_in_ci_and_immutable() -> None:
    workflow = _text(DESKTOP_RELEASE_WORKFLOW)
    assert "permissions:\n  contents: write" in workflow
    assert "dotnet publish windows/JAP.ControlCenter.Desktop/" in workflow
    assert "--self-contained true" in workflow
    assert "JAP-Control-Center-Desktop-win-x64.zip.sha256" in workflow
    assert "gh release create $env:DESKTOP_TAG" in workflow
    assert "--target $env:GITHUB_SHA" in workflow
    assert "bump VERSION before changing the host" in workflow
    assert "latest_direct" in workflow


def test_desktop_build_products_are_ignored() -> None:
    ignore = _text(GITIGNORE)
    assert "windows/JAP.ControlCenter.Desktop/bin/" in ignore
    assert "windows/JAP.ControlCenter.Desktop/obj/" in ignore
    assert "windows/JAP.ControlCenter.Desktop/JAP-Control-Center.ico" in ignore


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
    for path in (LAUNCHER, INSTALLER, UPDATER, STOPPER, APPLIER):
        lines = _text(path).splitlines()
        assert not any(line.rstrip().endswith("\\") for line in lines), path
