from pathlib import Path


INSTALLER = Path("scripts/windows/install_or_update_job_pipeline_scheduler.ps1")
WRAPPER = Path("scripts/windows/run_scheduled_pipeline.ps1")
DAILY = Path("scripts/run_daily_pipeline.sh")


def test_scheduler_stack_has_no_machine_checkout_guess() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    daily = DAILY.read_text(encoding="utf-8")

    legacy_paths = (
        "~/projects/job-application-pipeline",
        "$HOME/projects/job-application-pipeline",
    )
    for legacy in legacy_paths:
        assert legacy not in installer
        assert legacy not in wrapper
        assert legacy not in daily

    assert "WslProjectPath" not in installer
    assert "-ProjectPath" not in installer
    assert '[string]$ProjectPath' not in wrapper
    assert "Runtime context authority: RCC" in installer
    assert "runtime-contexts/$RepositoryId-$RunnerName.json" in wrapper
    assert "RCC_CONTEXT_FILE" in daily


def test_windows_wrapper_refreshes_projection_from_trusted_rcc_before_consuming_it() -> None:
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert 'Join-Path $env:LOCALAPPDATA "RunnerControlCenterWinUI"' in wrapper
    assert 'Join-Path $RccInstallRoot "RunnerControlCenter.exe"' in wrapper
    assert '$ExpectedRccPublisher = "CN=Jens Haberle"' in wrapper
    assert "Get-AuthenticodeSignature -LiteralPath $RccExe" in wrapper
    assert "--runtime-context-preflight" in wrapper
    assert "--repository-id $RepositoryId" in wrapper
    assert "--runner-name $RunnerName" in wrapper

    preflight = wrapper.index("--runtime-context-preflight")
    projection = wrapper.index('runtime-contexts/$RepositoryId-$RunnerName.json')
    assert preflight < projection
