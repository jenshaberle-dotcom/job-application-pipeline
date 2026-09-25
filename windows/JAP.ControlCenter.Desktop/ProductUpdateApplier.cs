using System.Diagnostics;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JAP.ControlCenter.Desktop;

internal static class ProductUpdateApplier
{
    private const string AcceptedSchema = "job_application_pipeline.windows_product_update.v2";
    private const string InstallSchema = "job_application_pipeline.windows_control_center_install.v3";
    private const string ResultSchema = "job_application_pipeline.windows_update_result.v2";
    private const string SnoozeSchema = "job_application_pipeline.windows_update_snooze.v1";
    private const string CompatibilityLine = "cgkb-product-local-1";
    private const string Policy = "product_local_latest_direct";
    private const string UpdateGeneration = "cgkb_product_local_v1";
    private const int ProductPort = 8780;
    private static readonly TimeSpan FailureRetryDelay = TimeSpan.FromMinutes(10);
    private static readonly TimeSpan MoveRetryWindow = TimeSpan.FromSeconds(45);
    private static readonly Regex ShaPattern = new("^[0-9a-f]{40}$", RegexOptions.CultureInvariant);
    private static readonly Regex DigestPattern = new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant);

    public static int RunFromCommandLine(string[] args)
    {
        var installRoot = ResolveArg(args, "--install-root");
        var hostPidText = ResolveArg(args, "--host-pid");
        var stateRoot = Path.Combine(installRoot, "state");
        var acceptedPath = Path.Combine(stateRoot, "accepted-update.json");
        var pendingPath = Path.Combine(stateRoot, "pending-update.json");
        var resultPath = Path.Combine(stateRoot, "update-result.json");
        var snoozePath = Path.Combine(stateRoot, "update-snooze.json");
        var logPath = Path.Combine(installRoot, "logs", "product-update-applier.log");
        var currentPath = Path.Combine(installRoot, "current.json");
        var desktopLive = Path.Combine(installRoot, "desktop-host");
        var runtimeLive = Path.Combine(installRoot, "runtime");

        string? targetSha = null;
        string? targetVersion = null;
        string? previousCurrentJson = null;
        string? rollbackRoot = null;
        string? desktopBackup = null;
        string? runtimeBackup = null;
        Process? restarted = null;
        var desktopMoved = false;
        var runtimeMoved = false;

        try
        {
            WriteLog(logPath, "apply_begin", $"host_pid={hostPidText}");
            WriteLog(logPath, "host_exit_wait_begin", $"host_pid={hostPidText}");
            WaitForHostExit(hostPidText);
            WriteLog(logPath, "host_exit_wait_complete", $"host_pid={hostPidText}");

            using var accepted = JsonDocument.Parse(File.ReadAllText(acceptedPath));
            var root = accepted.RootElement;
            Require(Get(root, "schema") == AcceptedSchema, "Accepted update schema mismatch.");
            Require(Get(root, "installer_schema") == InstallSchema, "Accepted installer schema mismatch.");
            Require(Get(root, "compatibility_line") == CompatibilityLine, "Accepted compatibility line mismatch.");
            Require(Get(root, "policy") == Policy, "Accepted update policy mismatch.");
            Require(Get(root, "update_generation") == UpdateGeneration, "Accepted update generation mismatch.");

            targetSha = Get(root, "target_main_sha").ToLowerInvariant();
            targetVersion = Get(root, "target_desktop_version");
            var targetRelease = Get(root, "target_release_tag");
            Require(ShaPattern.IsMatch(targetSha), "Accepted target SHA is invalid.");
            Require(Version.TryParse(targetVersion, out var version) && version >= new Version(1, 0, 62), "Accepted version is invalid.");

            var updateRoot = Path.Combine(installRoot, "updates", targetSha);
            var desktopStage = ProductUpdateIntegrity.RequirePathUnder(
                updateRoot, Get(root, "desktop_stage"), "Accepted desktop stage escaped managed update root.");
            var runtimeStage = ProductUpdateIntegrity.RequirePathUnder(
                updateRoot, Get(root, "runtime_stage"), "Accepted runtime stage escaped managed update root.");
            var helperRoot = ProductUpdateIntegrity.RequirePathUnder(
                updateRoot, Get(root, "apply_helper_root"), "Accepted helper escaped managed update root.");
            var helperExecutable = ProductUpdateIntegrity.RequirePathUnder(
                helperRoot, Get(root, "apply_helper_executable"), "Accepted helper executable escaped helper root.");

            var desktopTreeSha = Get(root, "desktop_tree_sha256").ToLowerInvariant();
            var runtimeTreeSha = Get(root, "runtime_tree_sha256").ToLowerInvariant();
            var helperTreeSha = Get(root, "apply_helper_tree_sha256").ToLowerInvariant();
            foreach (var digest in new[] { desktopTreeSha, runtimeTreeSha, helperTreeSha })
            {
                Require(DigestPattern.IsMatch(digest), "Accepted staged tree digest is invalid.");
            }

            Require(Directory.Exists(desktopStage), "Accepted desktop stage is missing.");
            Require(Directory.Exists(runtimeStage), "Accepted runtime stage is missing.");
            Require(Directory.Exists(helperRoot) && File.Exists(helperExecutable), "Accepted apply helper is missing.");
            Require(ProductUpdateIntegrity.ComputeDirectorySha256(desktopStage) == desktopTreeSha, "Accepted desktop stage integrity mismatch.");
            Require(ProductUpdateIntegrity.ComputeDirectorySha256(runtimeStage) == runtimeTreeSha, "Accepted runtime stage integrity mismatch.");
            Require(ProductUpdateIntegrity.ComputeDirectorySha256(helperRoot) == helperTreeSha, "Accepted apply helper integrity mismatch.");

            VerifyDesktopStage(desktopStage, targetSha, targetVersion);
            VerifyRuntimeStage(runtimeStage, targetSha, targetVersion);

            previousCurrentJson = File.ReadAllText(currentPath);
            using (var currentDoc = JsonDocument.Parse(previousCurrentJson))
            {
                Require(Get(currentDoc.RootElement, "schema") == InstallSchema, "Installed JAP schema changed before cutover.");
                Require(Get(currentDoc.RootElement, "update_generation") == UpdateGeneration, "Installed JAP generation changed before cutover.");
            }

            rollbackRoot = Path.Combine(
                installRoot,
                "rollback",
                $"product-{DateTimeOffset.UtcNow:yyyyMMddHHmmss}-{Environment.ProcessId}");
            desktopBackup = Path.Combine(rollbackRoot, "desktop-host");
            runtimeBackup = Path.Combine(rollbackRoot, "runtime");
            Directory.CreateDirectory(rollbackRoot);

            WriteLog(logPath, "cutover_begin", $"target={targetVersion} sha={targetSha}");
            if (Directory.Exists(desktopLive))
            {
                MoveDirectoryWithRetry(desktopLive, desktopBackup, logPath, "desktop_live_to_backup");
            }
            MoveDirectoryWithRetry(desktopStage, desktopLive, logPath, "desktop_stage_to_live");
            desktopMoved = true;

            if (Directory.Exists(runtimeLive))
            {
                MoveDirectoryWithRetry(runtimeLive, runtimeBackup, logPath, "runtime_live_to_backup");
            }
            MoveDirectoryWithRetry(runtimeStage, runtimeLive, logPath, "runtime_stage_to_live");
            runtimeMoved = true;

            VerifyDesktopStage(desktopLive, targetSha, targetVersion);
            VerifyRuntimeStage(runtimeLive, targetSha, targetVersion);
            Require(
                ProductUpdateIntegrity.ComputeDirectorySha256(desktopLive) == desktopTreeSha,
                "Live desktop tree integrity mismatch after cutover.");
            Require(
                ProductUpdateIntegrity.ComputeDirectorySha256(runtimeLive) == runtimeTreeSha,
                "Live runtime tree integrity mismatch after cutover.");
            WriteLog(logPath, "cutover_live_verified", $"target={targetVersion} sha={targetSha}");
            WriteLog(logPath, "cutover_complete", $"target={targetVersion} sha={targetSha}");

            using (var currentDoc = JsonDocument.Parse(previousCurrentJson))
            {
                var current = new Dictionary<string, object?>();
                foreach (var property in currentDoc.RootElement.EnumerateObject())
                {
                    current[property.Name] = JsonSerializer.Deserialize<object>(property.Value.GetRawText());
                }
                current["schema"] = InstallSchema;
                current["pinned_sha"] = targetSha;
                current["desktop_host_version"] = targetVersion;
                current["desktop_host_release"] = targetRelease;
                current["desktop_host_tree_sha256"] = desktopTreeSha;
                current["runtime_tree_sha256"] = runtimeTreeSha;
                current["compatibility_line"] = CompatibilityLine;
                current["update_generation"] = UpdateGeneration;
                current["update_authority"] = "product_local_update_agent_v2";
                current["installed_at"] = DateTimeOffset.UtcNow.ToString("O");
                WriteJsonAtomic(currentPath, current);
            }

            var exe = Path.Combine(desktopLive, "JAP.ControlCenter.Desktop.exe");
            Require(File.Exists(exe), "Installed desktop executable is missing after cutover.");
            WriteLog(logPath, "restart_begin", $"exe={exe}");
            restarted = Process.Start(new ProcessStartInfo
            {
                FileName = exe,
                WorkingDirectory = installRoot,
                UseShellExecute = true
            }) ?? throw new InvalidOperationException("Updated JAP host could not be restarted.");
            WriteLog(logPath, "restart_started", $"pid={restarted.Id} target={targetVersion}");

            WriteLog(logPath, "restart_verify_begin", $"pid={restarted.Id} sha={targetSha}");
            VerifyRestartedProduct(restarted, targetSha, TimeSpan.FromSeconds(105));
            WriteLog(logPath, "restart_verify_complete", $"pid={restarted.Id} sha={targetSha}");

            using (var verified = JsonDocument.Parse(File.ReadAllText(currentPath)))
            {
                Require(Get(verified.RootElement, "pinned_sha").ToLowerInvariant() == targetSha, "Installed source verification failed.");
                Require(Get(verified.RootElement, "desktop_host_version") == targetVersion, "Installed version verification failed.");
                Require(Get(verified.RootElement, "update_generation") == UpdateGeneration, "Installed generation verification failed.");
            }

            WriteResult(resultPath, "success", targetSha, targetVersion, "runtime_verified");
            TryDelete(acceptedPath);
            TryDelete(pendingPath);
            TryDelete(snoozePath);
            WriteLog(logPath, "apply_success", $"version={targetVersion} sha={targetSha}");
            TryDeleteDirectory(rollbackRoot);
            CleanupOldUpdates(installRoot, targetSha);
            return 0;
        }
        catch (Exception exc)
        {
            try
            {
                if (restarted is not null && !restarted.HasExited)
                {
                    try
                    {
                        restarted.CloseMainWindow();
                        if (!restarted.WaitForExit(25_000))
                        {
                            restarted.Kill(entireProcessTree: true);
                            restarted.WaitForExit(5_000);
                        }
                    }
                    catch { }
                }

                if (runtimeMoved)
                {
                    if (Directory.Exists(runtimeLive)) Directory.Delete(runtimeLive, true);
                    if (!string.IsNullOrWhiteSpace(runtimeBackup) && Directory.Exists(runtimeBackup))
                    {
                        MoveDirectoryWithRetry(runtimeBackup, runtimeLive, logPath, "rollback_runtime_backup_to_live");
                    }
                }

                if (desktopMoved)
                {
                    if (Directory.Exists(desktopLive)) Directory.Delete(desktopLive, true);
                    if (!string.IsNullOrWhiteSpace(desktopBackup) && Directory.Exists(desktopBackup))
                    {
                        MoveDirectoryWithRetry(desktopBackup, desktopLive, logPath, "rollback_desktop_backup_to_live");
                    }
                }

                if (!string.IsNullOrWhiteSpace(previousCurrentJson))
                {
                    var temporary = currentPath + ".rollback.tmp";
                    File.WriteAllText(temporary, previousCurrentJson);
                    File.Move(temporary, currentPath, true);
                }

                TryDelete(acceptedPath);
                TryDelete(pendingPath);
                WriteResult(resultPath, "failed", targetSha ?? string.Empty, targetVersion ?? string.Empty, exc.Message);
                WriteFailureSnooze(
                    snoozePath,
                    targetSha ?? string.Empty,
                    targetVersion ?? string.Empty,
                    DateTimeOffset.UtcNow.Add(FailureRetryDelay));
                WriteLog(
                    logPath,
                    "apply_failed",
                    $"{exc} retry_suppressed_until={DateTimeOffset.UtcNow.Add(FailureRetryDelay):O}");

                var oldExe = Path.Combine(desktopLive, "JAP.ControlCenter.Desktop.exe");
                if (File.Exists(oldExe))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = oldExe,
                        WorkingDirectory = installRoot,
                        UseShellExecute = true
                    });
                }
            }
            catch (Exception rollbackExc)
            {
                try { WriteLog(logPath, "rollback_failed", rollbackExc.ToString()); } catch { }
            }
            return 2;
        }
    }

    private static void MoveDirectoryWithRetry(
        string source,
        string destination,
        string logPath,
        string operation)
    {
        var deadline = DateTimeOffset.UtcNow.Add(MoveRetryWindow);
        var attempt = 0;
        while (true)
        {
            try
            {
                Directory.Move(source, destination);
                if (attempt > 0)
                {
                    WriteLog(
                        logPath,
                        "move_retry_recovered",
                        $"operation={operation} attempts={attempt + 1}");
                }
                return;
            }
            catch (Exception exc) when (
                IsTransientMoveFailure(exc)
                && DateTimeOffset.UtcNow < deadline)
            {
                attempt += 1;
                WriteLog(
                    logPath,
                    "move_retry",
                    $"operation={operation} attempt={attempt} type={exc.GetType().Name} "
                    + $"hresult=0x{exc.HResult:X8} error={exc.Message}");
                Thread.Sleep(Math.Min(1000, 150 + (attempt * 100)));
            }
        }
    }

    private static bool IsTransientMoveFailure(Exception exc)
    {
        if (exc is UnauthorizedAccessException)
        {
            return true;
        }

        return exc is IOException io && IsTransientSharingViolation(io);
    }

    private static bool IsTransientSharingViolation(IOException exc)
    {
        var nativeCode = exc.HResult & 0xFFFF;
        return nativeCode is 5 or 32 or 33;
    }

    private static void WaitForHostExit(string hostPidText)
    {
        if (!int.TryParse(hostPidText, out var hostPid) || hostPid <= 0) return;
        try
        {
            using var host = Process.GetProcessById(hostPid);
            if (!host.WaitForExit(30_000))
            {
                throw new InvalidOperationException("Running JAP host did not exit before update cutover.");
            }
        }
        catch (ArgumentException)
        {
            // Host already exited.
        }
    }

    private static void VerifyRestartedProduct(Process process, string targetSha, TimeSpan timeout)
    {
        using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
        var deadline = DateTimeOffset.UtcNow.Add(timeout);
        string? last = null;
        while (DateTimeOffset.UtcNow < deadline)
        {
            if (process.HasExited)
            {
                throw new InvalidOperationException($"Updated JAP host exited during verification with code {process.ExitCode}.");
            }

            try
            {
                using var response = client.GetAsync($"http://127.0.0.1:{ProductPort}/app-info.json")
                    .GetAwaiter().GetResult();
                if (response.IsSuccessStatusCode)
                {
                    using var document = JsonDocument.Parse(
                        response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
                    var source = Get(document.RootElement, "source_revision").Trim().ToLowerInvariant();
                    if (source == targetSha) return;
                    last = $"source_revision={source}";
                }
                else
                {
                    last = $"http={(int)response.StatusCode}";
                }
            }
            catch (Exception probeExc) when (
                probeExc is HttpRequestException
                    or TaskCanceledException
                    or JsonException
                    or IOException)
            {
                last = probeExc.Message;
            }

            Thread.Sleep(500);
        }

        throw new InvalidOperationException(
            "Updated JAP runtime did not prove exact target identity after restart."
            + (string.IsNullOrWhiteSpace(last) ? string.Empty : $" Last probe: {last}"));
    }

    private static void VerifyDesktopStage(string stage, string sourceSha, string version)
    {
        var buildInfoPath = Path.Combine(stage, "build-info.json");
        Require(File.Exists(buildInfoPath), "Staged desktop build identity is missing.");
        using var build = JsonDocument.Parse(File.ReadAllText(buildInfoPath));
        var root = build.RootElement;
        Require(Get(root, "schema") == "job_application_pipeline.desktop_host_build.v2", "Staged desktop build schema mismatch.");
        Require(Get(root, "source_sha").Equals(sourceSha, StringComparison.OrdinalIgnoreCase), "Staged desktop source identity mismatch.");
        Require(Get(root, "version") == version, "Staged desktop version identity mismatch.");
        Require(Get(root, "compatibility_line") == CompatibilityLine, "Staged desktop compatibility identity mismatch.");
        Require(Get(root, "update_generation") == UpdateGeneration, "Staged desktop generation identity mismatch.");
    }

    private static void VerifyRuntimeStage(string stage, string sourceSha, string version)
    {
        var infoPath = Path.Combine(stage, "runtime-info.json");
        Require(File.Exists(infoPath), "Staged runtime identity is missing.");
        using var info = JsonDocument.Parse(File.ReadAllText(infoPath));
        var root = info.RootElement;
        Require(Get(root, "schema") == "job_application_pipeline.runtime_bundle.v1", "Staged runtime schema mismatch.");
        Require(Get(root, "source_sha").Equals(sourceSha, StringComparison.OrdinalIgnoreCase), "Staged runtime source identity mismatch.");
        Require(Get(root, "version") == version, "Staged runtime version identity mismatch.");
        Require(Get(root, "compatibility_line") == CompatibilityLine, "Staged runtime compatibility identity mismatch.");
        Require(Get(root, "update_generation") == UpdateGeneration, "Staged runtime generation identity mismatch.");
        var scriptsRoot = Path.Combine(stage, "scripts");
        Require(Directory.Exists(scriptsRoot), "Staged runtime scripts directory is missing.");
        foreach (var shellScript in Directory.EnumerateFiles(
                     scriptsRoot,
                     "*.sh",
                     SearchOption.AllDirectories))
        {
            Require(
                !File.ReadAllBytes(shellScript).Contains((byte)'\r'),
                $"Staged runtime shell script contains CR bytes: {shellScript}");
        }
        Require(File.Exists(Path.Combine(stage, "vendor", "codex", "codex")), "Staged bundled Codex executable is missing.");
        Require(File.Exists(Path.Combine(stage, "vendor", "codex", "codex-info.json")), "Staged bundled Codex identity is missing.");
        var marker = Path.Combine(stage, "frontend", "control-center", "dist", ".jap-source-sha");
        Require(File.Exists(marker), "Staged frontend source marker is missing.");
        Require(File.ReadAllText(marker).Trim().Equals(sourceSha, StringComparison.OrdinalIgnoreCase), "Staged frontend source marker mismatch.");
    }

    private static void CleanupOldUpdates(string root, string keepSha)
    {
        var updates = Path.Combine(root, "updates");
        if (!Directory.Exists(updates)) return;
        foreach (var directory in Directory.EnumerateDirectories(updates))
        {
            var name = Path.GetFileName(directory);
            if (name.Equals(keepSha, StringComparison.OrdinalIgnoreCase)) continue;
            TryDeleteDirectory(directory);
        }
    }

    private static string ResolveArg(string[] args, string name)
    {
        for (var index = 0; index < args.Length - 1; index++)
        {
            if (args[index].Equals(name, StringComparison.OrdinalIgnoreCase))
            {
                return Path.GetFullPath(args[index + 1]);
            }
        }
        throw new InvalidOperationException($"Missing required argument {name}.");
    }

    private static string Get(JsonElement root, string name) =>
        root.TryGetProperty(name, out var value) ? value.GetString() ?? string.Empty : string.Empty;

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void WriteResult(string path, string status, string sha, string version, string detail) =>
        WriteJsonAtomic(path, new
        {
            schema = ResultSchema,
            status,
            target_main_sha = sha,
            target_desktop_version = version,
            detail,
            completed_at = DateTimeOffset.UtcNow.ToString("O")
        });

    private static void WriteFailureSnooze(
        string path,
        string targetSha,
        string targetVersion,
        DateTimeOffset until)
    {
        if (!ShaPattern.IsMatch(targetSha)
            || !Version.TryParse(targetVersion, out _))
        {
            return;
        }

        WriteJsonAtomic(
            path,
            new
            {
                schema = SnoozeSchema,
                snooze_until_utc = until.ToString("O"),
                target_main_sha = targetSha,
                target_desktop_version = targetVersion,
                reason = "apply_failed_retry_cooldown"
            });
    }

    private static void WriteJsonAtomic(string path, object value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(
            temporary,
            JsonSerializer.Serialize(value, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, path, true);
    }

    private static void WriteLog(string path, string phase, string detail)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.AppendAllText(
            path,
            $"{DateTimeOffset.UtcNow:O}\t{phase}\t{detail.Replace("\r", " ").Replace("\n", " ")}{Environment.NewLine}");
    }

    private static void TryDelete(string path)
    {
        try { if (File.Exists(path)) File.Delete(path); } catch { }
    }

    private static void TryDeleteDirectory(string? path)
    {
        try
        {
            if (!string.IsNullOrWhiteSpace(path) && Directory.Exists(path))
            {
                Directory.Delete(path, true);
            }
        }
        catch { }
    }
}
