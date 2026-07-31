from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.watch_origin_runtime_lease import (
    classify_gap,
    classify_recovery,
    default_state,
    execute_recovery_action,
    load_state,
    parse_wsl_state,
    record_observation,
    recovery_allowed,
)


def test_awake_time_separates_lease_and_non_lease_intervals() -> None:
    start = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    state = default_state(start)

    assert record_observation(state, start, False, 30.0) == (None, 0.0)
    classification, delta = record_observation(
        state, start + timedelta(seconds=5), True, 30.0
    )
    assert classification == "observed_awake"
    assert delta == 5.0
    assert state["totals"]["awake_without_lease_seconds"] == 5.0

    classification, delta = record_observation(
        state, start + timedelta(seconds=10), True, 30.0
    )
    assert classification == "observed_awake"
    assert delta == 5.0
    assert state["totals"]["lease_active_seconds"] == 5.0
    assert state["totals"]["observed_awake_seconds"] == 10.0


def test_long_gap_is_not_counted_as_awake_time() -> None:
    start = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    state = default_state(start)
    record_observation(state, start, False, 30.0)

    classification, delta = record_observation(
        state, start + timedelta(hours=4), False, 30.0
    )

    assert classify_gap(delta, 30.0) == "suspend_or_unobserved"
    assert classification == "suspend_or_unobserved"
    assert state["totals"]["observed_awake_seconds"] == 0.0
    assert state["totals"]["suspend_or_unobserved_seconds"] == 4 * 3600
    assert state["totals"]["suspend_or_unobserved_events"] == 1


def test_state_loading_preserves_new_metric_defaults(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        '{"schema_version": 1, "totals": {"observed_awake_seconds": 12}}',
        encoding="utf-8",
    )
    state = load_state(path, datetime(2026, 7, 31, tzinfo=timezone.utc))
    assert state["totals"]["observed_awake_seconds"] == 12
    assert state["totals"]["tailscale_recovery_attempts"] == 0
    assert "current_day" in state


def test_wsl_state_parser_handles_marker_and_nul_bytes() -> None:
    output = "  NAME STATE VERSION\n* Ubuntu Running 2\n  docker-desktop Stopped 2\n"
    assert parse_wsl_state(output, "Ubuntu") == "Running"
    assert parse_wsl_state(output.replace("", "\x00"), "Ubuntu") == "Running"
    assert parse_wsl_state(output, "missing") == "Unknown"


def test_recovery_classification_is_bounded_and_fail_closed() -> None:
    healthy = {
        "wsl_state_before": "Running",
        "service_state": "active",
        "status_rc": 0,
        "backend_state": "Running",
        "self_online": True,
        "interface_present": True,
        "error": None,
    }
    assert classify_recovery(healthy) == "none"
    assert classify_recovery({**healthy, "wsl_state_before": "Stopped"}) == "wsl_start_only"
    assert classify_recovery({**healthy, "service_state": "inactive"}) == "start"
    assert classify_recovery({**healthy, "self_online": False}) == "restart"
    assert classify_recovery({**healthy, "backend_state": "NeedsLogin"}) == "fail_closed_auth"
    assert classify_recovery({**healthy, "status_rc": 1, "error": "Logged out."}) == (
        "fail_closed_auth"
    )


def test_recovery_gate_enforces_cooldown_and_hourly_limit() -> None:
    attempts: deque[float] = deque([100.0, 200.0, 300.0])
    allowed, reason = recovery_allowed(350.0, attempts, 300.0, 600.0, 3)
    assert (allowed, reason) == (False, "cooldown")

    allowed, reason = recovery_allowed(1000.0, attempts, None, 600.0, 3)
    assert (allowed, reason) == (False, "hourly_limit")

    allowed, reason = recovery_allowed(4000.0, attempts, None, 600.0, 3)
    assert (allowed, reason) == (True, "allowed")
    assert not attempts


def test_recovery_action_runs_only_exact_tailscaled_service(monkeypatch) -> None:
    commands: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], timeout: float = 30.0):
        commands.append(command)
        return Result()

    monkeypatch.setattr("scripts.watch_origin_runtime_lease.run_process", fake_run)
    ok, error = execute_recovery_action("Ubuntu", "restart")

    assert ok is True
    assert error is None
    assert commands == [
        [
            "wsl.exe",
            "-d",
            "Ubuntu",
            "-u",
            "root",
            "--",
            "systemctl",
            "restart",
            "tailscaled",
        ]
    ]
