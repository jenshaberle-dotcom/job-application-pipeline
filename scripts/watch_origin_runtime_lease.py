"""Keep Windows awake while the private origin runtime owns its lease.

The Windows watcher also records conservative awake-time telemetry and performs
bounded recovery of the local WSL Tailscale client when database connectivity is
repeatedly unavailable. It never logs out, re-authenticates or deletes Tailscale
state.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from src.config import get_database_config
from src.search_intelligence.origin_runtime_lease import runtime_lease_present

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
TELEMETRY_SCHEMA_VERSION = 1
AUTH_REQUIRED_BACKEND_STATES = {"NeedsLogin", "NeedsMachineAuth", "NeedsApproval"}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def set_windows_awake(required: bool) -> None:
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if required else 0)
    result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
    if result == 0:
        raise OSError("SetThreadExecutionState failed")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc_text(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def append_event(path: Path, event: str, **fields: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "timestamp_utc": utc_text(utc_now()),
        "event": event,
        **fields,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _new_metrics() -> dict[str, float | int]:
    return {
        "observed_awake_seconds": 0.0,
        "lease_active_seconds": 0.0,
        "awake_without_lease_seconds": 0.0,
        "suspend_or_unobserved_seconds": 0.0,
        "suspend_or_unobserved_events": 0,
        "tailscale_recovery_attempts": 0,
        "tailscale_recovery_successes": 0,
        "tailscale_recovery_failures": 0,
    }


def default_state(now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "last_observed_at_utc": None,
        "last_lease_active": False,
        "watcher_starts": 0,
        "totals": _new_metrics(),
        "current_day": {
            "date": current.astimezone().date().isoformat(),
            **_new_metrics(),
        },
    }


def load_state(path: Path, now: datetime) -> dict[str, Any]:
    if not path.exists():
        return default_state(now)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state(now)
    if not isinstance(payload, dict) or payload.get("schema_version") != TELEMETRY_SCHEMA_VERSION:
        return default_state(now)
    baseline = default_state(now)
    for key, value in payload.items():
        if key not in {"totals", "current_day"}:
            baseline[key] = value
    baseline["totals"].update(payload.get("totals", {}))
    baseline["current_day"].update(payload.get("current_day", {}))
    return baseline


def roll_day_if_needed(
    state: dict[str, Any],
    observed_at: datetime,
    telemetry_path: Path | None = None,
) -> None:
    current_date = observed_at.astimezone().date().isoformat()
    day = state["current_day"]
    if day["date"] == current_date:
        return
    if telemetry_path is not None:
        append_event(telemetry_path, "awake_time_daily_summary", **day)
    state["current_day"] = {"date": current_date, **_new_metrics()}


def classify_gap(delta_seconds: float, threshold_seconds: float) -> str:
    if delta_seconds <= max(0.0, threshold_seconds):
        return "observed_awake"
    return "suspend_or_unobserved"


def record_observation(
    state: dict[str, Any],
    observed_at: datetime,
    lease_active: bool,
    threshold_seconds: float,
    telemetry_path: Path | None = None,
) -> tuple[str | None, float]:
    roll_day_if_needed(state, observed_at, telemetry_path)
    previous = parse_utc_text(state.get("last_observed_at_utc"))
    previous_lease_active = bool(state.get("last_lease_active", False))
    state["last_observed_at_utc"] = utc_text(observed_at)
    state["last_lease_active"] = lease_active
    if previous is None or observed_at <= previous:
        return None, 0.0

    delta = (observed_at - previous).total_seconds()
    classification = classify_gap(delta, threshold_seconds)
    totals = state["totals"]
    day = state["current_day"]
    if classification == "observed_awake":
        totals["observed_awake_seconds"] += delta
        day["observed_awake_seconds"] += delta
        metric = "lease_active_seconds" if previous_lease_active else "awake_without_lease_seconds"
        totals[metric] += delta
        day[metric] += delta
    else:
        totals["suspend_or_unobserved_seconds"] += delta
        totals["suspend_or_unobserved_events"] += 1
        day["suspend_or_unobserved_seconds"] += delta
        day["suspend_or_unobserved_events"] += 1
    return classification, delta


def record_recovery(state: dict[str, Any], result: str) -> None:
    for metrics in (state["totals"], state["current_day"]):
        metrics["tailscale_recovery_attempts"] += 1
        if result == "completed":
            metrics["tailscale_recovery_successes"] += 1
        elif result in {"failed", "failed_closed"}:
            metrics["tailscale_recovery_failures"] += 1


def parse_wsl_state(output: str, distro: str) -> str:
    cleaned = output.replace("\x00", "")
    for raw_line in cleaned.splitlines():
        stripped = raw_line.strip().lstrip("*").strip()
        if not stripped or stripped.lower().startswith("name"):
            continue
        parts = stripped.split()
        if len(parts) >= 3 and parts[-1].isdigit():
            name = " ".join(parts[:-2])
            if name.casefold() == distro.casefold():
                return parts[-2]
    return "Unknown"


def run_process(command: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def get_wsl_state(distro: str) -> str:
    try:
        result = run_process(["wsl.exe", "--list", "--verbose"], timeout=15.0)
    except (OSError, subprocess.TimeoutExpired):
        return "Unavailable"
    if result.returncode != 0:
        return "Unavailable"
    return parse_wsl_state(result.stdout, distro)


def inspect_tailscale(distro: str, wsl_state_before: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "wsl_state_before": wsl_state_before,
        "service_state": "unavailable",
        "interface_present": False,
        "status_rc": None,
        "backend_state": None,
        "self_online": None,
        "health": [],
        "error": None,
    }
    try:
        service = run_process(
            ["wsl.exe", "-d", distro, "--", "systemctl", "is-active", "tailscaled"]
        )
        snapshot["service_state"] = service.stdout.strip() or "unknown"
        interface = run_process(
            ["wsl.exe", "-d", distro, "--", "ip", "link", "show", "tailscale0"]
        )
        snapshot["interface_present"] = interface.returncode == 0
        status = run_process(
            ["wsl.exe", "-d", distro, "--", "tailscale", "status", "--json"]
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        snapshot["error"] = exc.__class__.__name__
        return snapshot

    snapshot["status_rc"] = status.returncode
    if status.returncode != 0:
        snapshot["error"] = (status.stderr.strip() or status.stdout.strip())[:500]
        return snapshot
    try:
        payload = json.loads(status.stdout)
    except json.JSONDecodeError:
        snapshot["error"] = "invalid_status_json"
        return snapshot

    backend = payload.get("BackendState")
    snapshot["backend_state"] = str(backend) if backend is not None else None
    self_payload = payload.get("Self")
    if isinstance(self_payload, dict) and isinstance(self_payload.get("Online"), bool):
        snapshot["self_online"] = self_payload["Online"]
    health = payload.get("Health")
    if isinstance(health, list):
        snapshot["health"] = [str(item) for item in health]
    return snapshot


def classify_recovery(snapshot: dict[str, Any]) -> str:
    backend = snapshot.get("backend_state")
    error_text = str(snapshot.get("error") or "").casefold()
    authentication_error = any(
        token in error_text
        for token in ("needslogin", "needs login", "not logged in", "logged out")
    )
    if backend in AUTH_REQUIRED_BACKEND_STATES or authentication_error:
        return "fail_closed_auth"
    if snapshot.get("service_state") != "active":
        return "start"
    healthy = (
        snapshot.get("status_rc") == 0
        and backend == "Running"
        and snapshot.get("self_online") is True
        and snapshot.get("interface_present") is True
    )
    if healthy:
        if snapshot.get("wsl_state_before") == "Stopped":
            return "wsl_start_only"
        return "none"
    return "restart"


def execute_recovery_action(distro: str, action: str) -> tuple[bool, str | None]:
    if action not in {"start", "restart"}:
        return True, None
    try:
        result = run_process(
            [
                "wsl.exe",
                "-d",
                distro,
                "-u",
                "root",
                "--",
                "systemctl",
                action,
                "tailscaled",
            ]
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, exc.__class__.__name__
    if result.returncode == 0:
        return True, None
    error = result.stderr.strip() or result.stdout.strip() or f"returncode_{result.returncode}"
    return False, error[:500]


def recovery_allowed(
    now_epoch: float,
    recent_attempts: deque[float],
    last_attempt_epoch: float | None,
    cooldown_seconds: float,
    max_per_hour: int,
) -> tuple[bool, str]:
    while recent_attempts and now_epoch - recent_attempts[0] >= 3600.0:
        recent_attempts.popleft()
    if last_attempt_epoch is not None and now_epoch - last_attempt_epoch < cooldown_seconds:
        return False, "cooldown"
    if len(recent_attempts) >= max_per_hour:
        return False, "hourly_limit"
    return True, "allowed"


def observe_lease() -> tuple[bool, bool, str | None]:
    try:
        with psycopg.connect(**get_database_config(), autocommit=True) as conn:
            return True, runtime_lease_present(conn), None
    except psycopg.Error as exc:
        return False, False, exc.__class__.__name__


def attempt_recovery(
    distro: str,
    telemetry_path: Path,
    state: dict[str, Any],
    settle_seconds: float,
) -> tuple[str, str, bool, dict[str, Any]]:
    before = inspect_tailscale(distro, get_wsl_state(distro))
    action = classify_recovery(before)
    if action == "fail_closed_auth":
        result = "failed_closed"
        record_recovery(state, result)
        append_event(
            telemetry_path,
            "tailscale_recovery",
            result=result,
            action="none",
            failure_stage="authentication",
            before=before,
        )
        return result, action, False, before

    action_ok, action_error = execute_recovery_action(distro, action)
    if action in {"start", "restart", "wsl_start_only"} and action_ok and settle_seconds > 0:
        time.sleep(settle_seconds)
    after = inspect_tailscale(distro, get_wsl_state(distro))
    database_available_after, _, database_error_after = observe_lease()
    tailscale_healthy_after = classify_recovery(after) in {"none", "wsl_start_only"}
    if action_ok and tailscale_healthy_after and database_available_after:
        result = "completed"
    elif action_ok and tailscale_healthy_after:
        result = "database_unavailable"
    else:
        result = "failed"
    record_recovery(state, result)
    append_event(
        telemetry_path,
        "tailscale_recovery",
        result=result,
        action=action,
        action_error=action_error,
        before=before,
        after=after,
        database_available_after=database_available_after,
        database_error_after=database_error_after,
    )
    return result, action, database_available_after, after


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Hold the origin runtime wake lock, record awake telemetry and perform "
            "bounded local Tailscale recovery."
        )
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--grace-seconds", type=float, default=90.0)
    parser.add_argument(
        "--telemetry-output",
        type=Path,
        default=Path(".runtime/origin-runtime-watcher.jsonl"),
    )
    parser.add_argument(
        "--telemetry-state",
        type=Path,
        default=Path(".runtime/origin-runtime-watcher-state.json"),
    )
    parser.add_argument("--summary-seconds", type=float, default=900.0)
    parser.add_argument("--state-flush-seconds", type=float, default=60.0)
    parser.add_argument("--awake-gap-threshold-seconds", type=float, default=30.0)
    parser.add_argument("--wsl-distro", default="Ubuntu")
    parser.add_argument("--recovery-failures", type=int, default=3)
    parser.add_argument("--recovery-cooldown-seconds", type=float, default=600.0)
    parser.add_argument("--recovery-max-per-hour", type=int, default=3)
    parser.add_argument("--recovery-settle-seconds", type=float, default=5.0)
    parser.add_argument("--disable-tailscale-recovery", action="store_true")
    parser.add_argument("--once", action="store_true")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.poll_seconds <= 0 or args.grace_seconds < 0:
        raise SystemExit("poll-seconds must be positive and grace-seconds non-negative")
    if args.summary_seconds <= 0 or args.state_flush_seconds <= 0:
        raise SystemExit("summary-seconds and state-flush-seconds must be positive")
    if args.awake_gap_threshold_seconds < args.poll_seconds:
        raise SystemExit("awake-gap-threshold-seconds must be at least poll-seconds")
    if args.recovery_failures <= 0 or args.recovery_max_per_hour <= 0:
        raise SystemExit("recovery-failures and recovery-max-per-hour must be positive")
    if args.recovery_cooldown_seconds < 0 or args.recovery_settle_seconds < 0:
        raise SystemExit("recovery cooldown and settle seconds must be non-negative")


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("watch_origin_runtime_lease must run in Windows")

    args = build_parser().parse_args()
    validate_args(args)
    load_env_file(args.env_file)

    observed_at = utc_now()
    state = load_state(args.telemetry_state, observed_at)
    state["watcher_starts"] = int(state.get("watcher_starts", 0)) + 1
    append_event(
        args.telemetry_output,
        "watcher_started",
        watcher_starts=state["watcher_starts"],
        wsl_distro=args.wsl_distro,
        tailscale_recovery_enabled=not args.disable_tailscale_recovery,
    )

    wake_lock_active = False
    lease_last_seen: float | None = None
    consecutive_database_failures = 0
    recovery_attempts: deque[float] = deque()
    last_recovery_epoch: float | None = None
    last_flush = time.monotonic()
    last_summary = time.monotonic()

    try:
        while True:
            observed_at = utc_now()
            database_available, lease_active, database_error = observe_lease()
            consecutive_database_failures = (
                0 if database_available else consecutive_database_failures + 1
            )
            if not database_available:
                print(
                    "origin_runtime_lease_watch=database_unavailable "
                    f"error={database_error}",
                    flush=True,
                )

            classification, gap_seconds = record_observation(
                state,
                observed_at,
                lease_active,
                args.awake_gap_threshold_seconds,
                args.telemetry_output,
            )
            if classification == "suspend_or_unobserved":
                append_event(
                    args.telemetry_output,
                    "suspend_or_unobserved_gap",
                    gap_seconds=gap_seconds,
                )

            if (
                not args.disable_tailscale_recovery
                and not database_available
                and consecutive_database_failures >= args.recovery_failures
            ):
                now_epoch = time.time()
                allowed, gate = recovery_allowed(
                    now_epoch,
                    recovery_attempts,
                    last_recovery_epoch,
                    args.recovery_cooldown_seconds,
                    args.recovery_max_per_hour,
                )
                if allowed:
                    recovery_attempts.append(now_epoch)
                    last_recovery_epoch = now_epoch
                    result, action, database_available_after, after = attempt_recovery(
                        args.wsl_distro,
                        args.telemetry_output,
                        state,
                        args.recovery_settle_seconds,
                    )
                    print(
                        "origin_runtime_tailscale_recovery="
                        f"{result} action={action} "
                        f"database_available_after={str(database_available_after).lower()} "
                        f"backend_after={after.get('backend_state')}",
                        flush=True,
                    )
                    if database_available_after:
                        consecutive_database_failures = 0
                else:
                    print(
                        "origin_runtime_tailscale_recovery=deferred "
                        f"gate={gate}",
                        flush=True,
                    )

            now_monotonic = time.monotonic()
            if lease_active:
                lease_last_seen = now_monotonic
            inside_grace = (
                lease_last_seen is not None
                and now_monotonic - lease_last_seen <= args.grace_seconds
            )
            should_hold = lease_active or inside_grace
            if should_hold and not wake_lock_active:
                set_windows_awake(True)
                wake_lock_active = True
                print("origin_runtime_windows_wake_lock=acquired", flush=True)
            elif not should_hold and wake_lock_active:
                set_windows_awake(False)
                wake_lock_active = False
                lease_last_seen = None
                print("origin_runtime_windows_wake_lock=released", flush=True)

            print(
                "origin_runtime_lease_watch="
                f"{'active' if lease_active else 'idle'} "
                f"database_available={str(database_available).lower()} "
                f"wake_lock={str(wake_lock_active).lower()}",
                flush=True,
            )

            if now_monotonic - last_summary >= args.summary_seconds:
                append_event(
                    args.telemetry_output,
                    "awake_time_summary",
                    **state["current_day"],
                    totals=state["totals"],
                )
                last_summary = now_monotonic
            if now_monotonic - last_flush >= args.state_flush_seconds:
                atomic_write_json(args.telemetry_state, state)
                last_flush = now_monotonic

            if args.once:
                break
            time.sleep(args.poll_seconds)
    finally:
        if wake_lock_active:
            set_windows_awake(False)
            print("origin_runtime_windows_wake_lock=released_on_exit", flush=True)
        atomic_write_json(args.telemetry_state, state)
        append_event(args.telemetry_output, "watcher_stopped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
