from src.connectors.base import RawJobRecord
from src.search_intelligence.employer_discovery_census import qualify_observation
from src.search_intelligence.employer_discovery_census_adapter import (
    market_observation_from_raw_record,
)


def test_ba_record_projects_into_common_census_observation():
    record = RawJobRecord(
        source_name="bundesagentur_fuer_arbeit",
        source_url="https://example.invalid/ba/1",
        external_job_id="ba-1",
        raw_data={"job": {
            "titel": "Machine Learning Engineer",
            "arbeitgeber": "Example GmbH",
            "arbeitsort": {"plz": "30159", "ort": "Hannover", "land": "Deutschland"},
        }},
    )
    observation = market_observation_from_raw_record(
        record, observed_at_utc="2026-09-27T20:00:00Z"
    )
    assert observation.company_name == "Example GmbH"
    assert observation.location == "30159 Hannover Deutschland"
    assert observation.reference == "ba-1"
    assert qualify_observation(observation) is not None


def test_stepstone_record_preserves_remote_hint_as_evidence():
    record = RawJobRecord(
        source_name="stepstone",
        source_url="https://www.stepstone.de/job/123",
        external_job_id="123",
        raw_data={
            "result_card": {
                "title": "Data Engineer",
                "company_name": "Remote AG",
                "location": "Deutschland",
                "remote_hint_text": "Home Office möglich",
            },
            "extraction": {"observed_at_utc": "2026-09-27T20:01:00Z"},
        },
    )
    observation = market_observation_from_raw_record(record)
    assert observation.remote_signal is True
    assert observation.observed_at_utc == "2026-09-27T20:01:00Z"
    qualified = qualify_observation(observation)
    assert qualified is not None
    assert qualified.remote_de_match is True


def test_adapter_does_not_promote_clear_out_of_target_onsite_job():
    record = RawJobRecord(
        source_name="stepstone",
        source_url="https://www.stepstone.de/job/999",
        external_job_id="999",
        raw_data={"result_card": {
            "title": "ML Engineer",
            "company_name": "Berlin AG",
            "location": "Berlin",
            "remote_hint_text": None,
        }},
    )
    observation = market_observation_from_raw_record(
        record, observed_at_utc="2026-09-27T20:02:00Z"
    )
    assert qualify_observation(observation) is None


def test_adapter_has_no_write_authority():
    import src.search_intelligence.employer_discovery_census_adapter as adapter

    source = open(adapter.__file__, encoding="utf-8").read().casefold()
    for forbidden in ("psycopg", "insert into", "update ", "delete from", "commit("):
        assert forbidden not in source
