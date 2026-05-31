from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
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
                source_url="https://example.com/hdi",
                external_job_id="1",
                raw_data={
                    "result_card": {
                        "title": "Data Engineer",
                        "company_name": "HDI AG",
                    }
                },
            ),
            RawJobRecord(
                source_name="stepstone",
                source_url="https://example.com/adesso",
                external_job_id="2",
                raw_data={
                    "result_card": {
                        "title": "Analytics Engineer",
                        "company_name": "Adesso SE",
                    }
                },
            ),
        ], "https://www.stepstone.de/jobs/data-engineer/in-hannover"


class FakeRepository:
    def __init__(self) -> None:
        self.saved_records = []
        self.finished_runs = []
        self.excluded_company_keys = {"HDI AG"}

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

    def load_aggregator_discovery_suppression_company_keys(self):
        return self.excluded_company_keys

    def load_employer_origin_candidate_company_keys(self):
        return {"HDI AG"}

    def save_market_evidence(self, **kwargs):
        return 1

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

    def save_raw_job(self, record, ingestion_run_id, search_profile_id):
        self.saved_records.append(record)
        return len(self.saved_records)

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


def test_stepstone_runner_suppresses_known_employer_origin_candidates(capsys) -> None:
    repository = FakeRepository()
    runner = JobIngestionRunner(
        repository=repository,
        connector=FakeStepStoneConnector(),
    )

    runner.run("stepstone_data_engineer_hannover")

    assert [
        record.raw_data["result_card"]["company_name"]
        for record in repository.saved_records
    ] == ["Adesso SE"]
    assert repository.finished_runs == [
        {
            "ingestion_run_id": 100,
            "total_loaded": 1,
            "inserted_count": 1,
            "duplicate_count": 0,
        }
    ]

    output = capsys.readouterr().out
    assert "1 StepStone-Ergebnisse wegen bekannter Employer-Origin-Kandidaten unterdrückt" in output
    assert "Unterdrückt: Data Engineer | HDI AG" in output
