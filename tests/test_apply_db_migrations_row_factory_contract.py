from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from psycopg.rows import dict_row

from scripts.apply_db_migrations import load_tracked_migrations, schema_migrations_exists


class _Cursor(AbstractContextManager["_Cursor"]):
    def __init__(self, *, row_factory: object, rows: list[dict[str, Any]]) -> None:
        self.row_factory = row_factory
        self.rows = rows

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, _sql: str, _params: object = None) -> None:
        return None

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class _Connection:
    def __init__(self) -> None:
        self.cursor_factories: list[object] = []
        self.calls = 0

    def cursor(self, *, row_factory: object = None) -> _Cursor:
        self.cursor_factories.append(row_factory)
        self.calls += 1
        if self.calls == 1:
            return _Cursor(row_factory=row_factory, rows=[{"exists": True}])
        if self.calls == 2:
            return _Cursor(row_factory=row_factory, rows=[{"exists": True}])
        return _Cursor(
            row_factory=row_factory,
            rows=[
                {
                    "migration_key": "104_example.sql",
                    "version_number": 104,
                    "filename": "104_example.sql",
                    "checksum_sha256": "a" * 64,
                    "execution_status": "success",
                    "execution_mode": "script_apply_exact",
                    "applied_by": "demo-001",
                }
            ],
        )


def test_schema_migration_helpers_request_dict_rows_explicitly() -> None:
    conn = _Connection()

    assert schema_migrations_exists(conn) is True
    tracked = load_tracked_migrations(conn)

    assert tracked["104_example.sql"].execution_status == "success"
    assert conn.cursor_factories == [dict_row, dict_row, dict_row]
