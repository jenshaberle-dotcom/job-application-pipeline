from src.connectors.base import RawJobRecord
from src.ingestion.runner import record_market_sensor_evidence
from src.search_intelligence.market_sensor_evidence_contract import (
    build_market_sensor_evidence_payload,
)


class FakeRepository:
    def __init__(self) -> None:
        self.calls = []

    def save_market_evidence(self, **kwargs):
        self.calls.append(kwargs)
        return len(self.calls)


def test_sensor_records_cross_boundary_as_company_and_vocabulary_only() -> None:
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

    written = record_market_sensor_evidence(
        repo,
        source_name="stepstone",
        records=records,
        profile_name="stepstone_data_engineer",
        search_term="data engineer",
        ingestion_run_id=42,
    )

    assert written == 1
    assert repo.calls[0]["company_name"] == "HDI AG"
    assert repo.calls[0]["title"] == "analytics"
    assert repo.calls[0]["evidence_kind"] == "market_sensor_company_sighting"
    assert repo.calls[0]["evidence_url"] is None
    assert repo.calls[0]["raw_job_external_id"] is None
    assert repo.calls[0]["evidence"]["vocabulary_terms"] == ["analytics"]
    assert repo.calls[0]["evidence"]["boundary"]["sensor_url_forwarded"] is False


def test_shared_sensor_contract_matches_ingestion_boundary() -> None:
    payload = build_market_sensor_evidence_payload(
        source_name="goodjobs",
        company_name="Example GmbH",
        display_title="Senior Data Engineer",
        search_profile_name="job_first_employer_discovery_census",
        search_term="Data Engineer",
        ingestion_run_id=None,
    )

    assert payload["evidence_source"] == "market_sensor_ingestion"
    assert payload["evidence_kind"] == "market_sensor_company_sighting"
    assert payload["company_name"] == "Example GmbH"
    assert payload["search_term"] == "Data Engineer"
    assert payload["evidence_url"] is None
    assert payload["raw_job_external_id"] is None
    assert payload["evidence"]["boundary"]["company_identity_only"] is True
    assert payload["evidence"]["boundary"]["sensor_url_forwarded"] is False
    assert payload["evidence"]["boundary"]["bronze_write"] is False
    assert payload["evidence"]["boundary"]["silver_write"] is False
    assert payload["evidence"]["boundary"]["product_write"] is False
    assert payload["evidence"]["boundary"]["candidate_creation"] is False
