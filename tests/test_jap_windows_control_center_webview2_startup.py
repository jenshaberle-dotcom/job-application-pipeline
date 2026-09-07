from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "Program.cs"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def _program() -> str:
    return PROGRAM.read_text(encoding="utf-8")


def test_webview2_startup_is_bounded_and_phase_visible() -> None:
    program = _program()
    assert "WebViewEnvironmentTimeout = TimeSpan.FromSeconds(20)" in program
    assert "WebViewControlTimeout = TimeSpan.FromSeconds(20)" in program
    assert "WebViewNavigationTimeout = TimeSpan.FromSeconds(15)" in program
    assert ".WaitAsync(WebViewEnvironmentTimeout)" in program
    assert ".WaitAsync(WebViewControlTimeout)" in program
    assert "navigation.Task.WaitAsync(WebViewNavigationTimeout)" in program
    assert 'SetStartupPhase("runtime_start"' in program
    assert 'SetStartupPhase("runtime_ready"' in program
    assert 'SetStartupPhase("webview_environment_start"' in program
    assert 'SetStartupPhase("webview_control_start"' in program
    assert 'SetStartupPhase("product_navigation_start"' in program
    assert 'WriteStartupPhase("startup_failed"' in program


def test_webview2_profile_is_isolated_by_desktop_host_version() -> None:
    program = _program()
    assert 'Path.Combine(AppContext.BaseDirectory, "build-info.json")' in program
    assert 'ResolveDesktopHostVersion()' in program
    assert '"webview2",' in program
    assert '$"host-{desktopVersion}"' in program
    assert 'WriteStartupPhase("webview_profile"' in program


def test_webview2_navigation_is_proven_before_splash_is_hidden() -> None:
    program = _program()
    navigation_ready = program.index('WriteStartupPhase("product_navigation_ready")')
    splash_hidden = program.index("_status.Visible = false")
    assert navigation_ready < splash_hidden
    assert "CoreWebView2NavigationCompletedEventArgs" in program
    assert "completed.IsSuccess" in program


def test_webview2_hardening_bumps_immutable_host_version() -> None:
    assert VERSION.read_text(encoding="utf-8").strip() == "1.0.2"
