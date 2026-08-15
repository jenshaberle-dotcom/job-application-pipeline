from __future__ import annotations

from pathlib import Path
from uuid import UUID

from src.config import get_database_config
from src.ingest_jobs import (
    INGESTION_EXECUTION_APPLICATION_PREFIX,
    configure_ingestion_execution_application_name,
)


def test_ingestion_invocation_sets_one_valid_application_execution_id(monkeypatch) -> None:
    monkeypatch.delenv("PGAPPNAME", raising=False)

    execution_id = configure_ingestion_execution_application_name()

    assert UUID(execution_id)
    assert (
        get_database_config()["application_name"]
        == f"{INGESTION_EXECUTION_APPLICATION_PREFIX}{execution_id}"
    )


def test_distinct_ingestion_invocations_receive_distinct_execution_ids(monkeypatch) -> None:
    monkeypatch.delenv("PGAPPNAME", raising=False)

    first = configure_ingestion_execution_application_name()
    second = configure_ingestion_execution_application_name()

    assert first != second
    assert UUID(first)
    assert UUID(second)


def test_database_config_does_not_invent_application_name(monkeypatch) -> None:
    monkeypatch.delenv("PGAPPNAME", raising=False)

    assert "application_name" not in get_database_config()


def test_migration_096_is_nullable_forward_only_execution_correlation() -> None:
    sql = (
        Path("db/migrations/096_add_ingestion_execution_correlation.sql")
        .read_text(encoding="utf-8")
        .lower()
    )

    assert "add column if not exists execution_id uuid" in sql
    assert "alter column execution_id set default" in sql
    assert "current_setting('application_name', true)" in sql
    assert "job-pipeline-ingest:%" in sql
    assert "update ingestion_runs" not in sql
    assert "add column if not exists execution_id uuid not null" not in sql
