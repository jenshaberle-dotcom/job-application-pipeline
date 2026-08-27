from __future__ import annotations

import pytest

from src.job_lifecycle_health import (
    COVERAGE_COMPLETE_INVENTORY,
    OUTCOME_NOT_SEEN,
    HealthClassification,
    JobHealthTarget,
    JobLifecycleHealthRepository,
)


def target(index: int) -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=index,
        raw_job_id=100 + index,
        ingestion_run_id=200 + index,
        source_name="personio:eraneos",
        external_job_id=f"job-{index}",
        source_url=(
            "https://eraneos.jobs.personio.de/job/"
            f"job-{index}?language=de"
        ),
        title="Example role",
        canonical_source_type=(
            "employer_origin_ats_backed_career_site"
        ),
        raw_source_type=(
            "employer_origin_ats_backed_career_site"
        ),
    )


def row_for(value: JobHealthTarget) -> dict:
    return {
        "silver_job_id": value.silver_job_id,
        "raw_job_id": value.raw_job_id,
        "ingestion_run_id": value.ingestion_run_id,
        "source_name": value.source_name,
        "external_job_id": value.external_job_id,
        "source_url": value.source_url,
        "title": value.title,
        "canonical_source_type": value.canonical_source_type,
        "raw_source_type": value.raw_source_type,
    }


def classification() -> HealthClassification:
    return HealthClassification(
        outcome=OUTCOME_NOT_SEEN,
        coverage=COVERAGE_COMPLETE_INVENTORY,
        evidence_reason="verified complete inventory absence",
        evidence={"contract": "test"},
    )


class FakeCursor:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.next_row = None
        self.next_rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params) -> None:
        normalized = " ".join(query.split())

        if "FROM gold_job_lifecycle_health lifecycle" in normalized:
            self.connection.lifecycle_query = normalized
            self.next_rows = list(self.connection.active_rows)
            return

        if normalized.startswith("SELECT "):
            self.next_row = self.connection.rows[int(params[0])]
            return

        if normalized.startswith(
            "INSERT INTO job_health_observations"
        ):
            self.connection.insert_attempts += 1

            if (
                self.connection.fail_on_insert
                == self.connection.insert_attempts
            ):
                raise RuntimeError("simulated batch insert failure")

            observation_id = 9000 + self.connection.insert_attempts
            self.connection.pending_rows.append(tuple(params))
            self.next_row = {"id": observation_id}
            return

        raise AssertionError(f"unexpected SQL: {normalized}")

    def fetchone(self):
        return self.next_row

    def fetchall(self):
        return list(self.next_rows)


class FakeConnection:
    def __init__(
        self,
        rows: dict[int, dict],
        *,
        active_rows: list[dict] | None = None,
        fail_on_insert: int | None = None,
    ) -> None:
        self.rows = rows
        self.active_rows = list(active_rows or [])
        self.lifecycle_query = ""
        self.fail_on_insert = fail_on_insert
        self.insert_attempts = 0
        self.pending_rows: list[tuple] = []
        self.committed_rows: list[tuple] = []
        self.commit_calls = 0
        self.rollback_seen = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.pending_rows.clear()
            self.rollback_seen = True
        return False

    def cursor(self):
        return FakeCursor(self)

    def commit(self) -> None:
        self.commit_calls += 1
        self.committed_rows.extend(self.pending_rows)
        self.pending_rows.clear()


def repository_for(connection: FakeConnection):
    repository = object.__new__(JobLifecycleHealthRepository)
    repository.get_connection = lambda: connection
    return repository


def test_batch_health_write_commits_all_rows_once() -> None:
    first = target(1)
    second = target(2)

    connection = FakeConnection(
        {
            1: row_for(first),
            2: row_for(second),
        }
    )

    repository = repository_for(connection)

    ids = repository.append_complete_inventory_absence_batch(
        expected_classifications=[
            (first, classification()),
            (second, classification()),
        ],
        expected_source_name="personio:eraneos",
        observed_by="batch-test",
        ingestion_run_id=77,
    )

    assert ids == [9001, 9002]
    assert connection.commit_calls == 1
    assert len(connection.committed_rows) == 2
    assert connection.rollback_seen is False


def test_batch_failure_has_no_committed_partial_rows() -> None:
    first = target(1)
    second = target(2)

    connection = FakeConnection(
        {
            1: row_for(first),
            2: row_for(second),
        },
        fail_on_insert=2,
    )

    repository = repository_for(connection)

    with pytest.raises(
        RuntimeError,
        match="simulated batch insert failure",
    ):
        repository.append_complete_inventory_absence_batch(
            expected_classifications=[
                (first, classification()),
                (second, classification()),
            ],
            expected_source_name="personio:eraneos",
            observed_by="batch-test",
            ingestion_run_id=78,
        )

    assert connection.commit_calls == 0
    assert connection.committed_rows == []
    assert connection.pending_rows == []
    assert connection.rollback_seen is True



def test_verified_inventory_loader_accepts_legacy_active_target_without_source_type(
) -> None:
    legacy = JobHealthTarget(
        silver_job_id=7,
        raw_job_id=107,
        ingestion_run_id=207,
        source_name="personio:eraneos",
        external_job_id="legacy-7",
        source_url=(
            "https://eraneos.jobs.personio.de/job/legacy-7"
            "?language=de"
        ),
        title="Legacy role",
        canonical_source_type=None,
        raw_source_type=None,
    )

    connection = FakeConnection(
        {7: row_for(legacy)},
        active_rows=[row_for(legacy)],
    )
    repository = repository_for(connection)

    loaded = (
        repository
        .load_active_targets_for_verified_complete_inventory_source(
            "personio:eraneos"
        )
    )

    assert loaded == [legacy]
    assert "lifecycle.lifecycle_status = 'active_confirmed'" in (
        connection.lifecycle_query
    )
    assert "canonical_source_type IN" not in connection.lifecycle_query
    assert "raw_data->>'source_type' IN" not in connection.lifecycle_query


def test_complete_inventory_batch_accepts_legacy_target_after_source_authority(
) -> None:
    legacy = JobHealthTarget(
        silver_job_id=8,
        raw_job_id=108,
        ingestion_run_id=208,
        source_name="personio:eraneos",
        external_job_id="legacy-8",
        source_url=(
            "https://eraneos.jobs.personio.de/job/legacy-8"
            "?language=de"
        ),
        title="Legacy role",
        canonical_source_type=None,
        raw_source_type=None,
    )

    connection = FakeConnection({8: row_for(legacy)})
    repository = repository_for(connection)

    ids = repository.append_complete_inventory_absence_batch(
        expected_classifications=[
            (legacy, classification()),
        ],
        expected_source_name="personio:eraneos",
        observed_by="batch-test",
        ingestion_run_id=88,
    )

    assert ids == [9001]
    assert connection.commit_calls == 1
    assert len(connection.committed_rows) == 1


def test_complete_inventory_batch_rejects_other_classification_before_write(
) -> None:
    current = target(9)
    connection = FakeConnection({9: row_for(current)})
    repository = repository_for(connection)

    invalid = HealthClassification(
        outcome="closed",
        coverage="exact_detail",
        evidence_reason="must not enter inventory batch",
        evidence={},
    )

    with pytest.raises(
        ValueError,
        match="only accepts not_seen/complete_inventory",
    ):
        repository.append_complete_inventory_absence_batch(
            expected_classifications=[(current, invalid)],
            expected_source_name="personio:eraneos",
            observed_by="batch-test",
            ingestion_run_id=89,
        )

    assert connection.insert_attempts == 0
    assert connection.commit_calls == 0



def test_normal_health_append_does_not_accept_legacy_target_from_complete_inventory_authority(
) -> None:
    legacy = JobHealthTarget(
        silver_job_id=10,
        raw_job_id=110,
        ingestion_run_id=210,
        source_name="personio:eraneos",
        external_job_id="legacy-10",
        source_url=(
            "https://eraneos.jobs.personio.de/job/legacy-10"
            "?language=de"
        ),
        title="Legacy role",
        canonical_source_type=None,
        raw_source_type=None,
    )

    connection = FakeConnection({10: row_for(legacy)})
    repository = repository_for(connection)

    exact_detail = HealthClassification(
        outcome="closed",
        coverage="exact_detail",
        evidence_reason="explicit exact-detail closure",
        evidence={},
    )

    with pytest.raises(
        ValueError,
        match=(
            "Target is not an employer_origin_career_site or "
            "employer_origin_ats_backed_career_site vacancy"
        ),
    ):
        repository.append_health_observation(
            expected_target=legacy,
            classification=exact_detail,
            observed_by="exact-detail-test",
            ingestion_run_id=90,
        )

    assert connection.insert_attempts == 0
    assert connection.commit_calls == 0
