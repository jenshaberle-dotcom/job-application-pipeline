using System.Security.Cryptography;
using System.Text;

namespace JAP.ControlCenter.Desktop;

internal static class ProductUpdateIntegrity
{
    public static string ComputeFileSha256(string path)
    {
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    public static string ComputeDirectorySha256(string root)
    {
        var fullRoot = Path.GetFullPath(root);
        if (!Directory.Exists(fullRoot))
        {
            throw new DirectoryNotFoundException(fullRoot);
        }

        using var digest = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        foreach (var file in Directory.EnumerateFiles(
                     fullRoot,
                     "*",
                     SearchOption.AllDirectories)
                 .OrderBy(
                     path => Path.GetRelativePath(fullRoot, path),
                     StringComparer.Ordinal))
        {
            var relative = Path.GetRelativePath(fullRoot, file)
                .Replace(Path.DirectorySeparatorChar, '/');
            digest.AppendData(Encoding.UTF8.GetBytes(relative));
            digest.AppendData(new byte[] { 0 });
            using var stream = new FileStream(
                file,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read);
            digest.AppendData(SHA256.HashData(stream));
            digest.AppendData(new byte[] { 0 });
        }

        return Convert.ToHexString(digest.GetHashAndReset()).ToLowerInvariant();
    }

    public static string RequirePathUnder(string root, string path, string message)
    {
        var fullRoot = Path.GetFullPath(root)
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var fullPath = Path.GetFullPath(path);
        var prefix = fullRoot + Path.DirectorySeparatorChar;
        if (!fullPath.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(message);
        }

        return fullPath;
    }
}
