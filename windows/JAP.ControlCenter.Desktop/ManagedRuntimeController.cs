using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JAP.ControlCenter.Desktop;

internal sealed class ManagedRuntimeController : IDisposable
{
    private const long ExpectedRepositoryId = 1230805345;
    private const string ExpectedRepository = "jenshaberle-dotcom/job-application-pipeline";
    private const int Port = 8780;
    private const int DatabasePort = 5432;
    private const string DockerContainerName = "job_pipeline_postgres";
    private static readonly TimeSpan DockerDesktopStartupTimeout = TimeSpan.FromSeconds(90);
    private static readonly TimeSpan DatabaseStartupTimeout = TimeSpan.FromSeconds(30);
    private static readonly Regex ShaPattern =
        new("^[0-9a-f]{40}$", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private readonly string _installRoot;
    private readonly HttpClient _http = new()
    {
        Timeout = TimeSpan.FromSeconds(3)
    };

    public ManagedRuntimeController(string installRoot)
    {
        _installRoot = Path.GetFullPath(installRoot);
    }

    public async Task EnsureStartedAsync(TimeSpan timeout)
    {
        var config = ReadConfig(_installRoot);
        NormalizeInstalledRuntimeShellScripts(_installRoot, config);
        await EnsureDatabaseRuntimeAsync(config);

        var endpoint = await ProbeEndpointAsync(config.PinnedSha);
        if (endpoint.Healthy)
        {
            return;
        }

        if (endpoint.IsJap)
        {
            var stopResult = await StopAsync(TimeSpan.FromSeconds(20));
            if (stopResult.ExitCode != 0)
            {
                throw new InvalidOperationException(
                    "Veraltete JAP Runtime konnte nicht gestoppt werden. "
                    + CompactDiagnostics(stopResult));
            }

            var releaseDeadline = DateTimeOffset.UtcNow.AddSeconds(10);
            while (DateTimeOffset.UtcNow < releaseDeadline && await IsPortOpenAsync(Port))
            {
                await Task.Delay(250);
            }

            if (await IsPortOpenAsync(Port))
            {
                throw new InvalidOperationException(
                    $"Die veraltete JAP Runtime hat Port {Port} nicht freigegeben.");
            }
        }
        else if (await IsPortOpenAsync(Port))
        {
            throw new InvalidOperationException(
                $"Port {Port} ist bereits durch einen anderen Dienst belegt.");
        }

        var wsl = ResolveWsl();
        var runnerProof = await RunProcessAsync(
            wsl,
            TimeSpan.FromSeconds(10),
            "-d",
            config.WslDistro,
            "--exec",
            "test",
            "-f",
            config.WslRunner);
        if (runnerProof.ExitCode != 0)
        {
            throw new InvalidOperationException(
                "Installierter JAP WSL-Runner ist nicht verfügbar. "
                + CompactDiagnostics(runnerProof));
        }

        var stateRoot = config.WslStateRoot.TrimEnd('/');
        var stdout = $"{stateRoot}/runtime.stdout.log";
        var stderr = $"{stateRoot}/runtime.stderr.log";
        var launch = await RunProcessAsync(
            wsl,
            TimeSpan.FromSeconds(20),
            "-d",
            config.WslDistro,
            "--exec",
            "bash",
            config.WslRunner,
            config.WslProjectRoot,
            config.RuntimeRoot,
            config.PinnedSha,
            config.WslStateRoot,
            "launch",
            stdout,
            stderr);
        if (launch.ExitCode != 0)
        {
            var failedLaunchStderr = await ReadLinuxTailAsync(wsl, config.WslDistro, stderr);
            var failedLaunchStdout = await ReadLinuxTailAsync(wsl, config.WslDistro, stdout);
            var detachedDiagnostics = string.Join(
                " | ",
                new[] { failedLaunchStderr, failedLaunchStdout }
                    .Where(value => !string.IsNullOrWhiteSpace(value)));
            throw new InvalidOperationException(
                "Direkter JAP WSL-Runtime-Handoff fehlgeschlagen. "
                + CompactDiagnostics(launch)
                + (string.IsNullOrWhiteSpace(detachedDiagnostics)
                    ? string.Empty
                    : " | Runtime: " + detachedDiagnostics));
        }

        WriteRuntimeState(config);

        var readinessBudgetSeconds = Math.Clamp(timeout.TotalSeconds - 10, 5, 75);
        var readinessDeadline = DateTimeOffset.UtcNow.AddSeconds(readinessBudgetSeconds);
        string? lastError = endpoint.Error;
        while (DateTimeOffset.UtcNow < readinessDeadline)
        {
            await Task.Delay(500);
            endpoint = await ProbeEndpointAsync(config.PinnedSha);
            lastError = endpoint.Error;
            if (endpoint.Healthy)
            {
                return;
            }
        }

        var stderrTail = await ReadLinuxTailAsync(wsl, config.WslDistro, stderr);
        if (!string.IsNullOrWhiteSpace(stderrTail))
        {
            throw new InvalidOperationException(
                "JAP Runtime wurde nicht bereit: " + stderrTail);
        }

        var stdoutTail = await ReadLinuxTailAsync(wsl, config.WslDistro, stdout);
        if (!string.IsNullOrWhiteSpace(stdoutTail))
        {
            throw new InvalidOperationException(
                "JAP Runtime wurde nicht bereit: " + stdoutTail);
        }

        if (!string.IsNullOrWhiteSpace(lastError))
        {
            throw new InvalidOperationException(
                "JAP Runtime wurde nicht bereit. Letzter Endpoint-Fehler: " + lastError);
        }

        throw new InvalidOperationException(
            $"JAP Runtime wurde nicht bereit. WSL-Logs: {stdout} und {stderr}.");
    }

    public async Task<ProcessResult> StopAsync(TimeSpan timeout)
    {
        var config = ReadConfig(_installRoot);
        NormalizeInstalledRuntimeShellScripts(_installRoot, config);
        var wsl = ResolveWsl();
        return await RunProcessAsync(
            wsl,
            timeout,
            "-d",
            config.WslDistro,
            "--exec",
            "bash",
            config.WslRunner,
            config.WslProjectRoot,
            config.RuntimeRoot,
            config.PinnedSha,
            config.WslStateRoot,
            "--stop");
    }

    public static void StopBestEffortSynchronously(string installRoot, TimeSpan timeout)
    {
        var config = ReadConfig(installRoot);
        NormalizeInstalledRuntimeShellScripts(installRoot, config);
        var wsl = ResolveWsl();
        var startInfo = BuildProcessStartInfo(
            wsl,
            "-d",
            config.WslDistro,
            "--exec",
            "bash",
            config.WslRunner,
            config.WslProjectRoot,
            config.RuntimeRoot,
            config.PinnedSha,
            config.WslStateRoot,
            "--stop");
        startInfo.RedirectStandardOutput = false;
        startInfo.RedirectStandardError = false;

        using var process = Process.Start(startInfo);
        if (process is null)
        {
            return;
        }

        if (!process.WaitForExit((int)Math.Clamp(timeout.TotalMilliseconds, 1000, int.MaxValue)))
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch
            {
                // Fail-closed exit remains the authority.
            }
        }
    }

    public static string CompactDiagnostics(ProcessResult result)
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

    private async Task EnsureDatabaseRuntimeAsync(RuntimeConfig config)
    {
        if (await IsPortOpenAsync(DatabasePort))
        {
            return;
        }

        var wsl = ResolveWsl();
        var dockerReady = await DockerDaemonReadyAsync(wsl, config.WslDistro);
        if (!dockerReady)
        {
            StartDockerDesktop();
            var dockerDeadline = DateTimeOffset.UtcNow.Add(DockerDesktopStartupTimeout);
            while (DateTimeOffset.UtcNow < dockerDeadline)
            {
                await Task.Delay(1000);
                if (await DockerDaemonReadyAsync(wsl, config.WslDistro))
                {
                    dockerReady = true;
                    break;
                }
            }
        }

        if (!dockerReady)
        {
            throw new InvalidOperationException(
                "Docker Desktop wurde nicht rechtzeitig bereit. "
                + "JAP benötigt den lokalen PostgreSQL-Container job_pipeline_postgres.");
        }

        var startResult = await RunProcessAsync(
            wsl,
            TimeSpan.FromSeconds(15),
            "-d",
            config.WslDistro,
            "--exec",
            "docker",
            "start",
            DockerContainerName);
        if (startResult.ExitCode != 0)
        {
            throw new InvalidOperationException(
                "Der kanonische JAP PostgreSQL-Container konnte nicht gestartet werden. "
                + CompactDiagnostics(startResult));
        }

        var databaseDeadline = DateTimeOffset.UtcNow.Add(DatabaseStartupTimeout);
        while (DateTimeOffset.UtcNow < databaseDeadline)
        {
            if (await IsPortOpenAsync(DatabasePort))
            {
                return;
            }

            await Task.Delay(500);
        }

        throw new InvalidOperationException(
            $"JAP PostgreSQL wurde auf Port {DatabasePort} nicht bereit.");
    }

    private static async Task<bool> DockerDaemonReadyAsync(string wsl, string distro)
    {
        try
        {
            var result = await RunProcessAsync(
                wsl,
                TimeSpan.FromSeconds(5),
                "-d",
                distro,
                "--exec",
                "docker",
                "info");
            return result.ExitCode == 0;
        }
        catch (TimeoutException)
        {
            return false;
        }
    }

    private static void StartDockerDesktop()
    {
        var dockerDesktop = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            "Docker",
            "Docker",
            "Docker Desktop.exe");
        if (!File.Exists(dockerDesktop))
        {
            throw new FileNotFoundException(
                "Docker Desktop ist für die lokale JAP PostgreSQL-Runtime erforderlich.",
                dockerDesktop);
        }

        try
        {
            _ = Process.Start(new ProcessStartInfo
            {
                FileName = dockerDesktop,
                WorkingDirectory = Path.GetDirectoryName(dockerDesktop)!,
                UseShellExecute = true
            });
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException(
                "Docker Desktop konnte aus JAP nicht gestartet werden.",
                exc);
        }
    }

    private async Task<EndpointState> ProbeEndpointAsync(string expectedSha)
    {
        try
        {
            using var response = await _http.GetAsync($"http://127.0.0.1:{Port}/app-info.json");
            if (!response.IsSuccessStatusCode)
            {
                return new EndpointState(false, false, string.Empty, $"HTTP {(int)response.StatusCode}");
            }

            using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            var sourceRevision = GetString(document.RootElement, "source_revision")
                .Trim()
                .ToLowerInvariant();
            var isJap = ShaPattern.IsMatch(sourceRevision);
            return new EndpointState(
                isJap && sourceRevision == expectedSha,
                isJap,
                sourceRevision,
                null);
        }
        catch (Exception exc) when (
            exc is HttpRequestException
                or TaskCanceledException
                or JsonException
                or IOException)
        {
            return new EndpointState(false, false, string.Empty, exc.Message);
        }
    }

    private static async Task<bool> IsPortOpenAsync(int port)
    {
        using var client = new TcpClient();
        using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(500));
        try
        {
            await client.ConnectAsync(IPAddress.Loopback, port, cts.Token);
            return true;
        }
        catch (Exception exc) when (
            exc is SocketException
                or OperationCanceledException)
        {
            return false;
        }
    }

    private static void NormalizeInstalledRuntimeShellScripts(
        string installRoot,
        RuntimeConfig config)
    {
        var runtimeRoot = Path.Combine(Path.GetFullPath(installRoot), "runtime");
        var infoPath = Path.Combine(runtimeRoot, "runtime-info.json");
        if (!File.Exists(infoPath))
        {
            throw new FileNotFoundException(
                "Installierte JAP Runtime-Identität fehlt.",
                infoPath);
        }

        using (var info = JsonDocument.Parse(File.ReadAllText(infoPath)))
        {
            var root = info.RootElement;
            if (GetString(root, "schema") != "job_application_pipeline.runtime_bundle.v1"
                || !GetString(root, "source_sha").Equals(
                    config.PinnedSha,
                    StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    "Installierte JAP Runtime-Identität stimmt nicht mit current.json überein.");
            }
        }

        var scriptsRoot = Path.Combine(runtimeRoot, "scripts");
        if (!Directory.Exists(scriptsRoot))
        {
            throw new DirectoryNotFoundException(
                "Installierter JAP Runtime-Scriptpfad fehlt.");
        }

        var utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        foreach (var shellScript in Directory.EnumerateFiles(
                     scriptsRoot,
                     "*.sh",
                     SearchOption.AllDirectories))
        {
            var bytes = File.ReadAllBytes(shellScript);
            if (!bytes.Contains((byte)'\r'))
            {
                continue;
            }

            var body = File.ReadAllText(shellScript, Encoding.UTF8)
                .Replace("\r\n", "\n", StringComparison.Ordinal)
                .Replace("\r", "\n", StringComparison.Ordinal);
            var temporary = shellScript + $".lf-repair.{Environment.ProcessId}.tmp";
            File.WriteAllText(temporary, body, utf8NoBom);
            File.Move(temporary, shellScript, overwrite: true);

            if (File.ReadAllBytes(shellScript).Contains((byte)'\r'))
            {
                throw new InvalidOperationException(
                    $"Installiertes JAP Runtime-Shellscript enthält weiterhin CR-Bytes: {shellScript}");
            }
        }
    }

    private static RuntimeConfig ReadConfig(string installRoot)
    {
        var currentPath = Path.Combine(Path.GetFullPath(installRoot), "current.json");
        if (!File.Exists(currentPath))
        {
            throw new FileNotFoundException("JAP Installationsmetadaten fehlen.", currentPath);
        }

        using var document = JsonDocument.Parse(File.ReadAllText(currentPath));
        var root = document.RootElement;
        var repositoryId = root.TryGetProperty("repository_id", out var repositoryIdElement)
            ? repositoryIdElement.GetInt64()
            : 0;
        var repository = GetString(root, "repository");
        var pinnedSha = GetString(root, "pinned_sha").Trim().ToLowerInvariant();
        var wslDistro = GetString(root, "wsl_distro").Trim();
        var projectRoot = GetString(root, "wsl_project_root").Trim();
        var runtimeRoot = GetString(root, "wsl_runtime_root").Trim();
        var stateRoot = GetString(root, "wsl_state_root").Trim();
        var runner = GetString(root, "wsl_runtime_runner_path").Trim();
        var port = root.TryGetProperty("port", out var portElement)
            ? portElement.GetInt32()
            : 0;

        if (GetString(root, "schema") != "job_application_pipeline.windows_control_center_install.v3")
        {
            throw new InvalidOperationException("JAP Installationsschema ist nicht die CGKB product-local Generation.");
        }
        if (GetString(root, "update_generation") != "cgkb_product_local_v1")
        {
            throw new InvalidOperationException("JAP Update-Generation stimmt nicht.");
        }
        if (repositoryId != ExpectedRepositoryId || repository != ExpectedRepository)
        {
            throw new InvalidOperationException("JAP Repository-Identität stimmt nicht.");
        }
        if (!ShaPattern.IsMatch(pinnedSha))
        {
            throw new InvalidOperationException("Installierter JAP Source-Pin ist ungültig.");
        }
        if (string.IsNullOrWhiteSpace(wslDistro))
        {
            throw new InvalidOperationException("Installierte JAP WSL-Distribution fehlt.");
        }
        foreach (var value in new[] { projectRoot, runtimeRoot, stateRoot, runner })
        {
            if (string.IsNullOrWhiteSpace(value) || !value.StartsWith('/'))
            {
                throw new InvalidOperationException(
                    "Installierte JAP WSL-Pfade sind unvollständig oder ungültig.");
            }
        }
        if (port != Port)
        {
            throw new InvalidOperationException(
                $"Installierter JAP Port {port} entspricht nicht dem Produktport {Port}.");
        }

        return new RuntimeConfig(
            pinnedSha,
            wslDistro,
            projectRoot,
            runtimeRoot,
            stateRoot,
            runner);
    }

    private void WriteRuntimeState(RuntimeConfig config)
    {
        var path = Path.Combine(_installRoot, "state", "runtime.json");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(
            temporary,
            JsonSerializer.Serialize(
                new
                {
                    repository_id = ExpectedRepositoryId,
                    launch_mode = "desktop_native_wsl_runtime_bundle_v1",
                    pinned_sha = config.PinnedSha,
                    started_at = DateTimeOffset.UtcNow.ToString("O"),
                    uri = $"http://127.0.0.1:{Port}/"
                },
                new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, path, overwrite: true);
    }

    private static async Task<string> ReadLinuxTailAsync(
        string wsl,
        string distro,
        string path)
    {
        var result = await RunProcessAsync(
            wsl,
            TimeSpan.FromSeconds(5),
            "-d",
            distro,
            "--exec",
            "tail",
            "-n",
            "12",
            path);
        return result.ExitCode == 0
            ? result.StandardOutput.Trim().Replace("\r", " ").Replace("\n", " | ")
            : string.Empty;
    }

    private static string ResolveWsl()
    {
        var wsl = Path.Combine(Environment.SystemDirectory, "wsl.exe");
        if (!File.Exists(wsl))
        {
            throw new FileNotFoundException(
                "WSL ist für JAP erforderlich, wurde aber nicht gefunden.",
                wsl);
        }

        return wsl;
    }

    private static ProcessStartInfo BuildProcessStartInfo(
        string executable,
        params string[] arguments)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = executable,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        return startInfo;
    }

    private static async Task<ProcessResult> RunProcessAsync(
        string executable,
        TimeSpan timeout,
        params string[] arguments)
    {
        var stdout = new ConcurrentQueue<string>();
        var stderr = new ConcurrentQueue<string>();
        using var process = new Process
        {
            StartInfo = BuildProcessStartInfo(executable, arguments)
        };
        process.OutputDataReceived += (_, args) =>
        {
            if (args.Data is { } line)
            {
                stdout.Enqueue(line);
            }
        };
        process.ErrorDataReceived += (_, args) =>
        {
            if (args.Data is { } line)
            {
                stderr.Enqueue(line);
            }
        };

        if (!process.Start())
        {
            throw new InvalidOperationException($"Prozess konnte nicht gestartet werden: {executable}");
        }

        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        try
        {
            await process.WaitForExitAsync().WaitAsync(timeout);
            await Task.Delay(50);
        }
        catch (TimeoutException)
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch
            {
                // Preserve timeout truth even if cleanup fails.
            }

            try
            {
                await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(5));
            }
            catch
            {
                // Do not turn cleanup into an unbounded wait.
            }

            throw;
        }
        finally
        {
            TryCancelRedirectedRead(process);
        }

        return new ProcessResult(
            process.ExitCode,
            string.Join(Environment.NewLine, stdout),
            string.Join(Environment.NewLine, stderr));
    }

    private static void TryCancelRedirectedRead(Process process)
    {
        try
        {
            process.CancelOutputRead();
        }
        catch
        {
            // Stream already closed.
        }

        try
        {
            process.CancelErrorRead();
        }
        catch
        {
            // Stream already closed.
        }
    }

    private static string GetString(JsonElement root, string property)
    {
        return root.TryGetProperty(property, out var value)
            ? value.GetString() ?? string.Empty
            : string.Empty;
    }

    public void Dispose()
    {
        _http.Dispose();
    }

    private sealed record RuntimeConfig(
        string PinnedSha,
        string WslDistro,
        string WslProjectRoot,
        string RuntimeRoot,
        string WslStateRoot,
        string WslRunner);

    private sealed record EndpointState(
        bool Healthy,
        bool IsJap,
        string SourceRevision,
        string? Error);

    internal sealed record ProcessResult(
        int ExitCode,
        string StandardOutput,
        string StandardError);
}
