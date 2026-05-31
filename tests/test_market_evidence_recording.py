from src.connectors.base import RawJobRecord
from src.ingestion.runner import record_market_evidence_for_aggregator_records


class FakeRepository:
    def __init__(self) -> None:
        self.calls = []

    def save_market_evidence(self, **kwargs):
        self.calls.append(kwargs)
        return len(self.calls)


def test_stepstone_records_are_recorded_as_market_evidence_before_suppression() -> None:
    repo = FakeRepository()
    records = [
        RawJobRecord(
            source_name="stepstone",
            source_url="https://example.test/job/1",
            external_job_id="stepstone-1",
            raw_data={
                "result_card": {
                    "company_name": "HDI AG",
                    "title": "Data & Analytics Engineer",
                }
            },
        )
    ]

    written = record_market_evidence_for_aggregator_records(
        repo,
        source_name="stepstone",
        records=records,
        profile_name="stepstone_data_engineer",
        search_term="data engineer",
        ingestion_run_id=42,
    )

    assert written == 1
    assert repo.calls[0]["company_name"] == "HDI AG"
    assert repo.calls[0]["title"] == "Data & Analytics Engineer"
    assert repo.calls[0]["evidence_kind"] == "aggregator_sighting"
