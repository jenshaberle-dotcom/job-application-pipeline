using System.Diagnostics;
using System.Text.Json;

namespace JAP.ControlCenter.Desktop;

internal sealed class UpdateCoordinator : IDisposable
{
    private const string PendingSchema = "job_application_pipeline.windows_product_update.v2";
    private const string SnoozeSchema = "job_application_pipeline.windows_update_snooze.v1";
    private const string ResultSchema = "job_application_pipeline.windows_update_result.v2";
    private const string InstallSchema = "job_application_pipeline.windows_control_center_install.v3";
    private const string CompatibilityLine = "cgkb-product-local-1";
    private static readonly TimeSpan SnoozeDuration = TimeSpan.FromHours(6);
    private static readonly TimeSpan FailureRetryDelay = TimeSpan.FromMinutes(10);
    private static readonly TimeSpan DiscoveryInterval = TimeSpan.FromMinutes(10);

    private readonly Form _owner;
    private readonly string _installRoot;
    private readonly string _pendingPath;
    private readonly string _acceptedPath;
    private readonly string _snoozePath;
    private readonly string _resultPath;
    private readonly string _eventLog;
    private readonly System.Windows.Forms.Timer _pollTimer;
    private bool _promptOpen;
    private bool _resultChecked;
    private bool _applyingUpdate;
    private bool _stagingInFlight;
    private DateTimeOffset _nextDiscoveryUtc = DateTimeOffset.MinValue;

    public UpdateCoordinator(Form owner, string installRoot)
    {
        _owner = owner;
        _installRoot = installRoot;
        var stateRoot = Path.Combine(_installRoot, "state");
        _pendingPath = Path.Combine(stateRoot, "pending-update.json");
        _acceptedPath = Path.Combine(stateRoot, "accepted-update.json");
        _snoozePath = Path.Combine(stateRoot, "update-snooze.json");
        _resultPath = Path.Combine(stateRoot, "update-result.json");
        _eventLog = Path.Combine(_installRoot, "logs", "desktop-host-update.log");
        _pollTimer = new System.Windows.Forms.Timer
        {
            Interval = 60_000
        };
        _pollTimer.Tick += (_, _) =>
        {
            PromptIfAvailable();
            TriggerStageLatest();
        };
    }

    public bool IsApplyingUpdate => _applyingUpdate;

    public void StartPolling()
    {
        _pollTimer.Start();
        PromptIfAvailable();
        TriggerStageLatest();
    }

    private void TriggerStageLatest()
    {
        var now = DateTimeOffset.UtcNow;
        if (_applyingUpdate || _stagingInFlight || now < _nextDiscoveryUtc)
        {
            return;
        }

        _nextDiscoveryUtc = now.Add(DiscoveryInterval);
        _stagingInFlight = true;
        _ = StageLatestAsync();
    }

    private async Task StageLatestAsync()
    {
        try
        {
            var executable = Environment.ProcessPath;
            if (string.IsNullOrWhiteSpace(executable) || !File.Exists(executable))
            {
                WriteEvent("product_update_agent_unavailable", "desktop executable path could not be resolved");
                return;
            }

            var startInfo = new ProcessStartInfo
            {
                FileName = executable,
                WorkingDirectory = _installRoot,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            startInfo.ArgumentList.Add("--stage-update");
            startInfo.ArgumentList.Add("--install-root");
            startInfo.ArgumentList.Add(_installRoot);

            using var process = Process.Start(startInfo)
                ?? throw new InvalidOperationException("JAP product update agent could not be started.");
            await process.WaitForExitAsync();
            if (process.ExitCode != 0)
            {
                WriteEvent("product_update_agent_failed", $"exit_code={process.ExitCode}");
                return;
            }

            if (!_owner.IsDisposed && _owner.IsHandleCreated)
            {
                _owner.BeginInvoke(new Action(() => PromptIfAvailable()));
            }
        }
        catch (Exception exc)
        {
            WriteEvent("product_update_agent_start_failed", exc.ToString());
        }
        finally
        {
            _stagingInFlight = false;
        }
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
        var snoozeMatchesPending = snooze is not null
            && snooze.TargetMainSha == pending.TargetMainSha
            && snooze.TargetDesktopVersion == pending.TargetDesktopVersion;
        if (snoozeMatchesPending && snooze!.SnoozeUntilUtc > now)
        {
            return false;
        }

        var wasSuperseded = snooze is not null
            && !snoozeMatchesPending;
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

            WriteAcceptedManifest(pending.ManifestJson);
            var handoffToken = ProductUpdateOperation.BeginHandoff(
                _installRoot,
                pending.TargetMainSha,
                pending.TargetDesktopVersion);
            TryDelete(_snoozePath);
            WriteEvent(
                "update_accepted",
                $"target={pending.TargetDesktopVersion} sha={pending.TargetMainSha}");
            _applyingUpdate = true;

            var helperExecutable = Path.GetFullPath(pending.ApplyHelperExecutable);
            var updatesRoot = Path.GetFullPath(Path.Combine(_installRoot, "updates"))
                .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                + Path.DirectorySeparatorChar;
            if (!helperExecutable.StartsWith(updatesRoot, StringComparison.OrdinalIgnoreCase)
                || !File.Exists(helperExecutable))
            {
                throw new InvalidOperationException(
                    "The frozen product-local apply helper is missing or outside the managed update root.");
            }

            _pollTimer.Stop();
            var startInfo = new ProcessStartInfo
            {
                FileName = helperExecutable,
                WorkingDirectory = _installRoot,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            startInfo.ArgumentList.Add("--apply-update");
            startInfo.ArgumentList.Add("--install-root");
            startInfo.ArgumentList.Add(_installRoot);
            startInfo.ArgumentList.Add("--host-pid");
            startInfo.ArgumentList.Add(Environment.ProcessId.ToString());
            ProductUpdateOperation.AttachRestartToken(startInfo, handoffToken);

            _ = Process.Start(startInfo)
                ?? throw new InvalidOperationException("JAP product-local update applier could not be started.");
            WriteEvent("update_apply_handoff", $"helper={helperExecutable}");
            _owner.Close();
            return true;
        }
        catch (Exception exc)
        {
            ProductUpdateOperation.ClearHandoff(_installRoot);
            TryDelete(_acceptedPath);
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

        return installedVersion >= new Version(1, 0, 65)
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
            var raw = File.ReadAllText(_pendingPath);
            using var document = JsonDocument.Parse(raw);
            var root = document.RootElement;
            if (GetString(root, "schema") != PendingSchema)
            {
                return null;
            }

            return new PendingUpdate(
                GetString(root, "target_main_sha"),
                GetString(root, "target_desktop_version"),
                GetString(root, "compatibility_line"),
                GetString(root, "installer_schema"),
                GetString(root, "apply_helper_executable"),
                raw);
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

    private void WriteFailureCooldown(
        string targetSha,
        string targetVersion,
        DateTimeOffset until)
    {
        WriteJsonAtomic(
            _snoozePath,
            new
            {
                schema = SnoozeSchema,
                snooze_until_utc = until.ToString("O"),
                target_main_sha = targetSha,
                target_desktop_version = targetVersion,
                reason = "apply_failed_retry_cooldown"
            });
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

    private void WriteAcceptedManifest(string rawJson)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_acceptedPath)!);
        var temporary = _acceptedPath + ".tmp";
        File.WriteAllText(temporary, rawJson);
        File.Move(temporary, _acceptedPath, overwrite: true);
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
                var targetSha = GetString(root, "target_main_sha");
                var targetVersion = GetString(root, "target_desktop_version");
                if (!string.IsNullOrWhiteSpace(targetSha)
                    && !string.IsNullOrWhiteSpace(targetVersion))
                {
                    WriteFailureCooldown(
                        targetSha,
                        targetVersion,
                        DateTimeOffset.UtcNow.Add(FailureRetryDelay));
                }

                MessageBox.Show(
                    _owner,
                    "Das letzte JAP-Update konnte nicht abgeschlossen werden. Die vorherige Installation wurde wieder gestartet."
                    + $"\n\nDerselbe Update-Stand wird für {FailureRetryDelay.TotalMinutes:0} Minuten nicht erneut angeboten. Ein neuerer Stand bleibt sofort zulässig."
                    + (string.IsNullOrWhiteSpace(detail) ? string.Empty : $"\n\nTechnisches Detail: {detail}"),
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
        string InstallerSchema,
        string ApplyHelperExecutable,
        string ManifestJson);

    private sealed record SnoozeState(
        DateTimeOffset SnoozeUntilUtc,
        string TargetMainSha,
        string TargetDesktopVersion);
}
