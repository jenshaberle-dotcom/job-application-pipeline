from __future__ import annotations

from typing import Any

import pytest

import src.run_silver_jobs as run_silver_jobs
from src.silver.successfactors_location_projection import (
    AUTOMATIC_EVIDENCE_SOURCE,
    build_successfactors_location_projection,
    write_silver_job_with_successfactors_locations,
)


EVIDENCE_TEXT = "Essen, DE Hannover, DE München, DE"


def make_raw_job(*, locations: object = None, include_locations: bool = True) -> dict:
    job = {
        "title": "(Senior) Data Engineer Data & AI (f/m/d)",
        "company_name": "E.ON Digital Technology GmbH",
        "location": "Essen",
    }
    if include_locations:
        job["locations"] = (
            [
                {
                    "city": "Essen",
                    "country_code": "DE",
                    "evidence_source": AUTOMATIC_EVIDENCE_SOURCE,
                    "evidence_text": EVIDENCE_TEXT,
                },
                {
                    "city": "Hannover",
                    "country_code": "DE",
                    "evidence_source": AUTOMATIC_EVIDENCE_SOURCE,
                    "evidence_text": EVIDENCE_TEXT,
                },
                {
                    "city": "München",
                    "country_code": "DE",
                    "evidence_source": AUTOMATIC_EVIDENCE_SOURCE,
                    "evidence_text": EVIDENCE_TEXT,
                },
            ]
            if locations is None
            else locations
        )
    return {
        "id": 27001,
        "source_name": "successfactors:eon_germany",
        "external_job_id": "eon_germany:future-job",
        "source_url": "https://careers.eon.com/deutschland/job/example/999/",
        "raw_data": {
            "job": job,
            "observed_at_utc": "2026-08-05T07:30:00+00:00",
        },
    }


def make_silver_job() -> dict:
    return {
        "raw_job_id": 27001,
        "source_name": "successfactors:eon_germany",
        "external_job_id": "eon_germany:future-job",
        "source_url": "https://careers.eon.com/deutschland/job/example/999/",
        "title": "(Senior) Data Engineer Data & AI (f/m/d)",
        "company_name": "E.ON Digital Technology GmbH",
        "city": "Essen",
        "postal_code": None,
        "country": "DE",
        "publication_date": None,
        "normalized_title": "(senior) data engineer data & ai (f/m/d)",
        "normalized_company_name": "e.on digital technology gmbh",
        "normalized_location": "essen | de",
        "canonical_status": "discovery_only",
        "canonical_source_type": "employer_origin_ats_backed_career_site",
        "canonical_key_candidate": (
            "e.on digital technology gmbh :: "
            "(senior) data engineer data & ai (f/m/d) :: essen | de"
        ),
    }


class RecordingCursor:
    def __init__(self, *, fail_on_location_insert: bool = False) -> None:
        self.calls: list[tuple[str, object]] = []
        self.fail_on_location_insert = fail_on_location_insert

    def __enter__(self) -> "RecordingCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, query: str, params: object = None) -> None:
        normalized = " ".join(query.split())
        self.calls.append((normalized, params))
        if self.fail_on_location_insert and normalized.startswith(
            "INSERT INTO silver_job_locations"
        ):
            raise RuntimeError("synthetic location insert failure")

    def fetchone(self) -> dict[str, int]:
        return {"id": 8801}


class RecordingConnection:
    def __init__(self, *, fail_on_location_insert: bool = False) -> None:
        self.cursor_instance = RecordingCursor(
            fail_on_location_insert=fail_on_location_insert
        )
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def cursor(self) -> RecordingCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1


class RecordingRepository:
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    def get_connection(self) -> RecordingConnection:
        return self.connection


def test_projection_preserves_order_and_matches_legacy_city_as_primary() -> None:
    projection = build_successfactors_location_projection(
        make_raw_job(),
        legacy_city="Essen",
    )

    assert projection.authoritative is True
    assert [(row.city, row.country_code) for row in projection.rows] == [
        ("Essen", "DE"),
        ("Hannover", "DE"),
        ("München", "DE"),
    ]
    assert [row.is_primary for row in projection.rows] == [True, False, False]
    assert all(
        row.evidence_source == AUTOMATIC_EVIDENCE_SOURCE
        for row in projection.rows
    )


def test_missing_structured_field_is_non_authoritative_for_legacy_records() -> None:
    projection = build_successfactors_location_projection(
        make_raw_job(include_locations=False),
        legacy_city="Essen",
    )

    assert projection.authoritative is False
    assert projection.rows == ()


def test_explicit_empty_structured_field_is_authoritative() -> None:
    projection = build_successfactors_location_projection(
        make_raw_job(locations=[]),
        legacy_city="Essen",
    )

    assert projection.authoritative is True
    assert projection.rows == ()


def test_malformed_or_duplicate_authoritative_locations_fail_closed() -> None:
    duplicate = [
        {
            "city": "Hannover",
            "country_code": "DE",
            "evidence_source": AUTOMATIC_EVIDENCE_SOURCE,
            "evidence_text": "Hannover, DE",
        },
        {
            "city": " hannover ",
            "country_code": "de",
            "evidence_source": AUTOMATIC_EVIDENCE_SOURCE,
            "evidence_text": "Hannover, DE",
        },
    ]

    with pytest.raises(ValueError, match="duplicate structured"):
        build_successfactors_location_projection(
            make_raw_job(locations=duplicate),
            legacy_city="Hannover",
        )

    malformed = [
        {
            "city": "Remote",
            "country_code": "DE",
            "evidence_source": AUTOMATIC_EVIDENCE_SOURCE,
            "evidence_text": "Remote",
        }
    ]
    with pytest.raises(ValueError, match="work model"):
        build_successfactors_location_projection(
            make_raw_job(locations=malformed),
            legacy_city="Essen",
        )


def test_atomic_writer_upserts_silver_and_three_locations_in_one_commit() -> None:
    connection = RecordingConnection()
    repository = RecordingRepository(connection)

    silver_job_id = write_silver_job_with_successfactors_locations(
        repository,
        silver_job=make_silver_job(),
        raw_job=make_raw_job(),
    )

    assert silver_job_id == 8801
    assert connection.commit_count == 1
    assert connection.rollback_count == 0
    assert connection.close_count == 1

    calls = connection.cursor_instance.calls
    assert calls[0][0].startswith("INSERT INTO silver_jobs")
    assert "RETURNING id" in calls[0][0]
    assert "UPDATE silver_job_locations" in calls[1][0]
    assert calls[2][0].startswith("DELETE FROM silver_job_locations")

    location_inserts = [
        call for call in calls if call[0].startswith("INSERT INTO silver_job_locations")
    ]
    assert len(location_inserts) == 3
    assert [call[1][1] for call in location_inserts] == [
        "Essen",
        "Hannover",
        "München",
    ]
    assert [call[1][3] for call in location_inserts] == [True, False, False]
    assert all("ON CONFLICT" in call[0] for call in location_inserts)
    assert all("IS DISTINCT FROM" in call[0] for call in location_inserts)


def test_legacy_record_writes_silver_without_touching_location_rows() -> None:
    connection = RecordingConnection()
    repository = RecordingRepository(connection)

    write_silver_job_with_successfactors_locations(
        repository,
        silver_job=make_silver_job(),
        raw_job=make_raw_job(include_locations=False),
    )

    assert len(connection.cursor_instance.calls) == 1
    assert connection.cursor_instance.calls[0][0].startswith(
        "INSERT INTO silver_jobs"
    )
    assert connection.commit_count == 1


def test_explicit_empty_list_removes_only_automatic_location_rows() -> None:
    connection = RecordingConnection()
    repository = RecordingRepository(connection)

    write_silver_job_with_successfactors_locations(
        repository,
        silver_job=make_silver_job(),
        raw_job=make_raw_job(locations=[]),
    )

    calls = connection.cursor_instance.calls
    assert len(calls) == 3
    assert "UPDATE silver_job_locations" in calls[1][0]
    assert calls[1][1] == (8801, AUTOMATIC_EVIDENCE_SOURCE)
    assert calls[2][0].startswith("DELETE FROM silver_job_locations")
    assert calls[2][1][0:2] == (8801, AUTOMATIC_EVIDENCE_SOURCE)
    assert calls[2][1][2] == "[]"


def test_location_failure_rolls_back_silver_write_and_closes_connection() -> None:
    connection = RecordingConnection(fail_on_location_insert=True)
    repository = RecordingRepository(connection)

    with pytest.raises(RuntimeError, match="synthetic location insert failure"):
        write_silver_job_with_successfactors_locations(
            repository,
            silver_job=make_silver_job(),
            raw_job=make_raw_job(),
        )

    assert connection.commit_count == 0
    assert connection.rollback_count == 1
    assert connection.close_count == 1


def test_standard_silver_runner_uses_atomic_writer(monkeypatch, capsys) -> None:
    raw_job = make_raw_job()
    silver_job = make_silver_job()
    writer_calls: list[tuple[Any, dict, dict]] = []

    class FakeRepository:
        def load_unprocessed_raw_jobs(self, **kwargs):
            assert kwargs["source_patterns"] == ["successfactors:eon_germany"]
            return [raw_job]

        def record_processing_decision(self, **kwargs) -> None:
            assert kwargs["decision"] == "included"

        def upsert_silver_job(self, job) -> None:
            raise AssertionError("legacy non-atomic writer must not be called")

    repository = FakeRepository()
    monkeypatch.setattr(run_silver_jobs, "SilverJobRepository", lambda: repository)
    monkeypatch.setattr(run_silver_jobs, "get_role_matches", lambda value: [])
    monkeypatch.setattr(run_silver_jobs, "get_skill_matches", lambda value: [])
    monkeypatch.setattr(
        run_silver_jobs,
        "get_accessibility_matches",
        lambda value: [],
    )
    monkeypatch.setattr(run_silver_jobs, "is_relevant_for_silver", lambda value: True)
    monkeypatch.setattr(
        run_silver_jobs,
        "transform_raw_job_to_silver",
        lambda value: silver_job,
    )

    def fake_writer(repo, *, silver_job, raw_job) -> int:
        writer_calls.append((repo, silver_job, raw_job))
        return 8801

    monkeypatch.setattr(
        run_silver_jobs,
        "write_silver_job_with_successfactors_locations",
        fake_writer,
    )

    run_silver_jobs.main(["--source", "successfactors:eon_germany"])

    assert writer_calls == [(repository, silver_job, raw_job)]
    assert "Transformed raw jobs: 1" in capsys.readouterr().out
