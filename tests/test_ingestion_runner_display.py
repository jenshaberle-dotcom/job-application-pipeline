from src.connectors.base import RawJobRecord
from src.ingestion.runner import (
    get_record_display_company,
    get_record_display_title,
)


def make_record(raw_data):
    return RawJobRecord(
        source_name="test",
        source_url="https://example.com/job",
        external_job_id=None,
        raw_data=raw_data,
    )


def test_display_values_from_stepstone_result_card() -> None:
    record = make_record(
        {
            "result_card": {
                "title": "Data Engineer (m/w/d)",
                "company_name": "Example Data GmbH",
            }
        }
    )

    assert get_record_display_title(record) == "Data Engineer (m/w/d)"
    assert get_record_display_company(record) == "Example Data GmbH"


def test_display_values_from_bundesagentur_job_payload() -> None:
    record = make_record(
        {
            "job": {
                "titel": "Data Engineer",
                "arbeitgeber": "Example Arbeitgeber GmbH",
            }
        }
    )

    assert get_record_display_title(record) == "Data Engineer"
    assert get_record_display_company(record) == "Example Arbeitgeber GmbH"


def test_display_values_from_greenhouse_like_job_payload() -> None:
    record = make_record(
        {
            "job": {
                "title": "Analytics Engineer",
            }
        }
    )

    assert get_record_display_title(record) == "Analytics Engineer"
    assert get_record_display_company(record) == "<missing>"


def test_display_values_fall_back_to_missing_marker() -> None:
    record = make_record({})

    assert get_record_display_title(record) == "<missing>"
    assert get_record_display_company(record) == "<missing>"

def test_runner_persists_search_term_lineage_on_ingestion_run() -> None:
    from src.connectors.base import SearchProfile, SearchTerm
    from src.connectors.capabilities import SourceCapabilities
    from src.ingestion.runner import JobIngestionRunner

    class FakeRepository:
        def __init__(self) -> None:
            self.created_runs = []

        def load_active_search_terms(self, profile_name):
            return [
                (
                    SearchProfile(
                        id=1,
                        profile_name=profile_name,
                        source_name="test_source",
                        search_location="Hannover",
                        search_radius_km=None,
                        offer_type=None,
                        page_size=25,
                    ),
                    SearchTerm(id=42, search_term="Data Engineer"),
                )
            ]

        def create_ingestion_run(
            self,
            source_name,
            search_profile_id,
            search_term_id=None,
            search_term=None,
            requested_url=None,
        ):
            self.created_runs.append(
                {
                    "source_name": source_name,
                    "search_profile_id": search_profile_id,
                    "search_term_id": search_term_id,
                    "search_term": search_term,
                    "requested_url": requested_url,
                }
            )
            return 100

        def update_ingestion_run_requested_url(self, ingestion_run_id, requested_url):
            return None

        def finish_ingestion_run(
            self,
            ingestion_run_id,
            total_loaded,
            inserted_count,
            duplicate_count,
        ):
            return None

    class FakeConnector:
        source_name = "test_source"
        capabilities = SourceCapabilities(
            supports_keyword=True,
            supports_location=True,
            supports_radius=False,
            supports_employment_type=False,
            supports_remote_filter=False,
            supports_pagination=False,
            supports_full_fetch=False,
        )

        def fetch_jobs(self, profile, search_term):
            return [], "https://example.com/jobs?q=data-engineer"

    repository = FakeRepository()
    runner = JobIngestionRunner(repository=repository, connector=FakeConnector())

    runner.run("test_profile")

    assert repository.created_runs == [
        {
            "source_name": "test_source",
            "search_profile_id": 1,
            "search_term_id": 42,
            "search_term": "Data Engineer",
            "requested_url": None,
        }
    ]


def test_runner_persists_failure_diagnostics_on_fetch_error() -> None:
    import pytest
    import requests

    from src.connectors.base import SearchProfile, SearchTerm
    from src.connectors.capabilities import SourceCapabilities
    from src.ingestion.runner import JobIngestionRunner

    class FakeRepository:
        def __init__(self) -> None:
            self.failed_runs = []

        def load_active_search_terms(self, profile_name):
            return [
                (
                    SearchProfile(
                        id=1,
                        profile_name=profile_name,
                        source_name="test_source",
                        search_location="Hannover",
                        search_radius_km=None,
                        offer_type=None,
                        page_size=25,
                    ),
                    SearchTerm(id=42, search_term="Data Engineer"),
                )
            ]

        def create_ingestion_run(
            self,
            source_name,
            search_profile_id,
            search_term_id=None,
            search_term=None,
            requested_url=None,
        ):
            return 100

        def fail_ingestion_run(
            self,
            ingestion_run_id,
            error_message,
            error_type=None,
            error_stage=None,
        ):
            self.failed_runs.append(
                {
                    "ingestion_run_id": ingestion_run_id,
                    "error_message": error_message,
                    "error_type": error_type,
                    "error_stage": error_stage,
                }
            )

    class FakeConnector:
        source_name = "test_source"
        capabilities = SourceCapabilities(
            supports_keyword=True,
            supports_location=True,
            supports_radius=False,
            supports_employment_type=False,
            supports_remote_filter=False,
            supports_pagination=False,
            supports_full_fetch=False,
        )

        def fetch_jobs(self, profile, search_term):
            raise requests.Timeout("request timed out")

    repository = FakeRepository()
    runner = JobIngestionRunner(repository=repository, connector=FakeConnector())

    with pytest.raises(requests.Timeout):
        runner.run("test_profile")

    assert repository.failed_runs == [
        {
            "ingestion_run_id": 100,
            "error_message": "Timeout: request timed out",
            "error_type": "network_timeout",
            "error_stage": "source_request",
        }
    ]


def test_runner_fetches_full_fetch_sources_once_and_records_matched_terms() -> None:
    from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
    from src.connectors.capabilities import SourceCapabilities
    from src.ingestion.runner import JobIngestionRunner

    class FakeRepository:
        def __init__(self) -> None:
            self.created_runs = []
            self.saved_records = []
            self.finished_runs = []

        def load_active_search_terms(self, profile_name):
            profile = SearchProfile(
                id=1,
                profile_name=profile_name,
                source_name="personio:example",
                search_location="remote",
                search_radius_km=None,
                offer_type=None,
                page_size=25,
            )
            return [
                (profile, SearchTerm(id=1, search_term="Data Engineer")),
                (profile, SearchTerm(id=2, search_term="Analytics Engineer")),
                (profile, SearchTerm(id=3, search_term="ETL")),
            ]

        def create_ingestion_run(
            self,
            source_name,
            search_profile_id,
            search_term_id=None,
            search_term=None,
            requested_url=None,
        ):
            self.created_runs.append(
                {
                    "source_name": source_name,
                    "search_profile_id": search_profile_id,
                    "search_term_id": search_term_id,
                    "search_term": search_term,
                    "requested_url": requested_url,
                }
            )
            return 100

        def update_ingestion_run_requested_url(self, ingestion_run_id, requested_url):
            return None

        def save_raw_job(self, record, ingestion_run_id, search_profile_id):
            self.saved_records.append(record)
            return 200

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

    class FakeConnector:
        source_name = "personio:example"
        capabilities = SourceCapabilities(
            supports_keyword=False,
            supports_location=False,
            supports_radius=False,
            supports_employment_type=False,
            supports_remote_filter=False,
            supports_pagination=False,
            supports_full_fetch=True,
        )

        def __init__(self) -> None:
            self.fetch_calls = []

        def fetch_jobs(self, profile, search_term):
            self.fetch_calls.append(search_term.search_term)
            return (
                [
                    RawJobRecord(
                        source_name="personio:example",
                        source_url="https://example.jobs.personio.de/job/1",
                        external_job_id="1",
                        raw_data={
                            "job": {
                                "title": "Analytics Engineer",
                                "description": "ETL and Data Warehouse",
                                "company_name": "Example GmbH",
                            }
                        },
                    ),
                    RawJobRecord(
                        source_name="personio:example",
                        source_url="https://example.jobs.personio.de/job/2",
                        external_job_id="2",
                        raw_data={
                            "job": {
                                "title": "Office Manager",
                                "description": "People operations",
                                "company_name": "Example GmbH",
                            }
                        },
                    ),
                ],
                "https://example.jobs.personio.de/xml?language=de",
            )

    repository = FakeRepository()
    connector = FakeConnector()
    runner = JobIngestionRunner(repository=repository, connector=connector)

    runner.run("test_profile")

    assert connector.fetch_calls == ["*"]
    assert repository.created_runs == [
        {
            "source_name": "personio:example",
            "search_profile_id": 1,
            "search_term_id": None,
            "search_term": None,
            "requested_url": None,
        }
    ]
    assert len(repository.saved_records) == 1
    assert repository.saved_records[0].raw_data["matching"]["matched_terms"] == [
        "Data Engineer",
        "Analytics Engineer",
        "ETL",
    ]
    assert repository.finished_runs == [
        {
            "ingestion_run_id": 100,
            "total_loaded": 1,
            "inserted_count": 1,
            "duplicate_count": 0,
        }
    ]
