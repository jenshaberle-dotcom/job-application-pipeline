"""Keep Windows awake while the private origin-runtime lease is present.

Run this process continuously in the logged-in Windows session. It observes the
PostgreSQL advisory lock held by the GitHub runtime and calls
SetThreadExecutionState only while the lease is active (plus a bounded grace
period). A lost runner connection removes the lock automatically.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from pathlib import Path

import psycopg

from src.config import get_database_config
from src.search_intelligence.origin_runtime_lease import runtime_lease_present

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hold a Windows execution-state request while the origin lease exists."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--grace-seconds", type=float, default=90.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("watch_origin_runtime_lease must run in Windows")

    args = build_parser().parse_args()
    if args.poll_seconds <= 0 or args.grace_seconds < 0:
        raise SystemExit("poll-seconds must be positive and grace-seconds non-negative")

    load_env_file(args.env_file)
    wake_lock_active = False
    lease_last_seen: float | None = None

    try:
        while True:
            lease_active = False
            try:
                with psycopg.connect(**get_database_config(), autocommit=True) as conn:
                    lease_active = runtime_lease_present(conn)
            except psycopg.Error as exc:
                print(
                    "origin_runtime_lease_watch=database_unavailable "
                    f"error={exc.__class__.__name__}",
                    flush=True,
                )

            now = time.monotonic()
            if lease_active:
                lease_last_seen = now
            inside_grace = (
                lease_last_seen is not None
                and now - lease_last_seen <= args.grace_seconds
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
                f"wake_lock={str(wake_lock_active).lower()}",
                flush=True,
            )

            if args.once:
                break
            time.sleep(args.poll_seconds)
    finally:
        if wake_lock_active:
            set_windows_awake(False)
            print("origin_runtime_windows_wake_lock=released_on_exit", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
