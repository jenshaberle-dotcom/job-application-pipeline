from __future__ import annotations

import json

from src.connectors.base import RawJobRecord
from src.ingestion.recurring_observation_evidence import (
    RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION,
)
from src.ingestion.repository import JobIngestionRepository
from src.search_intelligence.recurring_connector_economics import normalized_evidence_hash


class _CapturingCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self) -> _CapturingCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        self.calls.append((query, params))


class _CapturingConnection:
    def __init__(self, cursor: _CapturingCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> _CapturingConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> _CapturingCursor:
        return self._cursor


def _repository(connection: _CapturingConnection) -> JobIngestionRepository:
    repository = JobIngestionRepository.__new__(JobIngestionRepository)

    def get_connection() -> _CapturingConnection:
        return connection

    repository.get_connection = get_connection  # type: ignore[method-assign]
    return repository


def _record(title: str, observed_at: str) -> RawJobRecord:
    return RawJobRecord(
        source_name="personio:example",
        source_url="https://jobs.example.test/42",
        external_job_id="42",
        raw_data={
            "job": {
                "title": title,
                "location": "Hannover",
            },
            "source_specific": {"department": "Data"},
            "extraction": {"observed_at_utc": observed_at},
        },
    )


def test_distinct_executions_keep_distinct_observation_evidence_with_same_raw_job_id() -> None:
    cursor = _CapturingCursor()
    repository = _repository(_CapturingConnection(cursor))

    repository.save_job_observation(
        record=_record("Data Engineer", "2026-08-15T10:00:00Z"),
        ingestion_run_id=101,
        raw_job_id=77,
    )
    repository.save_job_observation(
        record=_record("Senior Data Engineer", "2026-08-16T10:00:00Z"),
        ingestion_run_id=202,
        raw_job_id=77,
    )

    assert len(cursor.calls) == 2
    first_sql, first_params = cursor.calls[0]
    second_sql, second_params = cursor.calls[1]
    assert first_params is not None
    assert second_params is not None

    assert "normalized_evidence" in first_sql
    assert "normalized_evidence" in second_sql
    assert first_params[3] == 101
    assert second_params[3] == 202
    assert first_params[4] == second_params[4] == 77

    first_evidence = json.loads(str(first_params[5]))
    second_evidence = json.loads(str(second_params[5]))
    assert first_evidence == {
        "source_url": "https://jobs.example.test/42",
        "raw_evidence": {
            "job": {"title": "Data Engineer", "location": "Hannover"},
            "source_specific": {"department": "Data"},
        },
    }
    assert second_evidence == {
        "source_url": "https://jobs.example.test/42",
        "raw_evidence": {
            "job": {"title": "Senior Data Engineer", "location": "Hannover"},
            "source_specific": {"department": "Data"},
        },
    }
    assert first_evidence != second_evidence

    assert normalized_evidence_hash(first_evidence) == first_params[6]
    assert normalized_evidence_hash(second_evidence) == second_params[6]
    assert first_params[6] != second_params[6]
    assert first_params[7] == second_params[7] == (
        RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION
    )


def test_run_query_metadata_is_not_persisted_as_recurring_evidence() -> None:
    cursor = _CapturingCursor()
    repository = _repository(_CapturingConnection(cursor))

    repository.save_job_observation(
        record=_record("Data Engineer", "2026-08-16T10:00:00Z"),
        ingestion_run_id=303,
        raw_job_id=77,
    )

    _, params = cursor.calls[0]
    assert params is not None
    evidence = json.loads(str(params[5]))
    assert "extraction" not in evidence["raw_evidence"]
