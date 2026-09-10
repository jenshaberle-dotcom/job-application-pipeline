from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "Program.cs"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"


def _program() -> str:
    return PROGRAM.read_text(encoding="utf-8")


def test_webview2_startup_is_bounded_and_phase_visible() -> None:
    program = _program()
    assert "RuntimeStartTimeout = TimeSpan.FromSeconds(90)" in program
    assert "WebViewEnvironmentTimeout = TimeSpan.FromSeconds(20)" in program
    assert "WebViewControlTimeout = TimeSpan.FromSeconds(20)" in program
    assert "WebViewNavigationTimeout = TimeSpan.FromSeconds(15)" in program
    assert "RuntimeStartTimeout," in program
    assert ".WaitAsync(WebViewEnvironmentTimeout)" in program
    assert ".WaitAsync(WebViewControlTimeout)" in program
    assert "navigation.Task.WaitAsync(WebViewNavigationTimeout)" in program
    assert "process.Kill(entireProcessTree: true)" in program
    for phase in (
        "runtime_start",
        "runtime_ready",
        "webview_environment_start",
        "webview_control_start",
        "product_navigation_start",
    ):
        assert f'"{phase}"' in program
    assert 'WriteStartupPhase("startup_failed"' in program


def test_startup_screen_shows_phase_progress_and_elapsed_time() -> None:
    program = _program()
    assert "private readonly ProgressBar _progress" in program
    assert "private readonly Label _phaseLabel" in program
    assert "private readonly Label _elapsed" in program
    assert "private readonly System.Windows.Forms.Timer _elapsedTimer" in program
    assert 'Text = "JAP Control Center wird vorbereitet"' in program
    assert '"Schritt 1 von 5 · JAP Runtime starten"' in program
    assert '"Schritt 2 von 5 · Runtime bereit"' in program
    assert '"Schritt 3 von 5 · Desktop-Engine vorbereiten"' in program
    assert '"Schritt 4 von 5 · Desktop-Fenster initialisieren"' in program
    assert '"Schritt 5 von 5 · JAP Oberfläche laden"' in program
    assert '"Bereit · JAP Control Center"' in program
    assert "ProgressBarStyle.Continuous" in program
    assert "_progress.Value = Math.Clamp" in program
    assert 'Text = "Verstrichene Zeit 00:00"' in program
    assert "_elapsedTimer.Start()" in program
    assert "UpdateElapsedLabel()" in program


def test_redirected_powershell_io_cannot_outlive_parent_unbounded() -> None:
    program = _program()
    assert "ConcurrentQueue<string>" in program
    assert "process.BeginOutputReadLine()" in program
    assert "process.BeginErrorReadLine()" in program
    assert "TryCancelRedirectedRead(process)" in program
    assert "process.CancelOutputRead()" in program
    assert "process.CancelErrorRead()" in program
    assert "ReadToEndAsync" not in program
    assert ".WaitAsync(timeoutValue)" in program
    assert ".WaitAsync(TimeSpan.FromSeconds(5))" in program


def test_webview2_profile_is_isolated_by_desktop_host_version() -> None:
    program = _program()
    assert 'Path.Combine(AppContext.BaseDirectory, "build-info.json")' in program
    assert "ResolveDesktopHostVersion()" in program
    assert '"webview2",' in program
    assert '$"host-{desktopVersion}"' in program
    assert 'WriteStartupPhase("webview_profile"' in program


def test_webview2_navigation_is_proven_before_splash_is_hidden() -> None:
    program = _program()
    on_shown_start = program.index("private async void OnShown")
    on_shown_end = program.index("private async Task StartManagedRuntimeAsync")
    on_shown = program[on_shown_start:on_shown_end]
    assert on_shown.index("await InitializeWebViewAsync();") < on_shown.index(
        "_startupPanel.Visible = false"
    )
    assert 'WriteStartupPhase("product_navigation_ready")' in program
    assert "CoreWebView2NavigationCompletedEventArgs" in program
    assert "completed.IsSuccess" in program


def test_webview2_hardening_bumps_immutable_host_version() -> None:
    assert VERSION.read_text(encoding="utf-8").strip() == "1.0.19"
