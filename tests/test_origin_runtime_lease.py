from __future__ import annotations

from typing import Any

from src.search_intelligence.origin_runtime_lease import (
    LEASE_INSTANCE_KEY,
    LEASE_NAMESPACE_KEY,
    acquire_runtime_lease,
    release_runtime_lease,
    runtime_lease_identity,
    runtime_lease_present,
)


class FakeCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, tuple[int, int]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[int, int]) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> tuple[object, ...] | None:
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.cursor_value = FakeCursor(rows)

    def cursor(self) -> FakeCursor:
        return self.cursor_value


def test_runtime_lease_uses_stable_non_secret_advisory_lock_identity() -> None:
    identity = runtime_lease_identity()
    assert identity == {
        "namespace_key": LEASE_NAMESPACE_KEY,
        "instance_key": LEASE_INSTANCE_KEY,
    }
    assert 0 < LEASE_NAMESPACE_KEY < 2**31
    assert 0 < LEASE_INSTANCE_KEY < 2**31


def test_runtime_lease_acquire_release_and_presence_queries() -> None:
    conn: Any = FakeConnection([(True,), (True,)])

    acquire_runtime_lease(conn)
    assert release_runtime_lease(conn) is True
    assert runtime_lease_present(conn) is False

    queries = conn.cursor_value.executed
    assert "pg_advisory_lock" in queries[0][0]
    assert "pg_advisory_unlock" in queries[1][0]
    assert "FROM pg_locks" in queries[2][0]
    assert all(params == (LEASE_NAMESPACE_KEY, LEASE_INSTANCE_KEY) for _, params in queries)
