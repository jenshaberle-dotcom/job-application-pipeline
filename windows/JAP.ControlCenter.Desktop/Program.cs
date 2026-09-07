using System.Diagnostics;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace JAP.ControlCenter.Desktop;

internal static class Program
{
    private const string MutexName = @"Local\JAP.ControlCenter.Desktop";

    [STAThread]
    private static void Main()
    {
        using var mutex = new Mutex(initiallyOwned: true, MutexName, out var createdNew);
        if (!createdNew)
        {
            MessageBox.Show(
                "JAP Control Center ist bereits geöffnet.",
                "JAP Control Center",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            return;
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new MainWindow());
        GC.KeepAlive(mutex);
    }
}

internal sealed class MainWindow : Form
{
    private static readonly Uri ProductUri = new("http://127.0.0.1:8780/");
    private static readonly TimeSpan WebViewEnvironmentTimeout = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan WebViewControlTimeout = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan WebViewNavigationTimeout = TimeSpan.FromSeconds(15);

    private readonly string _installRoot;
    private readonly string _startupLog;
    private readonly WebView2 _webView;
    private readonly Label _status;
    private bool _allowClose;
    private bool _stopInProgress;

    public MainWindow()
    {
        var hostRoot = AppContext.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar);
        _installRoot = Directory.GetParent(hostRoot)?.FullName
            ?? throw new InvalidOperationException("Desktop host installation root could not be resolved.");
        _startupLog = Path.Combine(_installRoot, "logs", "desktop-host-startup.log");

        Text = "JAP Control Center";
        StartPosition = FormStartPosition.CenterScreen;
        Width = 1440;
        Height = 900;
        MinimumSize = new Size(1180, 720);
        BackColor = Color.FromArgb(7, 20, 34);

        _status = new Label
        {
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
            ForeColor = Color.FromArgb(207, 231, 245),
            BackColor = Color.FromArgb(7, 20, 34),
            Font = new Font("Segoe UI", 13, FontStyle.Regular),
            Text = "JAP Control Center wird gestartet …"
        };

        _webView = new WebView2
        {
            Dock = DockStyle.Fill,
            Visible = false
        };

        Controls.Add(_webView);
        Controls.Add(_status);
        Shown += OnShown;
        FormClosing += OnFormClosing;
    }

    private async void OnShown(object? sender, EventArgs e)
    {
        try
        {
            SetStartupPhase("runtime_start", "JAP Runtime wird gestartet …");
            await StartManagedRuntimeAsync();

            SetStartupPhase(
                "runtime_ready",
                "JAP Runtime ist bereit. Desktop-Oberfläche wird initialisiert …");
            await InitializeWebViewAsync();

            SetStartupPhase("ready", "JAP Control Center ist bereit.");
            _status.Visible = false;
            _webView.Visible = true;
            _webView.BringToFront();
        }
        catch (Exception exc)
        {
            WriteStartupPhase("startup_failed", exc.ToString());
            MessageBox.Show(
                this,
                $"JAP Control Center konnte nicht gestartet werden.\n\n{exc.Message}",
                "JAP Control Center",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            Close();
        }
    }

    private async Task StartManagedRuntimeAsync()
    {
        var launcher = Path.Combine(_installRoot, "JAP-Control-Center.ps1");
        if (!File.Exists(launcher))
        {
            throw new FileNotFoundException("Der installierte JAP Runtime-Launcher fehlt.", launcher);
        }

        var result = await RunPowerShellAsync(launcher, "-NoBrowser");
        if (result.ExitCode != 0)
        {
            throw new InvalidOperationException(
                "Managed Runtime-Start fehlgeschlagen. " + CompactDiagnostics(result));
        }
    }

    private async Task InitializeWebViewAsync()
    {
        string? runtimeVersion;
        try
        {
            runtimeVersion = CoreWebView2Environment.GetAvailableBrowserVersionString();
        }
        catch (WebView2RuntimeNotFoundException)
        {
            throw new InvalidOperationException(
                "Microsoft Edge WebView2 Runtime ist auf diesem Windows-System nicht verfügbar.");
        }

        if (string.IsNullOrWhiteSpace(runtimeVersion))
        {
            throw new InvalidOperationException(
                "Microsoft Edge WebView2 Runtime ist auf diesem Windows-System nicht verfügbar.");
        }

        WriteStartupPhase("webview_runtime_found", runtimeVersion);
        SetStartupPhase(
            "webview_environment_start",
            "WebView2-Umgebung wird vorbereitet …");

        var desktopVersion = ResolveDesktopHostVersion();
        var userDataFolder = Path.Combine(
            _installRoot,
            "state",
            "webview2",
            $"host-{desktopVersion}");
        Directory.CreateDirectory(userDataFolder);
        WriteStartupPhase("webview_profile", userDataFolder);

        CoreWebView2Environment environment;
        try
        {
            environment = await CoreWebView2Environment.CreateAsync(
                    browserExecutableFolder: null,
                    userDataFolder: userDataFolder)
                .WaitAsync(WebViewEnvironmentTimeout);
        }
        catch (TimeoutException)
        {
            throw new TimeoutException(
                $"WebView2-Umgebung wurde innerhalb von {WebViewEnvironmentTimeout.TotalSeconds:0} Sekunden nicht bereit.");
        }

        WriteStartupPhase("webview_environment_ready");
        SetStartupPhase(
            "webview_control_start",
            "WebView2-Fenster wird initialisiert …");

        try
        {
            await _webView.EnsureCoreWebView2Async(environment)
                .WaitAsync(WebViewControlTimeout);
        }
        catch (TimeoutException)
        {
            throw new TimeoutException(
                $"WebView2-Fenster wurde innerhalb von {WebViewControlTimeout.TotalSeconds:0} Sekunden nicht initialisiert.");
        }

        var core = _webView.CoreWebView2
            ?? throw new InvalidOperationException("WebView2 initialization completed without a CoreWebView2 instance.");
        WriteStartupPhase("webview_control_ready");

        core.Settings.AreDevToolsEnabled = false;
        core.Settings.IsStatusBarEnabled = false;
        core.Settings.AreDefaultContextMenusEnabled = false;
        core.Settings.AreBrowserAcceleratorKeysEnabled = false;
        core.NavigationStarting += OnNavigationStarting;
        core.NewWindowRequested += OnNewWindowRequested;

        SetStartupPhase(
            "product_navigation_start",
            "JAP Oberfläche wird geladen …");
        var navigation = new TaskCompletionSource<CoreWebView2NavigationCompletedEventArgs>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        void OnNavigationCompleted(
            object? navigationSender,
            CoreWebView2NavigationCompletedEventArgs args)
        {
            navigation.TrySetResult(args);
        }

        core.NavigationCompleted += OnNavigationCompleted;
        try
        {
            core.Navigate(ProductUri.AbsoluteUri);
            CoreWebView2NavigationCompletedEventArgs completed;
            try
            {
                completed = await navigation.Task.WaitAsync(WebViewNavigationTimeout);
            }
            catch (TimeoutException)
            {
                throw new TimeoutException(
                    $"JAP Oberfläche wurde innerhalb von {WebViewNavigationTimeout.TotalSeconds:0} Sekunden nicht geladen.");
            }

            if (!completed.IsSuccess)
            {
                throw new InvalidOperationException(
                    $"JAP Oberfläche konnte in WebView2 nicht geladen werden: {completed.WebErrorStatus}.");
            }
        }
        finally
        {
            core.NavigationCompleted -= OnNavigationCompleted;
        }

        WriteStartupPhase("product_navigation_ready");
    }

    private string ResolveDesktopHostVersion()
    {
        var buildInfo = Path.Combine(AppContext.BaseDirectory, "build-info.json");
        if (!File.Exists(buildInfo))
        {
            return "unknown";
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(buildInfo));
            if (document.RootElement.TryGetProperty("version", out var versionElement))
            {
                var version = versionElement.GetString();
                if (!string.IsNullOrWhiteSpace(version))
                {
                    return version.Trim();
                }
            }
        }
        catch (JsonException exc)
        {
            WriteStartupPhase("build_info_invalid", exc.Message);
        }

        return "unknown";
    }

    private void SetStartupPhase(string phase, string message)
    {
        _status.Text = message;
        _status.Refresh();
        WriteStartupPhase(phase, message);
    }

    private void WriteStartupPhase(string phase, string? detail = null)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_startupLog)!);
            var line = $"{DateTime.UtcNow:o}\t{phase}";
            if (!string.IsNullOrWhiteSpace(detail))
            {
                line += $"\t{detail.Replace("\r", " ").Replace("\n", " ")}";
            }
            File.AppendAllText(_startupLog, line + Environment.NewLine);
        }
        catch
        {
            // Startup diagnostics must never become a startup dependency.
        }
    }

    private void OnNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs e)
    {
        if (IsLocalProductUri(e.Uri))
        {
            return;
        }

        e.Cancel = true;
        OpenExternal(e.Uri);
    }

    private void OnNewWindowRequested(object? sender, CoreWebView2NewWindowRequestedEventArgs e)
    {
        e.Handled = true;
        if (IsLocalProductUri(e.Uri))
        {
            _webView.CoreWebView2?.Navigate(e.Uri);
            return;
        }

        OpenExternal(e.Uri);
    }

    private static bool IsLocalProductUri(string raw)
    {
        if (!Uri.TryCreate(raw, UriKind.Absolute, out var uri))
        {
            return false;
        }

        return uri.Scheme == Uri.UriSchemeHttp
            && uri.Host == "127.0.0.1"
            && uri.Port == 8780;
    }

    private static void OpenExternal(string raw)
    {
        if (!Uri.TryCreate(raw, UriKind.Absolute, out var uri))
        {
            return;
        }

        if (uri.Scheme is not ("http" or "https" or "mailto"))
        {
            return;
        }

        Process.Start(new ProcessStartInfo(uri.AbsoluteUri)
        {
            UseShellExecute = true
        });
    }

    private async void OnFormClosing(object? sender, FormClosingEventArgs e)
    {
        if (_allowClose)
        {
            return;
        }

        e.Cancel = true;
        if (_stopInProgress)
        {
            return;
        }

        _stopInProgress = true;
        Hide();
        try
        {
            var stopper = Path.Combine(_installRoot, "Stop-JAP-Control-Center.ps1");
            if (File.Exists(stopper))
            {
                var result = await RunPowerShellAsync(stopper);
                if (result.ExitCode != 0)
                {
                    MessageBox.Show(
                        "Das Fenster wird geschlossen, aber die verwaltete JAP Runtime konnte nicht sauber gestoppt werden.\n\n"
                        + CompactDiagnostics(result),
                        "JAP Control Center",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                }
            }
        }
        catch (Exception exc)
        {
            MessageBox.Show(
                $"Das Fenster wird geschlossen, aber beim Stoppen der JAP Runtime trat ein Fehler auf.\n\n{exc.Message}",
                "JAP Control Center",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
        }
        finally
        {
            _allowClose = true;
            Close();
        }
    }

    private async Task<ProcessResult> RunPowerShellAsync(string script, params string[] arguments)
    {
        var powershell = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe");
        if (!File.Exists(powershell))
        {
            throw new FileNotFoundException("Windows PowerShell wurde nicht gefunden.", powershell);
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = powershell,
            WorkingDirectory = _installRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-WindowStyle");
        startInfo.ArgumentList.Add("Hidden");
        startInfo.ArgumentList.Add("-File");
        startInfo.ArgumentList.Add(script);
        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        using var process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("Windows PowerShell process could not be created.");
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        return new ProcessResult(
            process.ExitCode,
            await stdoutTask,
            await stderrTask);
    }

    private static string CompactDiagnostics(ProcessResult result)
    {
        var raw = string.Join(
            " | ",
            new[] { result.StandardError, result.StandardOutput }
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Select(value => value.Trim().Replace("\r", " ").Replace("\n", " | ")));
        if (string.IsNullOrWhiteSpace(raw))
        {
            return $"ExitCode={result.ExitCode}";
        }

        const int limit = 1600;
        return raw.Length <= limit ? raw : raw[^limit..];
    }

    private sealed record ProcessResult(
        int ExitCode,
        string StandardOutput,
        string StandardError);
}
