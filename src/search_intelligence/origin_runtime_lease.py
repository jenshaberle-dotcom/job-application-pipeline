"""Fail-safe PostgreSQL advisory-lock lease for the private origin runtime.

The GitHub runner owns a session-level advisory lock while local Windows, WSL,
Docker and PostgreSQL are needed. A local Windows watcher observes that lock and
holds an OS execution-state request. The lease disappears automatically when the
runner connection closes, so a crashed workflow cannot keep the workstation awake
indefinitely.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection

LEASE_NAMESPACE_KEY = 1_246_776_400
LEASE_INSTANCE_KEY = 1


def acquire_runtime_lease(conn: Connection[Any]) -> None:
    """Acquire the session-level origin-runtime lease on ``conn``."""

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_lock(%s, %s)",
            (LEASE_NAMESPACE_KEY, LEASE_INSTANCE_KEY),
        )


def release_runtime_lease(conn: Connection[Any]) -> bool:
    """Release the lease owned by ``conn`` and report whether it was held."""

    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_unlock(%s, %s)",
            (LEASE_NAMESPACE_KEY, LEASE_INSTANCE_KEY),
        )
        row = cur.fetchone()
    return bool(row and row[0])


def runtime_lease_present(conn: Connection[Any]) -> bool:
    """Return whether any session currently owns the origin-runtime lease."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_locks
                WHERE locktype = 'advisory'
                  AND classid = %s
                  AND objid = %s
                  AND granted
            )
            """,
            (LEASE_NAMESPACE_KEY, LEASE_INSTANCE_KEY),
        )
        row = cur.fetchone()
    return bool(row and row[0])


def runtime_lease_identity() -> dict[str, int]:
    """Return non-secret identifiers for audit output and tests."""

    return {
        "namespace_key": LEASE_NAMESPACE_KEY,
        "instance_key": LEASE_INSTANCE_KEY,
    }
