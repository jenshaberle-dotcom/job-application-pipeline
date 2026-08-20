from pathlib import Path

import pytest

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
from src.ingestion.run_stage_telemetry import (
    record_ingestion_stage_counts,
    validate_stage_counts,
)
from src.ingestion.runner import JobIngestionRunner


MIGRATION = Path("db/migrations/100_add_ingestion_run_stage_counts.sql")


def make_profile(*, source_name: str, page_size: int = 25) -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name="stage-telemetry-test",
        source_name=source_name,
        search_location="remote",
        search_radius_km=None,
        offer_type=None,
        page_size=page_size,
    )


def make_record(*, source_name: str, external_id: str, title: str) -> RawJobRecord:
    return RawJobRecord(
        source_name=source_name,
        source_url=f"https://example.test/jobs/{external_id}",
        external_job_id=external_id,
        raw_data={
            "job": {
                "title": title,
                "company_name": "Example GmbH",
            }
        },
    )


class StageTelemetryRepository:
    def __init__(
        self,
        *,
        source_name: str,
        search_terms: list[str],
        page_size: int = 25,
    ) -> None:
        profile = make_profile(source_name=source_name, page_size=page_size)
        self.search_terms = [
            (profile, SearchTerm(id=index, search_term=value))
            for index, value in enumerate(search_terms, start=1)
        ]
        self.stage_counts: list[dict[str, int]] = []
        self.finished_runs: list[dict[str, int]] = []
        self.saved_records: list[RawJobRecord] = []

    def load_active_search_terms(self, profile_name):
        return self.search_terms

    def create_ingestion_run(
        self,
        source_name,
        search_profile_id,
        search_term_id=None,
        search_term=None,
        requested_url=None,
    ):
        return 100

    def update_ingestion_run_requested_url(self, ingestion_run_id, requested_url):
        return None

    def record_ingestion_stage_counts(
        self,
        *,
        ingestion_run_id,
        connector_record_count,
        post_filter_count,
    ):
        self.stage_counts.append(
            {
                "ingestion_run_id": ingestion_run_id,
                "connector_record_count": connector_record_count,
                "post_filter_count": post_filter_count,
            }
        )

    def save_raw_job(self, record, ingestion_run_id, search_profile_id):
        self.saved_records.append(record)
        return 200 + len(self.saved_records)

    def find_existing_raw_job_id(self, source_name, external_job_id):
        return 200

    def save_job_observation(self, record, ingestion_run_id, raw_job_id):
        return None

    def finish_ingestion_run(
        self,
        ingestion_run_id,
        total_loaded,
        inserted_count,
        duplicate_count,
    ):
        self.finished_runs.append(
            {
                "ingestion_run_id": ingestion_run_id,
                "total_loaded": total_loaded,
                "inserted_count": inserted_count,
                "duplicate_count": duplicate_count,
            }
        )


class KeywordFilteringConnector:
    source_name = "test-filter"
    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=False,
    )

    def fetch_jobs(self, profile, search_term):
        return (
            [
                make_record(
                    source_name=self.source_name,
                    external_id="office-1",
                    title="Office Manager",
                )
            ],
            "https://example.test/jobs",
        )


class FullFetchConnector:
    source_name = "personio:telemetry-test"
    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=True,
    )

    def fetch_jobs(self, profile, search_term):
        return (
            [
                make_record(
                    source_name=self.source_name,
                    external_id="data-1",
                    title="Data Engineer",
                ),
                make_record(
                    source_name=self.source_name,
                    external_id="office-1",
                    title="Office Manager",
                ),
            ],
            "https://example.test/xml",
        )


def test_migration_adds_nullable_stage_counts_without_historical_backfill() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "connector_record_count INTEGER" in text
    assert "post_filter_count INTEGER" in text
    assert "ingestion_runs_connector_record_count_nonnegative" in text
    assert "ingestion_runs_post_filter_count_nonnegative" in text
    assert "ingestion_runs_stage_count_order" in text
    assert "post_filter_count <= connector_record_count" in text
    assert "UPDATE ingestion_runs" not in text
    assert "DEFAULT" not in text


def test_stage_count_validation_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="connector_record_count"):
        validate_stage_counts(connector_record_count=-1, post_filter_count=0)

    with pytest.raises(ValueError, match="post_filter_count"):
        validate_stage_counts(connector_record_count=1, post_filter_count=-1)

    with pytest.raises(ValueError, match="cannot exceed"):
        validate_stage_counts(connector_record_count=1, post_filter_count=2)


def test_explicit_test_repository_receives_stage_counts() -> None:
    repository = StageTelemetryRepository(
        source_name="test-filter",
        search_terms=["Data Engineer"],
    )

    record_ingestion_stage_counts(
        repository,
        ingestion_run_id=7,
        connector_record_count=3,
        post_filter_count=1,
    )

    assert repository.stage_counts == [
        {
            "ingestion_run_id": 7,
            "connector_record_count": 3,
            "post_filter_count": 1,
        }
    ]


def test_keyword_path_distinguishes_connector_output_from_filter_zero() -> None:
    repository = StageTelemetryRepository(
        source_name="test-filter",
        search_terms=["Data Engineer"],
    )
    runner = JobIngestionRunner(
        repository=repository,
        connector=KeywordFilteringConnector(),
    )

    runner.run("stage-telemetry-test")

    assert repository.stage_counts == [
        {
            "ingestion_run_id": 100,
            "connector_record_count": 1,
            "post_filter_count": 0,
        }
    ]
    assert repository.finished_runs == [
        {
            "ingestion_run_id": 100,
            "total_loaded": 0,
            "inserted_count": 0,
            "duplicate_count": 0,
        }
    ]


def test_full_fetch_path_records_pre_and_post_filter_counts() -> None:
    repository = StageTelemetryRepository(
        source_name="personio:telemetry-test",
        search_terms=["Data Engineer"],
    )
    runner = JobIngestionRunner(
        repository=repository,
        connector=FullFetchConnector(),
    )

    runner.run("stage-telemetry-test")

    assert repository.stage_counts == [
        {
            "ingestion_run_id": 100,
            "connector_record_count": 2,
            "post_filter_count": 1,
        }
    ]
    assert repository.finished_runs == [
        {
            "ingestion_run_id": 100,
            "total_loaded": 1,
            "inserted_count": 1,
            "duplicate_count": 0,
        }
    ]
