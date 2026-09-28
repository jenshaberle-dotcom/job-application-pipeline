from pathlib import Path

DISPATCHER = Path("scripts/dispatch_origin_provider_benchmark_if_changed.py").read_text(
    encoding="utf-8"
)
RUNNER = Path("scripts/run_origin_provider_event_benchmark.py").read_text(
    encoding="utf-8"
)
SNAPSHOT_RUNNER = Path("scripts/origin_provider_snapshot_runner.py").read_text(
    encoding="utf-8"
)
LEASE_HOLDER = Path("scripts/hold_origin_runtime_lease.py").read_text(encoding="utf-8")
LEASE_WATCHER = Path("scripts/install_windows_origin_runtime_lease_watcher.ps1").read_text(
    encoding="utf-8"
)
SQL = Path("db/ops/create_origin_benchmark_reader.sql").read_text(encoding="utf-8")


def test_dispatcher_sends_only_metadata_after_change_detection() -> None:
    assert "projection_fingerprint" in DISPATCHER
    assert "unchanged projection inside recovery window; no event sent" in DISPATCHER
    assert '"gh",' in DISPATCHER
    assert "repos/{runtime_repository}/dispatches" in DISPATCHER
    assert "candidate_url" not in DISPATCHER
    assert "market_evidence_urls" not in DISPATCHER


def test_remote_runner_stops_on_stale_fingerprint_before_provider_loop() -> None:
    stale_position = RUNNER.index("stale_dispatch_fingerprint")
    provider_loop_position = RUNNER.index("for row in projection[len(results) :]")
    assert stale_position < provider_loop_position
    assert "max_provider_requests" in RUNNER
    assert "review_output_only_not_pipeline_input" in RUNNER


def test_provider_loop_uses_verified_snapshot_without_reopening_database() -> None:
    assert "run_for_projection_row" in RUNNER
    assert '"database_reads_after_snapshot": 0' in RUNNER
    assert "psycopg" not in SNAPSHOT_RUNNER
    assert "get_database_config" not in SNAPSHOT_RUNNER
    assert "projection_snapshot_used" in SNAPSHOT_RUNNER


def test_runtime_lease_is_advisory_lock_based_and_windows_fail_safe() -> None:
    assert "pg_advisory_lock" in LEASE_HOLDER or "acquire_runtime_lease" in LEASE_HOLDER
    assert "SetThreadExecutionState" in LEASE_WATCHER
    assert "GraceSeconds" in LEASE_WATCHER
    assert "ES_SYSTEM_REQUIRED" in LEASE_WATCHER
    assert "$ShouldHold = $LeaseActive -or $InsideGrace" in LEASE_WATCHER


def test_windows_watcher_reuses_one_hidden_wsl_command_session() -> None:
    assert 'Join-Path $env:LOCALAPPDATA "JobPipelineRuntimeLeaseWatcher"' in LEASE_WATCHER
    assert '$HOME/projects/job-application-pipeline' in LEASE_WATCHER
    assert "Start-WslCommandSession" in LEASE_WATCHER
    assert "Stop-WslCommandSession" in LEASE_WATCHER
    assert "System.Diagnostics.ProcessStartInfo" in LEASE_WATCHER
    assert "$StartInfo.CreateNoWindow = $true" in LEASE_WATCHER
    assert "$StartInfo.RedirectStandardInput = $true" in LEASE_WATCHER
    assert 'wsl_session_mode = "persistent_single_process"' in LEASE_WATCHER
    assert "WindowStyle Hidden" in LEASE_WATCHER
    assert "windows_python_required=false" in LEASE_WATCHER
    assert ".venv\\Scripts\\python.exe" not in LEASE_WATCHER
    assert "& wsl.exe -d $WslDistro -- bash -lc" not in LEASE_WATCHER


def test_windows_watcher_records_conservative_awake_time() -> None:
    assert "total_observed_awake_seconds" in LEASE_WATCHER
    assert "total_lease_active_seconds" in LEASE_WATCHER
    assert "total_awake_without_lease_seconds" in LEASE_WATCHER
    assert "total_suspend_or_unobserved_seconds" in LEASE_WATCHER
    assert "AwakeGapThresholdSeconds" in LEASE_WATCHER
    assert 'Event "suspend_or_unobserved_gap"' in LEASE_WATCHER


def test_windows_watcher_tailscale_recovery_is_bounded_and_fail_closed() -> None:
    assert "RecoveryCooldownSeconds" in LEASE_WATCHER
    assert "RecoveryMaxPerHour" in LEASE_WATCHER
    assert '[ValidateSet("start", "restart")]' in LEASE_WATCHER
    assert "Invoke-HiddenWslRootServiceAction" in LEASE_WATCHER
    assert "-u root -- systemctl " in LEASE_WATCHER
    assert "$StartInfo.CreateNoWindow = $true" in LEASE_WATCHER
    assert "NeedsLogin" in LEASE_WATCHER
    assert "NeedsMachineAuth" in LEASE_WATCHER
    assert "tailscale up" not in LEASE_WATCHER
    assert "tailscale logout" not in LEASE_WATCHER
    assert "tailscaled.state" not in LEASE_WATCHER
    assert "systemctl $Action docker" not in LEASE_WATCHER
    assert "systemctl $Action postgresql" not in LEASE_WATCHER


def test_database_role_is_read_only_and_table_scoped() -> None:
    assert "default_transaction_read_only = 'on'" in SQL
    assert "employer_origin_source_candidates" in SQL
    assert "market_evidence" not in SQL
    assert "GRANT SELECT ON TABLE" in SQL
    assert "GRANT INSERT" not in SQL
    assert "GRANT UPDATE" not in SQL
    assert "GRANT DELETE" not in SQL
