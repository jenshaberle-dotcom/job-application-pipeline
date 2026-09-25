using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JAP.ControlCenter.Desktop;

internal static class ProductUpdateOperation
{
    private const string HandoffSchema = "job_application_pipeline.windows_update_handoff.v1";
    private const string HandoffFileName = "update-handoff.json";
    private const string HandoffTokenEnvironment = "JAP_UPDATE_HANDOFF_TOKEN";
    private static readonly Regex ShaPattern =
        new("^[0-9a-f]{40}$", RegexOptions.CultureInvariant);

    public static Mutex CreateOperationMutex(string installRoot) =>
        new(initiallyOwned: false, BuildOperationMutexName(installRoot));

    public static bool TryAcquire(
        Mutex mutex,
        TimeSpan timeout,
        out bool recoveredAbandoned)
    {
        recoveredAbandoned = false;
        try
        {
            return mutex.WaitOne(timeout, false);
        }
        catch (AbandonedMutexException)
        {
            recoveredAbandoned = true;
            return true;
        }
    }

    public static string BeginHandoff(
        string installRoot,
        string targetSha,
        string targetVersion)
    {
        var normalizedSha = targetSha.Trim().ToLowerInvariant();
        if (!ShaPattern.IsMatch(normalizedSha)
            || !Version.TryParse(targetVersion, out _))
        {
            throw new InvalidOperationException(
                "Product update handoff target identity is invalid.");
        }

        var token = Convert.ToHexString(RandomNumberGenerator.GetBytes(32))
            .ToLowerInvariant();
        WriteJsonAtomic(
            HandoffPath(installRoot),
            new
            {
                schema = HandoffSchema,
                target_main_sha = normalizedSha,
                target_desktop_version = targetVersion,
                token_sha256 = HashToken(token),
                phase = "accepted",
                created_at = DateTimeOffset.UtcNow.ToString("O")
            });
        return token;
    }

    public static bool HasActiveHandoff(string installRoot) =>
        File.Exists(HandoffPath(installRoot));

    public static string ReadEnvironmentToken() =>
        Environment.GetEnvironmentVariable(HandoffTokenEnvironment)?.Trim()
        ?? string.Empty;

    public static bool RestartTokenMatches(
        string installRoot,
        string token)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            return false;
        }

        var path = HandoffPath(installRoot);
        if (!File.Exists(path))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            var root = document.RootElement;
            if (Get(root, "schema") != HandoffSchema)
            {
                return false;
            }

            var expectedHash = Get(root, "token_sha256").Trim().ToLowerInvariant();
            var actualHash = HashToken(token);
            if (expectedHash.Length != actualHash.Length)
            {
                return false;
            }

            return CryptographicOperations.FixedTimeEquals(
                Convert.FromHexString(expectedHash),
                Convert.FromHexString(actualHash));
        }
        catch (Exception exc) when (
            exc is IOException
                or JsonException
                or FormatException)
        {
            return false;
        }
    }

    public static void AttachRestartToken(
        ProcessStartInfo startInfo,
        string token)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            throw new InvalidOperationException(
                "Product update handoff token is missing.");
        }

        startInfo.Environment[HandoffTokenEnvironment] = token;
    }

    public static void ClearHandoff(string installRoot)
    {
        try
        {
            File.Delete(HandoffPath(installRoot));
        }
        catch
        {
            // A stale handoff is safer than admitting an uncoordinated startup.
        }
    }

    private static string HandoffPath(string installRoot) =>
        Path.Combine(
            Path.GetFullPath(installRoot),
            "state",
            HandoffFileName);

    private static string BuildOperationMutexName(string installRoot)
    {
        var normalizedRoot = Path.GetFullPath(installRoot)
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            .ToUpperInvariant();
        var digest = Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(normalizedRoot)));
        return $@"Local\JAP.ControlCenter.ProductUpdateOperation.{digest}";
    }

    private static string HashToken(string token) =>
        Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(token)))
        .ToLowerInvariant();

    private static string Get(JsonElement root, string name) =>
        root.TryGetProperty(name, out var value)
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static void WriteJsonAtomic(string path, object value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(
            temporary,
            JsonSerializer.Serialize(
                value,
                new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, path, overwrite: true);
    }
}
