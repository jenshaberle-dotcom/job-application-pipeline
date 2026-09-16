from __future__ import annotations

import json

import pytest

from src.ingestion.verified_inventory_exact_detail_health import (
    VerifiedInventoryExactDetailHealthRepository,
)
from src.job_lifecycle_health import (
    COVERAGE_COMPLETE_INVENTORY,
    COVERAGE_EXACT_DETAIL,
    OUTCOME_CLOSED,
    OUTCOME_NOT_SEEN,
    HealthClassification,
    JobHealthTarget,
)


def target(*, source_url: str = "https://example.jobs.personio.de/job/123?language=de") -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=17,
        raw_job_id=31,
        ingestion_run_id=41,
        source_name="personio:example",
        external_job_id="123",
        source_url=source_url,
        title="Data Engineer",
        canonical_source_type=None,
        raw_source_type=None,
    )


def closed() -> HealthClassification:
    return HealthClassification(
        outcome=OUTCOME_CLOSED,
        coverage=COVERAGE_EXACT_DETAIL,
        evidence_reason="personio_explicit_job_url_not_found",
        evidence={"provider": "personio"},
    )


class FakeCursor:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = row
        self.executions: list[tuple[str, tuple[object, ...]]] = []
        self._result: dict[str, object] | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executions.append((sql, params))
        if "FROM silver_jobs sj" in sql:
            self._result = self.row
        elif "INSERT INTO job_health_observations" in sql:
            self._result = {"id": 991}
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self._result


class FakeConnection:
    def __init__(self, row: dict[str, object]) -> None:
        self.cursor_instance = FakeCursor(row)
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance

    def commit(self) -> None:
        self.commit_count += 1


class Repository(VerifiedInventoryExactDetailHealthRepository):
    def __init__(self, current: JobHealthTarget) -> None:
        self.connection = FakeConnection(
            {
                "silver_job_id": current.silver_job_id,
                "raw_job_id": current.raw_job_id,
                "ingestion_run_id": current.ingestion_run_id,
                "source_name": current.source_name,
                "external_job_id": current.external_job_id,
                "source_url": current.source_url,
                "title": current.title,
                "canonical_source_type": current.canonical_source_type,
                "raw_source_type": current.raw_source_type,
            }
        )

    def get_connection(self):
        return self.connection


def test_verified_inventory_writer_accepts_legacy_target_without_historical_source_type() -> None:
    current = target()
    repository = Repository(current)

    observation_id = repository.append_verified_inventory_exact_detail_health_observation(
        expected_target=current,
        classification=closed(),
        observed_by="test_verified_inventory",
    )

    assert observation_id == 991
    assert repository.connection.commit_count == 1
    inserts = [
        item
        for item in repository.connection.cursor_instance.executions
        if "INSERT INTO job_health_observations" in item[0]
    ]
    assert len(inserts) == 1
    params = inserts[0][1]
    assert params[5] == OUTCOME_CLOSED
    assert params[6] == COVERAGE_EXACT_DETAIL
    assert json.loads(str(params[8])) == {"provider": "personio"}
    assert params[9] == "test_verified_inventory"


def test_verified_inventory_writer_rejects_target_identity_drift() -> None:
    expected = target()
    repository = Repository(target(source_url="https://example.jobs.personio.de/job/999?language=de"))

    with pytest.raises(ValueError, match="Source URL mismatch"):
        repository.append_verified_inventory_exact_detail_health_observation(
            expected_target=expected,
            classification=closed(),
            observed_by="test_verified_inventory",
        )

    assert repository.connection.commit_count == 0


def test_verified_inventory_writer_rejects_non_exact_or_non_terminal_classification() -> None:
    current = target()
    repository = Repository(current)
    wrong_coverage = HealthClassification(
        outcome=OUTCOME_NOT_SEEN,
        coverage=COVERAGE_COMPLETE_INVENTORY,
        evidence_reason="inventory_absence",
        evidence={},
    )

    with pytest.raises(ValueError, match="exact_detail coverage"):
        repository.append_verified_inventory_exact_detail_health_observation(
            expected_target=current,
            classification=wrong_coverage,
            observed_by="test_verified_inventory",
        )

    assert repository.connection.cursor_instance.executions == []
