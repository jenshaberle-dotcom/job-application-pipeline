from __future__ import annotations

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
from src.ingestion.runner import JobIngestionRunner


PROFILE = SearchProfile(
    id=42,
    profile_name="example_origin",
    source_name="example:origin",
    search_location=None,
    search_radius_km=None,
    offer_type=None,
    page_size=25,
)


class FakeRepository:
    def __init__(self) -> None:
        self.finished = False
        self.failed = False
        self.failure = None

    def load_active_search_terms(self, profile_name: str):
        assert profile_name == PROFILE.profile_name
        return [(PROFILE, SearchTerm(id=1, search_term="data"))]

    def create_ingestion_run(
        self,
        source_name,
        search_profile_id,
        search_term_id=None,
        search_term=None,
    ):
        return 99

    def update_ingestion_run_requested_url(self, **kwargs):
        pass

    def save_raw_job(self, **kwargs):
        return 123

    def find_existing_raw_job_id(self, **kwargs):
        return None

    def save_job_observation(self, **kwargs):
        pass

    def finish_ingestion_run(self, **kwargs):
        self.finished = True

    def fail_ingestion_run(self, **kwargs):
        self.failed = True
        self.failure = kwargs


class FakeConnector:
    source_name = "example:origin"

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
                RawJobRecord(
                    source_name=self.source_name,
                    source_url="https://jobs.example.com/job/1",
                    external_job_id="job-1",
                    raw_data={
                        "job": {
                            "title": "Data Engineer",
                            "company_name": "Example",
                        }
                    },
                )
            ],
            "https://jobs.example.com/",
        )


def test_full_fetch_passes_unfiltered_inventory_to_recurring_health(
    monkeypatch,
) -> None:
    repository = FakeRepository()
    health_repository = object()
    captured = {}

    monkeypatch.setattr(
        "src.ingestion.runner.record_ingestion_stage_counts",
        lambda *args, **kwargs: None,
    )

    def fake_reconcile(**kwargs):
        captured.update(kwargs)

        class Summary:
            target_count = 1
            observed_target_count = 1
            missing_target_count = 0
            probe_count = 0
            seen_active_write_count = 0
            closed_write_count = 0
            unverifiable_count = 0

        return Summary()

    monkeypatch.setattr(
        "src.ingestion.runner.reconcile_recurring_exact_detail_health",
        fake_reconcile,
    )

    runner = JobIngestionRunner(
        repository=repository,
        connector=FakeConnector(),
        health_repository=health_repository,
    )

    runner.run(PROFILE.profile_name)

    assert repository.finished is True
    assert captured["health_repository"] is health_repository
    assert captured["source_name"] == "example:origin"
    assert captured["ingestion_run_id"] == 99

    records = captured["observed_records"]
    assert len(records) == 1
    assert records[0].external_job_id == "job-1"



def test_full_fetch_health_failure_prevents_success_and_marks_run_failed(
    monkeypatch,
) -> None:
    repository = FakeRepository()

    monkeypatch.setattr(
        "src.ingestion.runner.record_ingestion_stage_counts",
        lambda *args, **kwargs: None,
    )

    def failed_reconcile(**kwargs):
        raise RuntimeError("bounded health failure")

    monkeypatch.setattr(
        "src.ingestion.runner.reconcile_recurring_exact_detail_health",
        failed_reconcile,
    )

    runner = JobIngestionRunner(
        repository=repository,
        connector=FakeConnector(),
        health_repository=object(),
    )

    import pytest

    with pytest.raises(RuntimeError, match="bounded health failure"):
        runner.run(PROFILE.profile_name)

    assert repository.finished is False
    assert repository.failed is True
    assert repository.failure is not None
    assert repository.failure["ingestion_run_id"] == 99
    assert repository.failure["error_type"] == "RuntimeError"
    assert (
        repository.failure["error_stage"]
        == "recurring_lifecycle_health"
    )


def test_verified_complete_inventory_skips_exact_detail_fallback(
    monkeypatch,
) -> None:
    repository = FakeRepository()
    captured = {}

    monkeypatch.setattr(
        "src.ingestion.runner.record_ingestion_stage_counts",
        lambda *args, **kwargs: None,
    )

    class InventorySummary:
        authority_target_key = "eraneos"
        target_count = 2
        observed_target_count = 1
        missing_target_count = 1
        not_seen_write_count = 1

    def complete_inventory_reconcile(**kwargs):
        captured.update(kwargs)
        return InventorySummary()

    def forbidden_exact_detail(**kwargs):
        raise AssertionError(
            "verified complete inventory must skip detail fallback"
        )

    monkeypatch.setattr(
        "src.ingestion.runner."
        "reconcile_verified_complete_inventory_health",
        complete_inventory_reconcile,
    )
    monkeypatch.setattr(
        "src.ingestion.runner."
        "reconcile_recurring_exact_detail_health",
        forbidden_exact_detail,
    )

    runner = JobIngestionRunner(
        repository=repository,
        connector=FakeConnector(),
        health_repository=object(),
    )

    runner.run(PROFILE.profile_name)

    assert repository.finished is True
    assert repository.failed is False
    assert captured["ingestion_run_id"] == 99
    assert captured["source_name"] == "example:origin"
    assert len(captured["observed_records"]) == 1
