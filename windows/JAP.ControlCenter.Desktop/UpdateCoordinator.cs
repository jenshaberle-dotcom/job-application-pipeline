using System.Diagnostics;
using System.Text.Json;

namespace JAP.ControlCenter.Desktop;

internal sealed class UpdateCoordinator : IDisposable
{
    private const string PendingSchema = "job_application_pipeline.windows_pending_update.v1";
    private const string SnoozeSchema = "job_application_pipeline.windows_update_snooze.v1";
    private const string ResultSchema = "job_application_pipeline.windows_update_result.v1";
    private const string InstallSchema = "job_application_pipeline.windows_control_center_install.v2";
    private const string CompatibilityLine = "1";
    private static readonly TimeSpan SnoozeDuration = TimeSpan.FromHours(6);

    private readonly Form _owner;
    private readonly string _installRoot;
    private readonly string _pendingPath;
    private readonly string _snoozePath;
    private readonly string _resultPath;
    private readonly string _eventLog;
    private readonly System.Windows.Forms.Timer _pollTimer;
    private bool _promptOpen;
    private bool _resultChecked;
    private bool _applyingUpdate;

    public UpdateCoordinator(Form owner, string installRoot)
    {
        _owner = owner;
        _installRoot = installRoot;
        var stateRoot = Path.Combine(_installRoot, "state");
        _pendingPath = Path.Combine(stateRoot, "pending-update.json");
        _snoozePath = Path.Combine(stateRoot, "update-snooze.json");
        _resultPath = Path.Combine(stateRoot, "update-result.json");
        _eventLog = Path.Combine(_installRoot, "logs", "desktop-host-update.log");
        _pollTimer = new System.Windows.Forms.Timer
        {
            Interval = 60_000
        };
        _pollTimer.Tick += (_, _) => PromptIfAvailable();
    }

    public bool IsApplyingUpdate => _applyingUpdate;

    public void StartPolling()
    {
        _pollTimer.Start();
        PromptIfAvailable();
    }

    public bool PromptIfAvailable()
    {
        ShowPreviousUpdateFailureOnce();
        if (_applyingUpdate || _promptOpen)
        {
            return _applyingUpdate;
        }

        var current = ReadCurrent();
        var pending = ReadPending();
        if (current is null || pending is null)
        {
            return false;
        }

        if (pending.TargetMainSha == current.PinnedSha
            && pending.TargetDesktopVersion == current.DesktopHostVersion)
        {
            TryDelete(_pendingPath);
            TryDelete(_snoozePath);
            return false;
        }

        if (!IsCompatible(current, pending))
        {
            WriteEvent(
                "pending_blocked",
                $"installed={current.DesktopHostVersion} target={pending.TargetDesktopVersion} "
                + $"line={pending.CompatibilityLine} schema={pending.InstallerSchema}");
            return false;
        }

        var snooze = ReadSnooze();
        var now = DateTimeOffset.UtcNow;
        if (snooze is not null && snooze.SnoozeUntilUtc > now)
        {
            return false;
        }

        var wasSuperseded = snooze is not null
            && (snooze.TargetMainSha != pending.TargetMainSha
                || snooze.TargetDesktopVersion != pending.TargetDesktopVersion);
        var supersededText = wasSuperseded
            ? "\nWährend des Aufschubs wurde ein neuerer kompatibler Stand bereitgestellt."
            : string.Empty;

        _promptOpen = true;
        try
        {
            var answer = MessageBox.Show(
                _owner,
                "Ein Update für JAP Control Center ist verfügbar.\n\n"
                + $"Installiert: v{current.DesktopHostVersion}\n"
                + $"Verfügbar: v{pending.TargetDesktopVersion}"
                + supersededText
                + "\n\nBei 'Ja' wird JAP geschlossen, das Update installiert und JAP anschließend automatisch neu gestartet."
                + "\nBei 'Nein' wird die Abfrage für 6 Stunden zurückgestellt."
                + "\n\nJetzt installieren?",
                "JAP Control Center Update",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information,
                MessageBoxDefaultButton.Button1);

            if (answer != DialogResult.Yes)
            {
                WriteSnooze(pending, now.Add(SnoozeDuration));
                WriteEvent(
                    "update_snoozed",
                    $"target={pending.TargetDesktopVersion} until={now.Add(SnoozeDuration):O}");
                return false;
            }

            var applier = Path.Combine(_installRoot, "Apply-JAP-Control-Center-Update.ps1");
            if (!File.Exists(applier))
            {
                MessageBox.Show(
                    _owner,
                    "Das Update ist bereit, aber der installierte JAP-Updater fehlt. Das Update wurde nicht gestartet.",
                    "JAP Control Center Update",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                return false;
            }

            var powershell = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "System32",
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe");
            var startInfo = new ProcessStartInfo
            {
                FileName = powershell,
                WorkingDirectory = _installRoot,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            startInfo.ArgumentList.Add("-NoProfile");
            startInfo.ArgumentList.Add("-ExecutionPolicy");
            startInfo.ArgumentList.Add("Bypass");
            startInfo.ArgumentList.Add("-WindowStyle");
            startInfo.ArgumentList.Add("Hidden");
            startInfo.ArgumentList.Add("-File");
            startInfo.ArgumentList.Add(applier);
            startInfo.ArgumentList.Add("-ManifestPath");
            startInfo.ArgumentList.Add(_pendingPath);
            startInfo.ArgumentList.Add("-HostPid");
            startInfo.ArgumentList.Add(Environment.ProcessId.ToString());

            Process.Start(startInfo)
                ?? throw new InvalidOperationException("JAP update process could not be started.");
            _applyingUpdate = true;
            _pollTimer.Stop();
            TryDelete(_snoozePath);
            WriteEvent("update_accepted", $"target={pending.TargetDesktopVersion}");
            _owner.BeginInvoke(() => _owner.Close());
            return true;
        }
        catch (Exception exc)
        {
            WriteEvent("update_start_failed", exc.ToString());
            MessageBox.Show(
                _owner,
                $"Das JAP-Update konnte nicht gestartet werden.\n\n{exc.Message}",
                "JAP Control Center Update",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }
        finally
        {
            _promptOpen = false;
        }
    }

    private bool IsCompatible(CurrentInstall current, PendingUpdate pending)
    {
        if (current.Schema != InstallSchema
            || pending.InstallerSchema != InstallSchema
            || pending.CompatibilityLine != CompatibilityLine)
        {
            return false;
        }

        if (!Version.TryParse(current.DesktopHostVersion, out var installedVersion)
            || !Version.TryParse(pending.TargetDesktopVersion, out var targetVersion))
        {
            return false;
        }

        return installedVersion.Major == 1
            && targetVersion.Major == 1
            && targetVersion > installedVersion;
    }

    private CurrentInstall? ReadCurrent()
    {
        var path = Path.Combine(_installRoot, "current.json");
        if (!File.Exists(path))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            var root = document.RootElement;
            return new CurrentInstall(
                GetString(root, "schema"),
                GetString(root, "pinned_sha"),
                GetString(root, "desktop_host_version"));
        }
        catch (Exception exc) when (exc is IOException or JsonException)
        {
            WriteEvent("current_read_failed", exc.Message);
            return null;
        }
    }

    private PendingUpdate? ReadPending()
    {
        if (!File.Exists(_pendingPath))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(_pendingPath));
            var root = document.RootElement;
            if (GetString(root, "schema") != PendingSchema)
            {
                return null;
            }

            return new PendingUpdate(
                GetString(root, "target_main_sha"),
                GetString(root, "target_desktop_version"),
                GetString(root, "compatibility_line"),
                GetString(root, "installer_schema"));
        }
        catch (Exception exc) when (exc is IOException or JsonException)
        {
            WriteEvent("pending_read_failed", exc.Message);
            return null;
        }
    }

    private SnoozeState? ReadSnooze()
    {
        if (!File.Exists(_snoozePath))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(_snoozePath));
            var root = document.RootElement;
            if (GetString(root, "schema") != SnoozeSchema)
            {
                return null;
            }

            if (!DateTimeOffset.TryParse(
                    GetString(root, "snooze_until_utc"),
                    out var until))
            {
                return null;
            }

            return new SnoozeState(
                until,
                GetString(root, "target_main_sha"),
                GetString(root, "target_desktop_version"));
        }
        catch (Exception exc) when (exc is IOException or JsonException)
        {
            WriteEvent("snooze_read_failed", exc.Message);
            return null;
        }
    }

    private void WriteSnooze(PendingUpdate pending, DateTimeOffset until)
    {
        WriteJsonAtomic(
            _snoozePath,
            new
            {
                schema = SnoozeSchema,
                snooze_until_utc = until.ToString("O"),
                target_main_sha = pending.TargetMainSha,
                target_desktop_version = pending.TargetDesktopVersion
            });
    }

    private void ShowPreviousUpdateFailureOnce()
    {
        if (_resultChecked)
        {
            return;
        }

        _resultChecked = true;
        if (!File.Exists(_resultPath))
        {
            return;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(_resultPath));
            var root = document.RootElement;
            if (GetString(root, "schema") != ResultSchema)
            {
                return;
            }

            if (GetString(root, "status") == "failed")
            {
                var detail = GetString(root, "detail");
                MessageBox.Show(
                    _owner,
                    "Das letzte JAP-Update konnte nicht abgeschlossen werden. Die vorherige Installation wurde wieder gestartet."
                    + (string.IsNullOrWhiteSpace(detail) ? string.Empty : $"\n\n{detail}"),
                    "JAP Control Center Update",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
            }
        }
        catch
        {
            // Update-result diagnostics must not block product startup.
        }
        finally
        {
            TryDelete(_resultPath);
        }
    }

    private static string GetString(JsonElement root, string property)
    {
        return root.TryGetProperty(property, out var value)
            ? value.GetString() ?? string.Empty
            : string.Empty;
    }

    private static void WriteJsonAtomic(string path, object value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(
            temporary,
            JsonSerializer.Serialize(value, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, path, overwrite: true);
    }

    private void WriteEvent(string phase, string detail)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_eventLog)!);
            File.AppendAllText(
                _eventLog,
                $"{DateTimeOffset.UtcNow:O}\t{phase}\t{detail.Replace("\r", " ").Replace("\n", " ")}{Environment.NewLine}");
        }
        catch
        {
            // Update diagnostics must never become an update dependency.
        }
    }

    private static void TryDelete(string path)
    {
        try
        {
            File.Delete(path);
        }
        catch
        {
            // Stale metadata will be reconciled on the next poll.
        }
    }

    public void Dispose()
    {
        _pollTimer.Stop();
        _pollTimer.Dispose();
    }

    private sealed record CurrentInstall(
        string Schema,
        string PinnedSha,
        string DesktopHostVersion);

    private sealed record PendingUpdate(
        string TargetMainSha,
        string TargetDesktopVersion,
        string CompatibilityLine,
        string InstallerSchema);

    private sealed record SnoozeState(
        DateTimeOffset SnoozeUntilUtc,
        string TargetMainSha,
        string TargetDesktopVersion);
}
