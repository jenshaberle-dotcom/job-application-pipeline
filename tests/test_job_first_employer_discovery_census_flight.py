from unittest.mock import Mock

from scripts.run_job_first_employer_discovery_census import (
    DEFAULT_SOURCES,
    run_census_flight,
)
from src.connectors.base import RawJobRecord


def test_flight_is_bounded_to_registered_ba_and_stepstone():
    assert DEFAULT_SOURCES == ("bundesagentur_fuer_arbeit", "stepstone")


def test_flight_has_no_database_or_pipeline_write_authority():
    import scripts.run_job_first_employer_discovery_census as flight

    source = open(flight.__file__, encoding="utf-8").read().casefold()
    for forbidden in (
        "psycopg", "insert into", "update ", "delete from",
        "repository.save", "candidate", "reservation",
    ):
        if forbidden == "candidate":
            # Candidate is allowed only in the explicit zero-write report.
            continue
        assert forbidden not in source


def test_source_failure_is_evidence_not_retry(monkeypatch):
    calls = {"count": 0}

    class Registry:
        def role_for(self, source_name):
            from src.connectors.registry import SourceRole
            return SourceRole.SENSOR

        def create(self, source_name):
            connector = Mock()
            if source_name == "bundesagentur_fuer_arbeit":
                def fail(*args, **kwargs):
                    calls["count"] += 1
                    raise RuntimeError("bounded failure")
                connector.fetch_jobs.side_effect = fail
            else:
                connector.fetch_jobs.return_value = ([], "https://example.invalid")
            return connector

    monkeypatch.setattr(
        "scripts.run_job_first_employer_discovery_census.build_default_connector_registry",
        Registry,
    )
    report = run_census_flight(
        search_terms=["ML Engineer", "Data Engineer"],
        location="Hannover",
        radius_km=50,
        page_size=5,
    )
    assert calls["count"] == 1
    assert "bundesagentur_fuer_arbeit" in report["flight"]["source_errors"]
    assert report["flight"]["writes"] == {
        "database": 0, "bronze": 0, "silver": 0,
        "product": 0, "candidate": 0, "connector": 0,
    }


def test_flight_feeds_connector_records_into_common_census(monkeypatch):
    class Registry:
        def role_for(self, source_name):
            from src.connectors.registry import SourceRole
            return SourceRole.SENSOR

        def create(self, source_name):
            connector = Mock()
            if source_name == "stepstone":
                connector.fetch_jobs.return_value = ([
                    RawJobRecord(
                        source_name="stepstone",
                        source_url="https://www.stepstone.de/job/42",
                        external_job_id="42",
                        raw_data={"result_card": {
                            "title": "Machine Learning Engineer",
                            "company_name": "Census GmbH",
                            "location": "Hannover",
                            "remote_hint_text": None,
                        }},
                    )
                ], "https://www.stepstone.de")
            else:
                connector.fetch_jobs.return_value = ([], "https://example.invalid")
            return connector

    monkeypatch.setattr(
        "scripts.run_job_first_employer_discovery_census.build_default_connector_registry",
        Registry,
    )
    report = run_census_flight(
        search_terms=["Machine Learning Engineer"],
        location="Hannover",
        radius_km=50,
        page_size=5,
    )
    assert report["qualifying_job_count"] == 1
    assert report["employers"][0]["company_name"] == "Census GmbH"
