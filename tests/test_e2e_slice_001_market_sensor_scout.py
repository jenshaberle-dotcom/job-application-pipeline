from __future__ import annotations

from scripts.run_e2e_slice_001_market_sensor_scout import (
    _reservation_payload,
    choose_reservation,
    observation_from_record,
)
from src.connectors.base import RawJobRecord


def test_ba_observation_extracts_company_role_and_location() -> None:
    record = RawJobRecord(
        source_name="bundesagentur_fuer_arbeit",
        source_url="ba://123",
        external_job_id="123",
        raw_data={
            "job": {
                "titel": "Data Engineer (m/w/d)",
                "arbeitgeber": "Fresh Data GmbH",
                "arbeitsort": {"plz": "30159", "ort": "Hannover", "land": "DE"},
            }
        },
    )

    observation = observation_from_record(
        record,
        profile_name="ba_hannover",
        search_term="Data Engineer",
        known_companies=set(),
    )

    assert observation.company_name == "Fresh Data GmbH"
    assert observation.title == "Data Engineer (m/w/d)"
    assert observation.location == "30159 Hannover DE"
    assert observation.company_known is False
    assert observation.role_profile_match is True


def test_stepstone_observation_preserves_discovery_only_company_evidence() -> None:
    record = RawJobRecord(
        source_name="stepstone",
        source_url="https://www.stepstone.de/stellenangebote--123.html",
        external_job_id="123",
        raw_data={
            "result_card": {
                "title": "Platform Engineer",
                "company_name": "Known GmbH",
                "location": "Hannover",
            }
        },
    )

    observation = observation_from_record(
        record,
        profile_name="stepstone_hannover",
        search_term="Platform Engineer",
        known_companies={"knowngmbh"},
    )

    assert observation.company_name == "Known GmbH"
    assert observation.company_known is True
    assert observation.source_name == "stepstone"


def test_reservation_prefers_unknown_role_match_and_stays_out_of_product_plane() -> None:
    known = RawJobRecord(
        source_name="bundesagentur_fuer_arbeit",
        source_url="ba://known",
        external_job_id="known",
        raw_data={"job": {"titel": "Data Engineer", "arbeitgeber": "Known GmbH"}},
    )
    fresh = RawJobRecord(
        source_name="bundesagentur_fuer_arbeit",
        source_url="ba://fresh",
        external_job_id="fresh",
        raw_data={"job": {"titel": "Analytics Engineer", "arbeitgeber": "Fresh GmbH"}},
    )
    observations = [
        observation_from_record(
            known,
            profile_name="ba",
            search_term="data",
            known_companies={"knowngmbh"},
        ),
        observation_from_record(
            fresh,
            profile_name="ba",
            search_term="data",
            known_companies={"knowngmbh"},
        ),
    ]

    reservation = choose_reservation(observations)
    assert reservation is not None
    assert reservation.company_name == "Fresh GmbH"

    payload = _reservation_payload(reservation)
    assert payload["status"] == "held_out_of_pipeline_for_cold_e2e"
    assert payload["must_not_pre_ingest"] is True
    assert "bronze" in payload["required_later_path"]
    assert "silver" in payload["required_later_path"]
    assert "gold" in payload["required_later_path"]
    assert payload["discovery_evidence_sha256"]
