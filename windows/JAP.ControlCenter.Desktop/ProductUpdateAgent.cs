using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JAP.ControlCenter.Desktop;

internal static class ProductUpdateAgent
{
    private const long ExpectedRepositoryId = 1230805345;
    private const string ExpectedRepository = "jenshaberle-dotcom/job-application-pipeline";
    private const string InstallSchema = "job_application_pipeline.windows_control_center_install.v2";
    private const string PendingSchema = "job_application_pipeline.windows_pending_update.v1";
    private const string CompatibilityLine = "1";
    private const string ReleasePrefix = "jap-winapp-desktop-v";
    private const string ArchiveName = "JAP-Control-Center-Desktop-win-x64.zip";
    private const string ChecksumName = "JAP-Control-Center-Desktop-win-x64.zip.sha256";
    private const string StagingProvider = "product_local_update_agent_v1";
    private static readonly Regex ShaPattern = new("^[0-9a-fA-F]{40}$", RegexOptions.CultureInvariant);
    private static readonly Regex DigestPattern = new("^[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant);

    public static async Task<int> RunFromCommandLineAsync(string[] args)
    {
        var installRoot = ResolveInstallRoot(args);
        var logPath = Path.Combine(installRoot, "logs", "product-update-agent.log");
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(logPath)!);
            WriteLog(logPath, "stage_begin", $"install_root={installRoot}");
            var result = await StageLatestAsync(installRoot, logPath);
            WriteLog(logPath, "stage_complete", $"result={result}");
            return 0;
        }
        catch (Exception exc)
        {
            try
            {
                WriteLog(logPath, "stage_failed", exc.ToString());
            }
            catch
            {
                // Diagnostics must not hide the original failure.
            }
            return 2;
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
        if (GetString(current, "schema") != InstallSchema)
        {
            throw new InvalidOperationException("Installed JAP schema is not product-update compatible.");
        }
        if (!current.TryGetProperty("repository_id", out var repositoryId)
            || repositoryId.GetInt64() != ExpectedRepositoryId
            || GetString(current, "repository") != ExpectedRepository)
        {
            throw new InvalidOperationException("Installed JAP repository identity does not match update authority.");
        }
        if (!Version.TryParse(GetString(current, "desktop_host_version"), out var installedVersion)
            || installedVersion.Major != 1)
        {
            throw new InvalidOperationException("Installed JAP desktop version is outside compatibility line 1.");
        }

        using var client = new HttpClient
        {
            Timeout = TimeSpan.FromMinutes(3)
        };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("JAP-Product-Update-Agent/1.0");
        client.DefaultRequestHeaders.Accept.ParseAdd("application/vnd.github+json");
        client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");

        using (var repositoryResponse = await client.GetAsync(
            "https://api.github.com/repos/jenshaberle-dotcom/job-application-pipeline"))
        {
            repositoryResponse.EnsureSuccessStatusCode();
            using var repositoryDocument = JsonDocument.Parse(
                await repositoryResponse.Content.ReadAsStringAsync());
            if (!repositoryDocument.RootElement.TryGetProperty("id", out var id)
                || id.GetInt64() != ExpectedRepositoryId)
            {
                throw new InvalidOperationException("GitHub repository identity mismatch.");
            }
        }

        using var releasesResponse = await client.GetAsync(
            "https://api.github.com/repos/jenshaberle-dotcom/job-application-pipeline/releases?per_page=100");
        releasesResponse.EnsureSuccessStatusCode();
        using var releasesDocument = JsonDocument.Parse(await releasesResponse.Content.ReadAsStringAsync());

        ReleaseCandidate? selected = null;
        foreach (var release in releasesDocument.RootElement.EnumerateArray())
        {
            if (GetBool(release, "draft") || GetBool(release, "prerelease"))
            {
                continue;
            }

            var tag = GetString(release, "tag_name");
            if (!tag.StartsWith(ReleasePrefix, StringComparison.Ordinal))
            {
                continue;
            }

            var versionText = tag[ReleasePrefix.Length..];
            if (!Version.TryParse(versionText, out var version)
                || version.Major != 1
                || version <= installedVersion)
            {
                continue;
            }

            var sourceSha = GetString(release, "target_commitish");
            if (!ShaPattern.IsMatch(sourceSha))
            {
                continue;
            }

            string? archiveUrl = null;
            string? checksumUrl = null;
            if (release.TryGetProperty("assets", out var assets))
            {
                foreach (var asset in assets.EnumerateArray())
                {
                    var name = GetString(asset, "name");
                    var url = GetString(asset, "browser_download_url");
                    if (name == ArchiveName)
                    {
                        archiveUrl = url;
                    }
                    else if (name == ChecksumName)
                    {
                        checksumUrl = url;
                    }
                }
            }

            if (string.IsNullOrWhiteSpace(archiveUrl) || string.IsNullOrWhiteSpace(checksumUrl))
            {
                continue;
            }

            if (selected is null || version > selected.Version)
            {
                selected = new ReleaseCandidate(version, tag, sourceSha.ToLowerInvariant(), archiveUrl, checksumUrl);
            }
        }

        if (selected is null)
        {
            return "no_update";
        }

        var stageRoot = Path.Combine(installRoot, "updates", selected.SourceSha, "payload");
        Directory.CreateDirectory(stageRoot);
        var archivePath = Path.Combine(stageRoot, ArchiveName);
        var checksumPath = Path.Combine(stageRoot, ChecksumName);

        var checksumText = (await client.GetStringAsync(selected.ChecksumUrl)).Trim();
        var expectedHash = checksumText.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)
            .FirstOrDefault()?.Trim().ToLowerInvariant() ?? string.Empty;
        if (!DigestPattern.IsMatch(expectedHash))
        {
            throw new InvalidOperationException("Published JAP release checksum is invalid.");
        }

        await WriteTextAtomicAsync(checksumPath, checksumText + Environment.NewLine);

        var archiveReady = File.Exists(archivePath)
            && string.Equals(await ComputeSha256Async(archivePath), expectedHash, StringComparison.OrdinalIgnoreCase);
        if (!archiveReady)
        {
            var temporaryArchive = archivePath + $".download.{Environment.ProcessId}";
            try
            {
                if (File.Exists(temporaryArchive))
                {
                    File.Delete(temporaryArchive);
                }

                using (var response = await client.GetAsync(selected.ArchiveUrl, HttpCompletionOption.ResponseHeadersRead))
                {
                    response.EnsureSuccessStatusCode();
                    await using var source = await response.Content.ReadAsStreamAsync();
                    await using var destination = new FileStream(
                        temporaryArchive,
                        FileMode.CreateNew,
                        FileAccess.Write,
                        FileShare.None,
                        bufferSize: 1024 * 128,
                        useAsync: true);
                    await source.CopyToAsync(destination);
                    await destination.FlushAsync();
                }

                var actualHash = await ComputeSha256Async(temporaryArchive);
                if (!string.Equals(actualHash, expectedHash, StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException("Downloaded JAP release checksum verification failed.");
                }

                File.Move(temporaryArchive, archivePath, overwrite: true);
            }
            finally
            {
                if (File.Exists(temporaryArchive))
                {
                    File.Delete(temporaryArchive);
                }
            }
        }

        var finalHash = await ComputeSha256Async(archivePath);
        if (!string.Equals(finalHash, expectedHash, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Staged JAP release checksum verification failed.");
        }

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
                policy = "latest_direct",
                desktop_archive = archivePath,
                desktop_checksum = checksumPath,
                desktop_sha256 = expectedHash,
                staging_provider = StagingProvider,
                staged_at = DateTimeOffset.UtcNow.ToString("O")
            });

        WriteLog(
            logPath,
            "pending_published",
            $"version={selected.Version} sha={selected.SourceSha} provider={StagingProvider}");
        return $"staged:{selected.Version}";
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

    private static string GetString(JsonElement root, string property)
    {
        return root.TryGetProperty(property, out var value)
            ? value.GetString() ?? string.Empty
            : string.Empty;
    }

    private static bool GetBool(JsonElement root, string property)
    {
        return root.TryGetProperty(property, out var value)
            && value.ValueKind is JsonValueKind.True or JsonValueKind.False
            && value.GetBoolean();
    }

    private static async Task<string> ComputeSha256Async(string path)
    {
        await using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 1024 * 128,
            useAsync: true);
        using var sha = SHA256.Create();
        var digest = await sha.ComputeHashAsync(stream);
        return Convert.ToHexString(digest).ToLowerInvariant();
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
        string ArchiveUrl,
        string ChecksumUrl);
}
