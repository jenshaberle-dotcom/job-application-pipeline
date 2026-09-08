using System.Diagnostics;
using System.Runtime.CompilerServices;

namespace JAP.ControlCenter.Desktop;

internal static class DesktopLifecycleGuard
{
    private static int _terminating;

    [ModuleInitializer]
    internal static void Initialize()
    {
        if (!Environment.UserInteractive)
        {
            WriteLifecycleEvent(
                "noninteractive_start_rejected",
                $"pid={Environment.ProcessId}");
            Environment.Exit(0);
        }

        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
        Application.ThreadException += (_, eventArgs) =>
            FailClosed("ui_thread_exception", eventArgs.Exception);
        AppDomain.CurrentDomain.UnhandledException += (_, eventArgs) =>
            FailClosed(
                "appdomain_unhandled_exception",
                eventArgs.ExceptionObject as Exception
                    ?? new InvalidOperationException("Unhandled non-Exception object."));
    }

    private static void FailClosed(string phase, Exception exception)
    {
        if (Interlocked.Exchange(ref _terminating, 1) != 0)
        {
            return;
        }

        WriteLifecycleEvent(phase, exception.ToString());
        StopManagedRuntimeBestEffort();
        Environment.Exit(1);
    }

    private static void StopManagedRuntimeBestEffort()
    {
        try
        {
            var installRoot = ResolveInstallRoot();
            if (string.IsNullOrWhiteSpace(installRoot))
            {
                return;
            }

            var stopper = Path.Combine(installRoot, "Stop-JAP-Control-Center.ps1");
            if (!File.Exists(stopper))
            {
                return;
            }

            var powershell = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "System32",
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe");
            if (!File.Exists(powershell))
            {
                return;
            }

            using var process = Process.Start(new ProcessStartInfo
            {
                FileName = powershell,
                WorkingDirectory = installRoot,
                UseShellExecute = false,
                CreateNoWindow = true,
                Arguments = $"-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"{stopper}\""
            });
            if (process is null)
            {
                return;
            }

            if (!process.WaitForExit(20_000))
            {
                try
                {
                    process.Kill(entireProcessTree: true);
                }
                catch
                {
                    // Fail-closed termination remains the authority.
                }
            }
        }
        catch (Exception cleanupException)
        {
            WriteLifecycleEvent("runtime_cleanup_failed", cleanupException.ToString());
        }
    }

    private static string? ResolveInstallRoot()
    {
        try
        {
            var hostRoot = AppContext.BaseDirectory.TrimEnd(
                Path.DirectorySeparatorChar,
                Path.AltDirectorySeparatorChar);
            return Directory.GetParent(hostRoot)?.FullName;
        }
        catch
        {
            return null;
        }
    }

    private static void WriteLifecycleEvent(string phase, string detail)
    {
        try
        {
            var installRoot = ResolveInstallRoot();
            if (string.IsNullOrWhiteSpace(installRoot))
            {
                return;
            }

            var log = Path.Combine(
                installRoot,
                "logs",
                "desktop-host-lifecycle.log");
            Directory.CreateDirectory(Path.GetDirectoryName(log)!);
            var cleanDetail = detail.Replace("\r", " ").Replace("\n", " ");
            File.AppendAllText(
                log,
                $"{DateTimeOffset.UtcNow:O}\t{phase}\t{cleanDetail}{Environment.NewLine}");
        }
        catch
        {
            // Lifecycle diagnostics must never prevent fail-closed exit.
        }
    }
}
