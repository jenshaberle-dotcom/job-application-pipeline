using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JAP.ControlCenter.Desktop;

internal static class ProductUpdateApplier
{
    private const string AcceptedSchema = "job_application_pipeline.windows_pending_update.v1";
    private const string InstallSchema = "job_application_pipeline.windows_control_center_install.v2";
    private const string ResultSchema = "job_application_pipeline.windows_update_result.v1";
    private static readonly Regex ShaPattern = new("^[0-9a-f]{40}$", RegexOptions.CultureInvariant);
    private static readonly Regex DigestPattern = new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant);

    public static int RunFromCommandLine(string[] args)
    {
        var installRoot = ResolveArg(args, "--install-root");
        var hostPidText = ResolveArg(args, "--host-pid");
        var stateRoot = Path.Combine(installRoot, "state");
        var acceptedPath = Path.Combine(stateRoot, "accepted-update.json");
        var resultPath = Path.Combine(stateRoot, "update-result.json");
        var logPath = Path.Combine(installRoot, "logs", "product-update-applier.log");
        string? backup = null;
        string? targetSha = null;
        string? targetVersion = null;
        try
        {
            if (int.TryParse(hostPidText, out var hostPid) && hostPid > 0)
            {
                try
                {
                    using var host = Process.GetProcessById(hostPid);
                    if (!host.WaitForExit(30_000))
                    {
                        throw new InvalidOperationException("Running JAP host did not exit before update cutover.");
                    }
                }
                catch (ArgumentException) { }
            }

            using var accepted = JsonDocument.Parse(File.ReadAllText(acceptedPath));
            var root = accepted.RootElement;
            Require(Get(root, "schema") == AcceptedSchema, "Accepted update schema mismatch.");
            Require(Get(root, "installer_schema") == InstallSchema, "Accepted installer schema mismatch.");
            Require(Get(root, "compatibility_line") == "1", "Accepted compatibility line mismatch.");
            Require(Get(root, "policy") == "latest_direct", "Accepted update policy mismatch.");
            targetSha = Get(root, "target_main_sha").ToLowerInvariant();
            targetVersion = Get(root, "target_desktop_version");
            var archive = Get(root, "desktop_archive");
            var expectedHash = Get(root, "desktop_sha256").ToLowerInvariant();
            Require(ShaPattern.IsMatch(targetSha), "Accepted target SHA is invalid.");
            Require(Version.TryParse(targetVersion, out var version) && version.Major == 1, "Accepted version is invalid.");
            Require(DigestPattern.IsMatch(expectedHash), "Accepted checksum is invalid.");
            Require(File.Exists(archive), "Accepted staged archive is missing.");
            Require(ComputeSha256(archive) == expectedHash, "Accepted staged archive checksum mismatch.");

            var stage = Path.Combine(installRoot, "updates", targetSha, "apply");
            if (Directory.Exists(stage)) Directory.Delete(stage, true);
            Directory.CreateDirectory(stage);
            ZipFile.ExtractToDirectory(archive, stage);
            var buildInfoPath = Path.Combine(stage, "build-info.json");
            Require(File.Exists(buildInfoPath), "Staged build identity is missing.");
            using (var build = JsonDocument.Parse(File.ReadAllText(buildInfoPath)))
            {
                Require(Get(build.RootElement, "source_sha").ToLowerInvariant() == targetSha, "Staged source identity mismatch.");
                Require(Get(build.RootElement, "version") == targetVersion, "Staged version identity mismatch.");
                Require(Get(build.RootElement, "compatibility_line") == "1", "Staged compatibility identity mismatch.");
            }
            Require(File.Exists(Path.Combine(stage, "JAP.ControlCenter.Desktop.exe")), "Staged desktop executable is missing.");

            var desktop = Path.Combine(installRoot, "desktop-host");
            backup = Path.Combine(installRoot, "rollback", $"desktop-host-{DateTimeOffset.UtcNow:yyyyMMddHHmmss}");
            Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
            if (Directory.Exists(desktop)) Directory.Move(desktop, backup);
            Directory.Move(stage, desktop);

            var currentPath = Path.Combine(installRoot, "current.json");
            using var currentDoc = JsonDocument.Parse(File.ReadAllText(currentPath));
            var current = new Dictionary<string, object?>();
            foreach (var property in currentDoc.RootElement.EnumerateObject())
            {
                current[property.Name] = JsonSerializer.Deserialize<object>(property.Value.GetRawText());
            }
            current["pinned_sha"] = targetSha;
            current["desktop_host_version"] = targetVersion;
            WriteJsonAtomic(currentPath, current);

            var exe = Path.Combine(desktop, "JAP.ControlCenter.Desktop.exe");
            var process = Process.Start(new ProcessStartInfo { FileName = exe, WorkingDirectory = installRoot, UseShellExecute = true })
                ?? throw new InvalidOperationException("Updated JAP host could not be restarted.");
            Thread.Sleep(2500);
            Require(!process.HasExited, "Updated JAP host exited during verification.");
            using var verified = JsonDocument.Parse(File.ReadAllText(currentPath));
            Require(Get(verified.RootElement, "pinned_sha").ToLowerInvariant() == targetSha, "Installed source verification failed.");
            Require(Get(verified.RootElement, "desktop_host_version") == targetVersion, "Installed version verification failed.");

            WriteResult(resultPath, "success", targetSha, targetVersion, "verified");
            File.Delete(acceptedPath);
            var pending = Path.Combine(stateRoot, "pending-update.json");
            if (File.Exists(pending)) File.Delete(pending);
            WriteLog(logPath, "apply_success", $"version={targetVersion} sha={targetSha}");
            CleanupOldUpdates(installRoot, targetSha);
            return 0;
        }
        catch (Exception exc)
        {
            try
            {
                var desktop = Path.Combine(installRoot, "desktop-host");
                if (!string.IsNullOrWhiteSpace(backup) && Directory.Exists(backup))
                {
                    if (Directory.Exists(desktop)) Directory.Delete(desktop, true);
                    Directory.Move(backup, desktop);
                    var oldExe = Path.Combine(desktop, "JAP.ControlCenter.Desktop.exe");
                    if (File.Exists(oldExe)) Process.Start(new ProcessStartInfo { FileName = oldExe, WorkingDirectory = installRoot, UseShellExecute = true });
                }
                WriteResult(resultPath, "failed", targetSha ?? "", targetVersion ?? "", exc.Message);
                WriteLog(logPath, "apply_failed", exc.ToString());
            }
            catch { }
            return 2;
        }
    }

    private static void CleanupOldUpdates(string root, string keepSha)
    {
        var updates = Path.Combine(root, "updates");
        if (!Directory.Exists(updates)) return;
        foreach (var directory in Directory.EnumerateDirectories(updates))
        {
            var name = Path.GetFileName(directory);
            if (name.Equals(keepSha, StringComparison.OrdinalIgnoreCase) || name == "apply-helper") continue;
            try { Directory.Delete(directory, true); } catch { }
        }
    }

    private static string ResolveArg(string[] args, string name)
    {
        for (var i = 0; i < args.Length - 1; i++) if (args[i].Equals(name, StringComparison.OrdinalIgnoreCase)) return Path.GetFullPath(args[i + 1]);
        throw new InvalidOperationException($"Missing required argument {name}.");
    }

    private static string Get(JsonElement root, string name) => root.TryGetProperty(name, out var value) ? value.GetString() ?? "" : "";
    private static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
    private static string ComputeSha256(string path) { using var stream = File.OpenRead(path); return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant(); }
    private static void WriteResult(string path, string status, string sha, string version, string detail) => WriteJsonAtomic(path, new { schema = ResultSchema, status, target_main_sha = sha, target_desktop_version = version, detail, completed_at = DateTimeOffset.UtcNow.ToString("O") });
    private static void WriteJsonAtomic(string path, object value) { Directory.CreateDirectory(Path.GetDirectoryName(path)!); var tmp = path + ".tmp"; File.WriteAllText(tmp, JsonSerializer.Serialize(value, new JsonSerializerOptions { WriteIndented = true })); File.Move(tmp, path, true); }
    private static void WriteLog(string path, string phase, string detail) { Directory.CreateDirectory(Path.GetDirectoryName(path)!); File.AppendAllText(path, $"{DateTimeOffset.UtcNow:O}\t{phase}\t{detail.Replace("\r"," ").Replace("\n"," ")}{Environment.NewLine}"); }
}
