from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
from src.connectors.registry import SourceRole
from src.ingestion.runner import JobIngestionRunner


class FakeStepStoneConnector:
    source_name = "stepstone"
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
        return [
            RawJobRecord(
                source_name="stepstone",
                source_url="https://example.com/hdi/job/123",
                external_job_id="1",
                raw_data={
                    "result_card": {
                        "title": "Data & Analytics Engineer",
                        "company_name": "HDI AG",
                    }
                },
            )
        ], "https://www.stepstone.de/jobs/data-engineer/in-hannover"


class FakeRepository:
    def __init__(self) -> None:
        self.market_evidence = []
        self.raw_job_calls = 0
        self.observation_calls = 0
        self.finished_runs = []

    def load_active_search_terms(self, profile_name):
        return [
            (
                SearchProfile(
                    id=1,
                    profile_name=profile_name,
                    source_name="stepstone",
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

    def update_ingestion_run_requested_url(self, ingestion_run_id, requested_url):
        return None

    def save_market_evidence(self, **kwargs):
        self.market_evidence.append(kwargs)
        return len(self.market_evidence)

    def save_raw_job(self, *args, **kwargs):
        self.raw_job_calls += 1
        raise AssertionError("market sensors must not write raw_jobs")

    def save_job_observation(self, *args, **kwargs):
        self.observation_calls += 1
        raise AssertionError("market sensors must not write job_observations")

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


def test_stepstone_sensor_writes_no_product_job_records(capsys) -> None:
    repository = FakeRepository()
    runner = JobIngestionRunner(
        repository=repository,
        connector=FakeStepStoneConnector(),
        source_role=SourceRole.SENSOR,
    )

    runner.run("stepstone_data_engineer_hannover")

    assert repository.raw_job_calls == 0
    assert repository.observation_calls == 0
    assert len(repository.market_evidence) == 1
    evidence = repository.market_evidence[0]
    assert evidence["company_name"] == "HDI AG"
    assert evidence["title"] == "analytics"
    assert evidence["evidence_url"] is None
    assert evidence["raw_job_external_id"] is None
    assert repository.finished_runs == [
        {
            "ingestion_run_id": 100,
            "total_loaded": 1,
            "inserted_count": 0,
            "duplicate_count": 0,
        }
    ]

    output = capsys.readouterr().out
    assert "Company/vocabulary evidence written: 1" in output
    assert "Product job writes: 0" in output
