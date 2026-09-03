from __future__ import annotations

from scripts.run_e2e_slice_001_market_sensor_scout import (
    _reservation_payload,
    choose_reservation,
    fresh_company_names,
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


def test_new_jobs_at_known_company_are_not_new_market_discoveries() -> None:
    records = [
        RawJobRecord(
            source_name="stepstone",
            source_url=f"https://www.stepstone.de/stellenangebote--{job_id}.html",
            external_job_id=job_id,
            raw_data={
                "result_card": {
                    "title": title,
                    "company_name": "Known GmbH",
                    "location": "Hannover",
                }
            },
        )
        for job_id, title in (
            ("101", "Data Engineer"),
            ("102", "Analytics Engineer"),
        )
    ]
    observations = [
        observation_from_record(
            record,
            profile_name="stepstone_hannover",
            search_term="Data",
            known_companies={"knowngmbh"},
        )
        for record in records
    ]

    assert fresh_company_names(observations) == []
    assert choose_reservation(observations) is None


def test_multiple_jobs_from_one_unknown_company_count_as_one_company() -> None:
    records = [
        RawJobRecord(
            source_name="bundesagentur_fuer_arbeit",
            source_url=f"ba://{job_id}",
            external_job_id=job_id,
            raw_data={
                "job": {
                    "titel": title,
                    "arbeitgeber": "Fresh GmbH",
                }
            },
        )
        for job_id, title in (
            ("201", "Data Engineer"),
            ("202", "Analytics Engineer"),
        )
    ]
    observations = [
        observation_from_record(
            record,
            profile_name="ba",
            search_term="data",
            known_companies=set(),
        )
        for record in records
    ]

    assert fresh_company_names(observations) == ["Fresh GmbH"]


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
    assert payload["discovery_unit"] == "company"
    assert payload["job_record_semantics"] == "discovery_evidence_only"
    assert "bronze" in payload["required_later_path"]
    assert "silver" in payload["required_later_path"]
    assert "gold" in payload["required_later_path"]
    assert payload["discovery_evidence_sha256"]


class _KnownCompanyCursor:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = str(query)

    def fetchall(self):
        for table, rows in self.rows_by_table.items():
            if f"FROM {table}" in self.query:
                return rows
        return []


class _KnownCompanyConnection:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table

    def cursor(self):
        return _KnownCompanyCursor(self.rows_by_table)

    def rollback(self):
        pass


def test_market_evidence_only_company_is_already_known() -> None:
    from scripts.run_e2e_slice_001_market_sensor_scout import (
        _load_known_companies,
    )

    conn = _KnownCompanyConnection(
        {
            "market_evidence": [
                {"company_name": "Historical Market GmbH"},
            ],
        }
    )

    known = _load_known_companies(conn)

    assert "historicalmarketgmbh" in known


def test_raw_jobs_only_company_is_already_known() -> None:
    from scripts.run_e2e_slice_001_market_sensor_scout import (
        _load_known_companies,
    )

    conn = _KnownCompanyConnection(
        {
            "raw_jobs": [
                {"company_name": "Historical Raw GmbH"},
            ],
        }
    )

    known = _load_known_companies(conn)

    assert "historicalrawgmbh" in known


def test_existing_cold_reservation_is_never_overwritten(tmp_path) -> None:
    from scripts.run_e2e_slice_001_market_sensor_scout import (
        write_reservation_once,
    )

    first_record = RawJobRecord(
        source_name="bundesagentur_fuer_arbeit",
        source_url="ba://first",
        external_job_id="first",
        raw_data={
            "job": {
                "titel": "Data Engineer",
                "arbeitgeber": "First Fresh GmbH",
            }
        },
    )

    second_record = RawJobRecord(
        source_name="bundesagentur_fuer_arbeit",
        source_url="ba://second",
        external_job_id="second",
        raw_data={
            "job": {
                "titel": "Analytics Engineer",
                "arbeitgeber": "Second Fresh GmbH",
            }
        },
    )

    first = observation_from_record(
        first_record,
        profile_name="ba",
        search_term="data",
        known_companies=set(),
    )

    second = observation_from_record(
        second_record,
        profile_name="ba",
        search_term="data",
        known_companies=set(),
    )

    reservation_path = tmp_path / "reserved.json"

    assert write_reservation_once(reservation_path, first) is True

    original = reservation_path.read_bytes()

    assert write_reservation_once(reservation_path, second) is False
    assert reservation_path.read_bytes() == original
