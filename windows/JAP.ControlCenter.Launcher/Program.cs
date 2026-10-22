using System.Diagnostics;

internal static class Program
{
    [STAThread]
    static int Main(string[] args)
    {
        string root = AppContext.BaseDirectory;
        string log = Path.Combine(root, "launcher.log");
        try
        {
            var info = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RunnerControlCenter", "tools", "PowerShell", "7", "pwsh.exe"));
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            foreach (string arg in new[] { "-NoProfile", "-STA", "-File", Path.Combine(root, "Start-JapLatest.ps1") }) info.ArgumentList.Add(arg);
            if (args.Contains("--verify-only")) info.ArgumentList.Add("-VerifyOnly");
            using var child = Process.Start(info) ?? throw new Exception("Startprozess konnte nicht erzeugt werden.");
            var stdout = child.StandardOutput.ReadToEndAsync();
            var stderr = child.StandardError.ReadToEndAsync();
            child.WaitForExit();
            File.AppendAllText(log, $"{DateTimeOffset.Now:O} exit={child.ExitCode}\n{stdout.Result}\n{stderr.Result}\n");
            if (child.ExitCode != 0) throw new Exception("JAP konnte nicht gestartet werden. Details: " + log);
            return 0;
        }
        catch (Exception ex)
        {
            File.AppendAllText(log, $"{DateTimeOffset.Now:O} {ex.Message}\n");
            MessageBox.Show(ex.Message, "JAP Start", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
