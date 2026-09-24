import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install-jap-control-center.ps1"
STOPPER = ROOT / "Stop-JAP-Control-Center.ps1"
WSL_INSTALLER = ROOT / "scripts" / "install_jap_windows_control_center.sh"
WSL_RUNNER = ROOT / "scripts" / "run_jap_windows_control_center.sh"
ICON_GENERATOR = ROOT / "scripts" / "generate_jap_control_center_icon.py"
DESKTOP_ROOT = ROOT / "windows" / "JAP.ControlCenter.Desktop"
DESKTOP_PROJECT = DESKTOP_ROOT / "JAP.ControlCenter.Desktop.csproj"
DESKTOP_PROGRAM = DESKTOP_ROOT / "Program.cs"
DESKTOP_RUNTIME = DESKTOP_ROOT / "ManagedRuntimeController.cs"
DESKTOP_VERSION = DESKTOP_ROOT / "VERSION"
DESKTOP_COMPATIBILITY = DESKTOP_ROOT / "UPDATE_COMPATIBILITY.json"
DESKTOP_RELEASE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "jap-windows-desktop-host-release.yml"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_windows_product_local_entrypoints_are_present() -> None:
    for path in (
        INSTALLER,
        STOPPER,
        WSL_INSTALLER,
        WSL_RUNNER,
        ICON_GENERATOR,
        DESKTOP_PROJECT,
        DESKTOP_PROGRAM,
        DESKTOP_RUNTIME,
        DESKTOP_VERSION,
        DESKTOP_COMPATIBILITY,
        DESKTOP_RELEASE_WORKFLOW,
    ):
        assert path.is_file(), path
    assert not (ROOT / "JAP-Control-Center.ps1").exists()


def test_bootstrap_bridge_is_per_user_and_installs_product_local_generation() -> None:
    text = _text(INSTALLER)
    assert 'Join-Path $env:LOCALAPPDATA "JAP-Control-Center"' in text
    assert 'job_application_pipeline.windows_control_center_install.v3' in text
    assert 'cgkb_product_local_v1' in text
    assert 'jap-winapp-product-v' in text
    assert 'JAP-Control-Center-Runtime.zip' in text
    assert 'wsl_runtime_root = $wslRuntimeRoot' in text
    assert 'wsl_runtime_runner_path = $wslRuntimeRunner' in text
    assert 'update_authority = "product_local_update_agent_v2"' in text
    assert 'New-AppShortcut (Join-Path $programs "Update JAP Control Center.lnk")' not in text
    assert 'JAP_CONTROL_CENTER_BOOTSTRAP_BRIDGE=PASS' in text
    assert 'Product runtime shell script contains CR bytes' in text


def test_bootstrap_bridge_does_not_assign_powershell_home_automatic_variable() -> None:
    text = _text(INSTALLER)
    assert not re.search(r"(?im)^\\s*\\$home\\s*=", text)
    assert '$wslHomeOutput = Invoke-Wsl @("-d", $WslDistro, "--exec", "bash", "-lc", \'printf "%s" "$HOME"\')' in text
    assert '$wslHome = (($wslHomeOutput | Select-Object -First 1) -as [string]).Trim()' in text


def test_bootstrap_bridge_does_not_copy_private_runtime_state() -> None:
    text = _text(INSTALLER)
    for forbidden in (
        'Copy-Item -Force "$PSScriptRoot\\.env"',
        'Copy-Item -Force "$PSScriptRoot\\private_application_sources"',
        "POSTGRES_PASSWORD=",
    ):
        assert forbidden not in text
    assert 'secrets_location = "wsl_project_env_only"' in text
    assert 'private_documents_location = "wsl_project_private_application_sources_only"' in text


def test_runtime_bundle_replaces_git_checkout_and_frontend_build_authority() -> None:
    runner = _text(WSL_RUNNER)
    assert 'RUNTIME_INFO="${RUNTIME_ROOT}/runtime-info.json"' in runner
    assert 'job_application_pipeline.runtime_bundle.v1' in runner
    assert '[[ "$runtime_source_sha" == "$PINNED_SHA" ]]' in runner
    assert 'FRONTEND_BUILD_SHA_FILE="${FRONTEND_DIST}/.jap-source-sha"' in runner
    assert '[[ "$frontend_build_sha" == "$PINNED_SHA" ]]' in runner
    assert 'source "$PROJECT_ROOT/.venv/bin/activate"' in runner
    assert 'source "$PROJECT_ROOT/.env"' in runner
    assert 'export PRODUCT_V1_PRIVATE_DOCUMENT_ROOT="$PROJECT_ROOT/private_application_sources"' in runner
    assert 'launcher=(python -u scripts/run_product_v1_live_demo.py --installed-runtime --reuse-frontend)' in runner
    assert "git -C" not in runner
    assert "git fetch" not in runner
    assert "npm ci" not in runner
    assert "npm install" not in runner
    assert "npm run build" not in runner
    assert '"prepare"' not in runner


def test_windows_runtime_uses_persisted_runtime_bundle_paths() -> None:
    runtime = _text(DESKTOP_RUNTIME)
    stopper = _text(STOPPER)
    assert 'GetString(root, "wsl_runtime_root")' in runtime
    assert 'GetString(root, "wsl_runtime_runner_path")' in runtime
    assert "config.RuntimeRoot" in runtime
    assert 'launch_mode = "desktop_native_wsl_runtime_bundle_v1"' in runtime
    assert 'wsl_runtime_root' in stopper
    assert 'wsl_runtime_runner_path' in stopper
    assert "managed_worktree" not in runtime
    assert "wsl_installed_runner_path" not in runtime


def test_desktop_host_is_self_contained_webview2_window() -> None:
    project = _text(DESKTOP_PROJECT)
    program = _text(DESKTOP_PROGRAM)
    runtime = _text(DESKTOP_RUNTIME)
    assert "<OutputType>WinExe</OutputType>" in project
    assert "<UseWindowsForms>true</UseWindowsForms>" in project
    assert "<SelfContained>true</SelfContained>" in project
    assert 'PackageReference Include="Microsoft.Web.WebView2"' in project
    assert 'new("http://127.0.0.1:8780/")' in program
    assert "CoreWebView2" in program
    assert "MutexName" in program
    assert "new Mutex(initiallyOwned: false, MutexName)" in program
    assert "mutex.WaitOne(0, false)" in program
    assert "catch (AbandonedMutexException)" in program
    assert "mutex.ReleaseMutex()" in program
    assert "out var createdNew" not in program
    assert "TryActivateExistingVisibleWindow" in program
    assert "mutex.WaitOne(LifecycleHandoffTimeout, false)" in program
    assert "IsProductUpdateHandoffInProgress" in program
    assert "accepted-update.json" in program
    assert "JAP Control Center ist bereits geöffnet." not in program
    assert "RuntimeStartTimeout" in program
    assert "_runtime.EnsureStartedAsync(RuntimeStartTimeout)" in program
    assert '"--exec"' in runtime
    assert '"bash"' in runtime
    assert '"launch"' in runtime
    assert "powershell.exe" not in program.lower()


def test_product_release_builds_immutable_desktop_and_runtime_assets() -> None:
    workflow = _text(DESKTOP_RELEASE_WORKFLOW)
    compatibility = _text(DESKTOP_COMPATIBILITY)
    assert "permissions:\n  contents: write" in workflow
    assert "jap-winapp-product-v$Version" in workflow
    assert "JAP-Control-Center-Desktop-win-x64.zip" in workflow
    assert "JAP-Control-Center-Runtime.zip" in workflow
    assert "runtime-info.json" in workflow
    assert r'Get-ChildItem -Force "frontend\control-center\dist" | Copy-Item -Destination $Frontend -Recurse -Force' in workflow
    assert 'Set-Content -Path (Join-Path $Frontend ".jap-source-sha") -Value $env:GITHUB_SHA -Encoding ASCII -NoNewline' in workflow
    assert "[System.IO.Compression.ZipFile]::CreateFromDirectory(" in workflow
    assert '"frontend/control-center/dist/.jap-source-sha"' in workflow
    assert "Compress-Archive" not in workflow
    assert "gh release list" in workflow
    assert "--json tagName" in workflow
    assert "gh release view $env:PRODUCT_TAG" not in workflow
    assert "gh release create $env:PRODUCT_TAG" in workflow
    assert "--target $env:GITHUB_SHA" in workflow
    assert '"schema": "job_application_pipeline.windows_update_compatibility.v2"' in compatibility
    assert '"policy": "product_local_latest_direct"' in compatibility
    assert '"installer_schema": "job_application_pipeline.windows_control_center_install.v3"' in compatibility
    assert '$Body = $Body.Replace("`r`n", "`n").Replace("`r", "`n")' in workflow
    assert "Runtime shell script still contains CR bytes" in workflow
    assert "Runtime release ZIP contains CR bytes" in workflow


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


def test_powershell_bootstrap_and_stop_do_not_use_bash_line_continuations() -> None:
    for path in (INSTALLER, STOPPER):
        lines = _text(path).splitlines()
        assert not any(line.rstrip().endswith("\\") for line in lines), path
