import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install-jap-control-center.ps1"
APPLIER = ROOT / "Apply-JAP-Control-Center-Update.ps1"
UPDATE_COORDINATOR = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "UpdateCoordinator.cs"
UPDATE_CONTEXT = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "UpdateAwareApplicationContext.cs"
PROGRAM = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "Program.cs"
VERSION = ROOT / "windows" / "JAP.ControlCenter.Desktop" / "VERSION"
COMPATIBILITY = (
    ROOT / "windows" / "JAP.ControlCenter.Desktop" / "UPDATE_COMPATIBILITY.json"
)
RELEASE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "jap-windows-desktop-host-release.yml"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_update_compatibility_contract_is_latest_direct_v1_with_six_hour_snooze() -> None:
    contract = json.loads(_text(COMPATIBILITY))
    assert contract["schema"] == "job_application_pipeline.windows_update_compatibility.v1"
    assert contract["compatibility_line"] == "1"
    assert contract["policy"] == "latest_direct"
    assert contract["direct_upgrade_from"] == "1.x"
    assert contract["installer_schema"] == "job_application_pipeline.windows_control_center_install.v2"
    assert contract["snooze_hours"] == 6
    assert _text(VERSION).strip() == "1.0.11"


def test_desktop_host_polls_pending_update_and_prompts_for_consent() -> None:
    coordinator = _text(UPDATE_COORDINATOR)
    context = _text(UPDATE_CONTEXT)
    program = _text(PROGRAM)
    assert "TimeSpan.FromHours(6)" in coordinator
    assert "Interval = 60_000" in coordinator
    assert 'pending-update.json' in coordinator
    assert 'accepted-update.json' in coordinator
    assert 'update-snooze.json' in coordinator
    assert "MessageBoxButtons.YesNo" in coordinator
    assert "Jetzt installieren?" in coordinator
    assert "für 6 Stunden zurückgestellt" in coordinator
    assert "Während des Aufschubs wurde ein neuerer kompatibler Stand bereitgestellt." in coordinator
    assert "Apply-JAP-Control-Center-Update.ps1" in coordinator
    assert "WriteAcceptedManifest(pending.ManifestJson)" in coordinator
    assert "_owner.BeginInvoke(new Action(() => _owner.Close()))" in coordinator
    assert "_updates.StartPolling()" in context
    assert "Application.Run(new UpdateAwareApplicationContext())" in program


def test_update_applier_closes_stops_installs_exact_staged_target_and_restarts() -> None:
    applier = _text(APPLIER)
    assert "$hostProcess.WaitForExit(60000)" in applier
    assert 'Join-Path $InstallRoot "Stop-JAP-Control-Center.ps1"' in applier
    assert "-PinnedSha $targetSha" in applier
    assert "-DesktopHostArchivePath $archive" in applier
    assert "-DesktopHostChecksumPath $checksum" in applier
    assert "Get-FileHash $archive -Algorithm SHA256" in applier
    assert "Remove-AcceptedManifest" in applier
    assert 'status = "success"' in applier
    assert 'status = "failed"' in applier
    assert "Restart-JapIfPresent" in applier
    assert "target_main_sha" in applier
    assert "target_desktop_version" in applier


def test_installer_supports_exact_staged_payload_without_losing_main_ancestry_proof() -> None:
    installer = _text(INSTALLER)
    assert "[string]$PinnedSha" in installer
    assert "[string]$DesktopHostArchivePath" in installer
    assert "[string]$DesktopHostChecksumPath" in installer
    assert '"cat-file", "-e", "$PinnedSha^{commit}"' in installer
    assert "merge-base --is-ancestor $PinnedSha $fetchedMain" in installer
    assert "Install-DesktopHost $desktopHostVersion $DesktopHostArchivePath $DesktopHostChecksumPath" in installer
    assert 'update_mode = $UpdateMode' in installer
    assert 'update_surface = "integrated_main_app"' in installer
    assert 'compatibility_line = $CompatibilityLine' in installer
    assert 'update_authority = "local_runner_staged_gui_prompt"' in installer
    assert "Copy-Item -Force $sourceApplier $StableApplier" in installer


def test_standalone_update_shortcut_and_script_are_removed_from_installed_surface() -> None:
    installer = _text(INSTALLER)
    coordinator = _text(UPDATE_COORDINATOR)
    assert '$LegacyStableUpdater = Join-Path $InstallRoot "Update-JAP-Control-Center.ps1"' in installer
    assert "Remove-Item -Force $LegacyStableUpdater -ErrorAction SilentlyContinue" in installer
    assert '$legacyUpdateShortcut = Join-Path $programs "Update JAP Control Center.lnk"' in installer
    assert "Remove-Item -Force $legacyUpdateShortcut -ErrorAction SilentlyContinue" in installer
    assert 'New-AppShortcut (Join-Path $programs "Update JAP Control Center.lnk")' not in installer
    assert "Copy-Item -Force $sourceUpdater $StableUpdater" not in installer
    assert "MessageBoxButtons.YesNo" in coordinator
    assert "Apply-JAP-Control-Center-Update.ps1" in coordinator


def test_release_workflow_enforces_direct_v1_compatibility_before_publish() -> None:
    workflow = _text(RELEASE_WORKFLOW)
    assert "Prove direct latest-update compatibility contract" in workflow
    assert 'policy -ne "latest_direct"' in workflow
    assert 'compatibility_line -ne "1"' in workflow
    assert 'direct_upgrade_from -ne "1.x"' in workflow
    assert "snooze_hours" in workflow
    assert "A breaking desktop update requires a new compatibility bridge" in workflow
    assert "Direct v1 latest-state upgrade" in workflow
