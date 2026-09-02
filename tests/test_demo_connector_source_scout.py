from __future__ import annotations

from src.connectors.base import JobSourceConnector, RawJobRecord
from scripts.run_demo_connector_source_scout import (
    ConnectorSpec,
    build_report,
    record_to_observation,
)


class FakeConnector(JobSourceConnector):
    source_name = "fake:demo"

    def __init__(self, records: list[RawJobRecord] | None = None, error: Exception | None = None):
        self.records = records or []
        self.error = error

    def fetch_jobs(self, profile, search_term):
        if self.error is not None:
            raise self.error
        return self.records, "https://jobs.example.test/search"


def _record(
    *,
    title: str,
    location: str,
    source_url: str = "https://jobs.example.test/job/1",
) -> RawJobRecord:
    return RawJobRecord(
        source_name="fake:demo",
        source_url=source_url,
        external_job_id="1",
        raw_data={
            "source_type": "employer_origin_career_site",
            "job": {
                "title": title,
                "company_name": "Example GmbH",
                "location": location,
                "source_url": source_url,
            },
        },
    )


def test_record_observation_reuses_product_role_classifier() -> None:
    row = record_to_observation(
        _record(
            title="Machine Learning Platform Engineer",
            location="Hannover · Hybrid",
        )
    )

    assert row["role_profile_match"] is True
    assert row["role_tier"] == "primary"
    assert row["role_family"] in {"machine_learning_engineer", "ml_platform"}
    assert row["location_signal_match"] is True
    assert "hannover" in row["location_signals"]
    assert "hybrid" in row["location_signals"]


def test_non_profile_job_is_observed_without_becoming_demo_candidate() -> None:
    row = record_to_observation(
        _record(
            title="Accountant",
            location="Hannover",
        )
    )

    assert row["role_profile_match"] is False
    assert row["location_signal_match"] is True


def test_build_report_keeps_connector_failures_as_health_evidence() -> None:
    good = ConnectorSpec(
        "fake:good",
        lambda: FakeConnector(
            records=[
                _record(
                    title="Senior Data Engineer",
                    location="Remote Germany",
                )
            ]
        ),
    )
    bad = ConnectorSpec(
        "fake:bad",
        lambda: FakeConnector(error=RuntimeError("HTTP 503")),
    )

    report = build_report((good, bad))

    assert report["summary"] == {
        "connector_count": 2,
        "healthy_connector_count": 1,
        "observed_job_count": 1,
        "profile_match_count": 1,
        "profile_and_location_signal_count": 1,
        "sources_with_profile_matches": 1,
    }
    assert report["sources"][1]["status"] == "error"
    assert "HTTP 503" in report["sources"][1]["error"]
    assert report["boundaries"]["database_writes"] is False
    assert report["boundaries"]["demo_ranking_created"] is False


def test_profile_match_without_location_signal_is_not_strong_demo_candidate() -> None:
    spec = ConnectorSpec(
        "fake:demo",
        lambda: FakeConnector(
            records=[
                _record(
                    title="Data Engineer",
                    location="München",
                )
            ]
        ),
    )

    report = build_report((spec,))

    assert report["summary"]["profile_match_count"] == 1
    assert report["summary"]["profile_and_location_signal_count"] == 0
    assert report["profile_and_location_signal_matches"] == []
