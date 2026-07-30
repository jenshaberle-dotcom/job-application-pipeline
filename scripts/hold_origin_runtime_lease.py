"""Hold the fail-safe origin-runtime lease from a GitHub runner.

The process owns a PostgreSQL session-level advisory lock and sends lightweight
heartbeats. Closing the process or losing the database session releases the lease
automatically.
"""

from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

import psycopg

from src.config import get_database_config
from src.search_intelligence.origin_runtime_lease import (
    acquire_runtime_lease,
    release_runtime_lease,
    runtime_lease_identity,
)

_STOP_REQUESTED = False


def _request_stop(_signum: int, _frame: object) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hold the PostgreSQL advisory-lock lease for the origin runtime."
    )
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--heartbeat-seconds", type=float, default=20.0)
    parser.add_argument("--max-seconds", type=float, default=2_100.0)
    return parser


def _write_ready(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("ready\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = build_parser().parse_args()
    if args.heartbeat_seconds <= 0:
        raise SystemExit("heartbeat-seconds must be positive")
    if args.max_seconds <= 0:
        raise SystemExit("max-seconds must be positive")

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    identity = runtime_lease_identity()
    started = time.monotonic()
    heartbeat_count = 0

    with psycopg.connect(**get_database_config(), autocommit=True) as conn:
        acquire_runtime_lease(conn)
        _write_ready(args.ready_file)
        print(
            "origin_runtime_lease=acquired "
            f"namespace={identity['namespace_key']} instance={identity['instance_key']}",
            flush=True,
        )
        try:
            while not _STOP_REQUESTED and time.monotonic() - started < args.max_seconds:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                heartbeat_count += 1
                print(
                    f"origin_runtime_lease_heartbeat={heartbeat_count}",
                    flush=True,
                )
                deadline = time.monotonic() + args.heartbeat_seconds
                while not _STOP_REQUESTED and time.monotonic() < deadline:
                    time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        finally:
            released = release_runtime_lease(conn)
            args.ready_file.unlink(missing_ok=True)
            print(
                "origin_runtime_lease=released "
                f"owned={str(released).lower()} heartbeats={heartbeat_count}",
                flush=True,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
