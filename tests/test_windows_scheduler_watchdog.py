from pathlib import Path


def test_scheduler_wrapper_has_same_day_success_guard() -> None:
    text = Path("scripts/windows/run_scheduled_pipeline.ps1").read_text(encoding="utf-8")

    assert "last_successful_local_date" in text
    assert "SKIP daily pipeline already completed successfully" in text
    assert "-Force" in text or "[switch]$Force" in text
    assert "daily-pipeline-state.json" in text


def test_scheduler_installer_registers_daily_and_logon_catchup_triggers() -> None:
    text = Path("scripts/windows/install_or_update_job_pipeline_scheduler.ps1").read_text(encoding="utf-8")

    assert "New-ScheduledTaskTrigger -Daily" in text
    assert "New-ScheduledTaskTrigger -AtLogOn" in text
    assert "StartWhenAvailable" in text
    assert "WakeToRun" in text
    assert "run_scheduled_pipeline.ps1" in text
