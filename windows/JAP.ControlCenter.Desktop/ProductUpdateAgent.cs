using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JAP.ControlCenter.Desktop;

internal static class ProductUpdateAgent
{
    private const long ExpectedRepositoryId = 1230805345;
    private const string ExpectedRepository = "jenshaberle-dotcom/job-application-pipeline";
    private const string InstallSchema = "job_application_pipeline.windows_control_center_install.v3";
    private const string PendingSchema = "job_application_pipeline.windows_product_update.v2";
    private const string CompatibilityLine = "cgkb-product-local-1";
    private const string Policy = "product_local_latest_direct";
    private const string UpdateGeneration = "cgkb_product_local_v1";
    private const string ReleasePrefix = "jap-winapp-product-v";
    private const string DesktopArchiveName = "JAP-Control-Center-Desktop-win-x64.zip";
    private const string DesktopChecksumName = "JAP-Control-Center-Desktop-win-x64.zip.sha256";
    private const string RuntimeArchiveName = "JAP-Control-Center-Runtime.zip";
    private const string RuntimeChecksumName = "JAP-Control-Center-Runtime.zip.sha256";
    private const string StagingProvider = "product_local_update_agent_v2";
    private static readonly Version MinimumDirectVersion = new(1, 0, 65);
    private static readonly Regex ShaPattern = new("^[0-9a-fA-F]{40}$", RegexOptions.CultureInvariant);
    private static readonly Regex DigestPattern = new("^[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant);

    public static async Task<int> RunFromCommandLineAsync(string[] args)
    {
        var installRoot = ResolveInstallRoot(args);
        var logPath = Path.Combine(installRoot, "logs", "product-update-agent.log");
        using var stageMutex = new Mutex(
            initiallyOwned: false,
            BuildStageMutexName(installRoot));
        var ownsStageMutex = false;
        try
        {
            try
            {
                ownsStageMutex = stageMutex.WaitOne(0, false);
            }
            catch (AbandonedMutexException)
            {
                ownsStageMutex = true;
                WriteLog(logPath, "stage_lock_recovered", $"install_root={installRoot}");
            }

            if (!ownsStageMutex)
            {
                WriteLog(logPath, "stage_skipped", "reason=stage_already_running");
                return 0;
            }

            Directory.CreateDirectory(Path.GetDirectoryName(logPath)!);
            WriteLog(logPath, "stage_begin", $"install_root={installRoot}");
            var result = await StageLatestAsync(installRoot, logPath);
            WriteLog(logPath, "stage_complete", $"result={result}");
            return 0;
        }
        catch (Exception exc)
        {
            try { WriteLog(logPath, "stage_failed", exc.ToString()); } catch { }
            return 2;
        }
        finally
        {
            if (ownsStageMutex)
            {
                stageMutex.ReleaseMutex();
            }
        }
    }

    private static async Task<string> StageLatestAsync(string installRoot, string logPath)
    {
        var currentPath = Path.Combine(installRoot, "current.json");
        if (!File.Exists(currentPath))
        {
            throw new InvalidOperationException("JAP current installation metadata is missing.");
        }

        using var currentDocument = JsonDocument.Parse(await File.ReadAllTextAsync(currentPath));
        var current = currentDocument.RootElement;
        Require(GetString(current, "schema") == InstallSchema, "Installed JAP schema is not product-local-update compatible.");
        Require(current.TryGetProperty("repository_id", out var repositoryId)
            && repositoryId.GetInt64() == ExpectedRepositoryId
            && GetString(current, "repository") == ExpectedRepository,
            "Installed JAP repository identity does not match update authority.");
        Require(GetString(current, "update_generation") == UpdateGeneration,
            "Installed JAP update generation does not match product-local authority.");
        Require(Version.TryParse(GetString(current, "desktop_host_version"), out var installedVersion)
            && installedVersion >= MinimumDirectVersion,
            "Installed JAP version requires the explicit bootstrap bridge.");

        using var client = new HttpClient { Timeout = TimeSpan.FromMinutes(3) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("JAP-Product-Update-Agent/2.0");
        client.DefaultRequestHeaders.Accept.ParseAdd("application/vnd.github+json");
        client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");

        using (var repositoryResponse = await client.GetAsync(
            "https://api.github.com/repos/jenshaberle-dotcom/job-application-pipeline"))
        {
            repositoryResponse.EnsureSuccessStatusCode();
            using var repositoryDocument = JsonDocument.Parse(
                await repositoryResponse.Content.ReadAsStringAsync());
            Require(repositoryDocument.RootElement.TryGetProperty("id", out var id)
                && id.GetInt64() == ExpectedRepositoryId,
                "GitHub repository identity mismatch.");
        }

        using var releasesResponse = await client.GetAsync(
            "https://api.github.com/repos/jenshaberle-dotcom/job-application-pipeline/releases?per_page=100");
        releasesResponse.EnsureSuccessStatusCode();
        using var releasesDocument = JsonDocument.Parse(await releasesResponse.Content.ReadAsStringAsync());

        ReleaseCandidate? selected = null;
        foreach (var release in releasesDocument.RootElement.EnumerateArray())
        {
            if (GetBool(release, "draft") || GetBool(release, "prerelease")) continue;
            var tag = GetString(release, "tag_name");
            if (!tag.StartsWith(ReleasePrefix, StringComparison.Ordinal)) continue;
            var versionText = tag[ReleasePrefix.Length..];
            if (!Version.TryParse(versionText, out var version)
                || version < MinimumDirectVersion
                || version <= installedVersion)
            {
                continue;
            }

            var sourceSha = GetString(release, "target_commitish");
            if (!ShaPattern.IsMatch(sourceSha)) continue;

            var assets = new Dictionary<string, string>(StringComparer.Ordinal);
            if (release.TryGetProperty("assets", out var assetArray))
            {
                foreach (var asset in assetArray.EnumerateArray())
                {
                    var name = GetString(asset, "name");
                    var url = GetString(asset, "browser_download_url");
                    if (!string.IsNullOrWhiteSpace(name) && !string.IsNullOrWhiteSpace(url))
                    {
                        assets[name] = url;
                    }
                }
            }

            if (!assets.ContainsKey(DesktopArchiveName)
                || !assets.ContainsKey(DesktopChecksumName)
                || !assets.ContainsKey(RuntimeArchiveName)
                || !assets.ContainsKey(RuntimeChecksumName))
            {
                continue;
            }

            if (selected is null || version > selected.Version)
            {
                selected = new ReleaseCandidate(
                    version,
                    tag,
                    sourceSha.ToLowerInvariant(),
                    assets[DesktopArchiveName],
                    assets[DesktopChecksumName],
                    assets[RuntimeArchiveName],
                    assets[RuntimeChecksumName]);
            }
        }

        if (selected is null) return "no_update";

        var updateRoot = Path.Combine(installRoot, "updates", selected.SourceSha);
        var payloadRoot = Path.Combine(updateRoot, "payload");
        var desktopStage = Path.Combine(updateRoot, "desktop-staged");
        var runtimeStage = Path.Combine(updateRoot, "runtime-staged");
        var helperRoot = Path.Combine(updateRoot, "apply-helper");
        Directory.CreateDirectory(payloadRoot);

        var desktopArchive = Path.Combine(payloadRoot, DesktopArchiveName);
        var desktopChecksum = Path.Combine(payloadRoot, DesktopChecksumName);
        var runtimeArchive = Path.Combine(payloadRoot, RuntimeArchiveName);
        var runtimeChecksum = Path.Combine(payloadRoot, RuntimeChecksumName);

        var desktopArchiveSha = await PrepareArchiveAsync(
            client, selected.DesktopArchiveUrl, selected.DesktopChecksumUrl, desktopArchive, desktopChecksum);
        var runtimeArchiveSha = await PrepareArchiveAsync(
            client, selected.RuntimeArchiveUrl, selected.RuntimeChecksumUrl, runtimeArchive, runtimeChecksum);

        ExtractFresh(desktopArchive, desktopStage);
        ExtractFresh(runtimeArchive, runtimeStage);
        VerifyDesktopStage(desktopStage, selected.SourceSha, selected.Version.ToString());
        VerifyRuntimeStage(runtimeStage, selected.SourceSha, selected.Version.ToString());

        DeleteDirectory(helperRoot);
        CopyDirectory(AppContext.BaseDirectory, helperRoot);
        var helperExecutable = Path.Combine(helperRoot, "JAP.ControlCenter.Desktop.exe");
        Require(File.Exists(helperExecutable), "Product-local apply helper executable is missing.");

        var desktopTreeSha = ProductUpdateIntegrity.ComputeDirectorySha256(desktopStage);
        var runtimeTreeSha = ProductUpdateIntegrity.ComputeDirectorySha256(runtimeStage);
        var helperTreeSha = ProductUpdateIntegrity.ComputeDirectorySha256(helperRoot);

        var pendingPath = Path.Combine(installRoot, "state", "pending-update.json");
        await WriteJsonAtomicAsync(
            pendingPath,
            new
            {
                schema = PendingSchema,
                target_main_sha = selected.SourceSha,
                target_desktop_version = selected.Version.ToString(),
                target_release_tag = selected.Tag,
                compatibility_line = CompatibilityLine,
                installer_schema = InstallSchema,
                policy = Policy,
                update_generation = UpdateGeneration,
                desktop_archive = desktopArchive,
                desktop_archive_sha256 = desktopArchiveSha,
                runtime_archive = runtimeArchive,
                runtime_archive_sha256 = runtimeArchiveSha,
                desktop_stage = desktopStage,
                desktop_tree_sha256 = desktopTreeSha,
                runtime_stage = runtimeStage,
                runtime_tree_sha256 = runtimeTreeSha,
                apply_helper_root = helperRoot,
                apply_helper_executable = helperExecutable,
                apply_helper_tree_sha256 = helperTreeSha,
                staging_provider = StagingProvider,
                staged_at = DateTimeOffset.UtcNow.ToString("O")
            });

        WriteLog(
            logPath,
            "pending_published",
            $"version={selected.Version} sha={selected.SourceSha} provider={StagingProvider}");
        return $"staged:{selected.Version}";
    }

    private static async Task<string> PrepareArchiveAsync(
        HttpClient client,
        string archiveUrl,
        string checksumUrl,
        string archivePath,
        string checksumPath)
    {
        var checksumText = (await client.GetStringAsync(checksumUrl)).Trim();
        var expectedHash = checksumText.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)
            .FirstOrDefault()?.Trim().ToLowerInvariant() ?? string.Empty;
        Require(DigestPattern.IsMatch(expectedHash), "Published JAP release checksum is invalid.");
        await WriteTextAtomicAsync(checksumPath, checksumText + Environment.NewLine);

        var archiveReady = File.Exists(archivePath)
            && string.Equals(
                ProductUpdateIntegrity.ComputeFileSha256(archivePath),
                expectedHash,
                StringComparison.OrdinalIgnoreCase);
        if (!archiveReady)
        {
            var temporaryArchive = archivePath + $".download.{Environment.ProcessId}";
            try
            {
                if (File.Exists(temporaryArchive)) File.Delete(temporaryArchive);
                await DownloadArchiveAsync(client, archiveUrl, temporaryArchive);
                Require(
                    string.Equals(
                        ProductUpdateIntegrity.ComputeFileSha256(temporaryArchive),
                        expectedHash,
                        StringComparison.OrdinalIgnoreCase),
                    "Downloaded JAP release checksum verification failed.");
                File.Move(temporaryArchive, archivePath, overwrite: true);
            }
            finally
            {
                if (File.Exists(temporaryArchive)) File.Delete(temporaryArchive);
            }
        }

        Require(
            string.Equals(
                ProductUpdateIntegrity.ComputeFileSha256(archivePath),
                expectedHash,
                StringComparison.OrdinalIgnoreCase),
            "Staged JAP release checksum verification failed.");
        return expectedHash;
    }

    private static async Task DownloadArchiveAsync(
        HttpClient client,
        string archiveUrl,
        string temporaryArchive)
    {
        using var response = await client.GetAsync(
            archiveUrl,
            HttpCompletionOption.ResponseHeadersRead);
        response.EnsureSuccessStatusCode();

        await using var source = await response.Content.ReadAsStreamAsync();
        await using (var destination = new FileStream(
            temporaryArchive,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.None,
            bufferSize: 1024 * 128,
            useAsync: true))
        {
            await source.CopyToAsync(destination);
            await destination.FlushAsync();
        }
    }

    private static void ExtractFresh(string archivePath, string destination)
    {
        DeleteDirectory(destination);
        Directory.CreateDirectory(destination);
        ZipFile.ExtractToDirectory(archivePath, destination);
    }

    private static void VerifyDesktopStage(string stage, string sourceSha, string version)
    {
        var buildInfoPath = Path.Combine(stage, "build-info.json");
        Require(File.Exists(buildInfoPath), "Staged desktop build identity is missing.");
        using var build = JsonDocument.Parse(File.ReadAllText(buildInfoPath));
        var root = build.RootElement;
        Require(GetString(root, "schema") == "job_application_pipeline.desktop_host_build.v2", "Staged desktop build schema mismatch.");
        Require(GetString(root, "source_sha").Equals(sourceSha, StringComparison.OrdinalIgnoreCase), "Staged desktop source identity mismatch.");
        Require(GetString(root, "version") == version, "Staged desktop version identity mismatch.");
        Require(GetString(root, "compatibility_line") == CompatibilityLine, "Staged desktop compatibility identity mismatch.");
        Require(GetString(root, "update_generation") == UpdateGeneration, "Staged desktop generation identity mismatch.");
        Require(File.Exists(Path.Combine(stage, "JAP.ControlCenter.Desktop.exe")), "Staged desktop executable is missing.");
    }

    private static void VerifyRuntimeStage(string stage, string sourceSha, string version)
    {
        var infoPath = Path.Combine(stage, "runtime-info.json");
        Require(File.Exists(infoPath), "Staged runtime identity is missing.");
        using var info = JsonDocument.Parse(File.ReadAllText(infoPath));
        var root = info.RootElement;
        Require(GetString(root, "schema") == "job_application_pipeline.runtime_bundle.v1", "Staged runtime schema mismatch.");
        Require(GetString(root, "source_sha").Equals(sourceSha, StringComparison.OrdinalIgnoreCase), "Staged runtime source identity mismatch.");
        Require(GetString(root, "version") == version, "Staged runtime version identity mismatch.");
        Require(GetString(root, "compatibility_line") == CompatibilityLine, "Staged runtime compatibility identity mismatch.");
        Require(GetString(root, "update_generation") == UpdateGeneration, "Staged runtime generation identity mismatch.");
        Require(File.Exists(Path.Combine(stage, "scripts", "run_product_v1_live_demo.py")), "Staged runtime launcher is missing.");
        var runtimeBridge = Path.Combine(stage, "scripts", "run_jap_windows_control_center.sh");
        Require(File.Exists(runtimeBridge), "Staged WSL runtime bridge is missing.");
        Require(!File.ReadAllBytes(runtimeBridge).Contains((byte)'\r'), "Staged WSL runtime bridge contains CR bytes.");
        var localOssProvisioner = Path.Combine(stage, "scripts", "ensure_pinned_local_oss_runtime.sh");
        Require(File.Exists(localOssProvisioner), "Staged local OSS provisioner is missing.");
        Require(!File.ReadAllBytes(localOssProvisioner).Contains((byte)'\r'), "Staged local OSS provisioner contains CR bytes.");
        Require(File.Exists(Path.Combine(stage, "vendor", "codex", "codex")), "Staged bundled Codex executable is missing.");
        Require(File.Exists(Path.Combine(stage, "vendor", "codex", "codex-info.json")), "Staged bundled Codex identity is missing.");
        Require(File.Exists(Path.Combine(stage, "frontend", "control-center", "dist", "index.html")), "Staged frontend bundle is missing.");
        var marker = Path.Combine(stage, "frontend", "control-center", "dist", ".jap-source-sha");
        Require(File.Exists(marker), "Staged frontend source marker is missing.");
        Require(File.ReadAllText(marker).Trim().Equals(sourceSha, StringComparison.OrdinalIgnoreCase), "Staged frontend source marker mismatch.");
    }

    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (var file in Directory.EnumerateFiles(source))
        {
            File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), overwrite: true);
        }
        foreach (var directory in Directory.EnumerateDirectories(source))
        {
            CopyDirectory(directory, Path.Combine(destination, Path.GetFileName(directory)));
        }
    }

    private static void DeleteDirectory(string path)
    {
        if (Directory.Exists(path)) Directory.Delete(path, recursive: true);
    }

    private static string BuildStageMutexName(string installRoot)
    {
        var normalizedRoot = Path.GetFullPath(installRoot)
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            .ToUpperInvariant();
        var digest = Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(normalizedRoot)));
        return $@"Local\JAP.ControlCenter.ProductUpdateStage.{digest}";
    }

    private static string ResolveInstallRoot(string[] args)
    {
        for (var index = 0; index < args.Length - 1; index++)
        {
            if (string.Equals(args[index], "--install-root", StringComparison.OrdinalIgnoreCase))
            {
                return Path.GetFullPath(args[index + 1]);
            }
        }

        var hostRoot = AppContext.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar);
        return Directory.GetParent(hostRoot)?.FullName
            ?? throw new InvalidOperationException("JAP installation root could not be resolved.");
    }

    private static string GetString(JsonElement root, string property) =>
        root.TryGetProperty(property, out var value) ? value.GetString() ?? string.Empty : string.Empty;

    private static bool GetBool(JsonElement root, string property) =>
        root.TryGetProperty(property, out var value)
        && value.ValueKind is JsonValueKind.True or JsonValueKind.False
        && value.GetBoolean();

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static async Task WriteTextAtomicAsync(string path, string content)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + $".tmp.{Environment.ProcessId}";
        await File.WriteAllTextAsync(temporary, content);
        File.Move(temporary, path, overwrite: true);
    }

    private static async Task WriteJsonAtomicAsync(string path, object value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + $".tmp.{Environment.ProcessId}";
        await File.WriteAllTextAsync(
            temporary,
            JsonSerializer.Serialize(value, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, path, overwrite: true);
    }

    private static void WriteLog(string path, string phase, string detail)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.AppendAllText(
            path,
            $"{DateTimeOffset.UtcNow:O}\t{phase}\t{detail.Replace("\r", " ").Replace("\n", " ")}{Environment.NewLine}");
    }

    private sealed record ReleaseCandidate(
        Version Version,
        string Tag,
        string SourceSha,
        string DesktopArchiveUrl,
        string DesktopChecksumUrl,
        string RuntimeArchiveUrl,
        string RuntimeChecksumUrl);
}
