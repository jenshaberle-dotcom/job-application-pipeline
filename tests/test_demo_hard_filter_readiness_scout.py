from __future__ import annotations

from src.connectors.base import JobSourceConnector, RawJobRecord
from scripts.run_demo_connector_source_scout import ConnectorSpec
from scripts.run_demo_hard_filter_readiness_scout import (
    assessment_readiness,
    build_report,
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


def _record(*, description: str, title: str = "Data Engineer") -> RawJobRecord:
    url = "https://jobs.example.test/job/1"
    return RawJobRecord(
        source_name="fake:demo",
        source_url=url,
        external_job_id="1",
        raw_data={
            "source_type": "employer_origin_career_site",
            "job": {
                "title": title,
                "company_name": "Example GmbH",
                "location": "Remote Germany",
                "description": description,
                "employment_type": "Permanent",
                "schedule": "Full-time",
                "source_url": url,
            },
        },
    )


def test_complete_source_evidence_is_reported_without_granting_authority() -> None:
    row = assessment_readiness(
        _record(
            description=(
                "Permanent employment. Fluent German and English are required. "
                "The role is 35-40 hours per week and offers hybrid work."
            )
        )
    )

    assert row["role_profile_match"] is True
    assert row["location_signal_match"] is True
    assert row["employment_type"] == "permanent"
    assert row["required_languages"] == ["de", "en"]
    assert row["weekly_hours_min"] == 35.0
    assert row["weekly_hours_max"] == 40.0
    assert row["hard_filter_source_evidence_complete"] is True
    assert row["structured_employment_type"] == "Permanent"
    assert row["structured_schedule"] == "Full-time"


def test_sparse_description_stays_incomplete_even_with_structured_schedule() -> None:
    row = assessment_readiness(
        _record(description="Build reliable data platforms with Python and SQL.")
    )

    assert row["hard_filter_source_evidence_complete"] is False
    assert "employment_type" in row["assessment_unresolved_fields"]
    assert "required_languages" in row["assessment_unresolved_fields"]
    assert "weekly_hours" in row["assessment_unresolved_fields"]
    assert row["structured_employment_type"] == "Permanent"
    assert row["structured_schedule"] == "Full-time"


def test_build_report_preserves_source_failure_and_zero_authority() -> None:
    good = ConnectorSpec(
        "fake:good",
        lambda: FakeConnector(
            records=[
                _record(
                    description=(
                        "Permanent employment. Fluent German and English. "
                        "35-40 hours per week."
                    )
                )
            ]
        ),
    )
    bad = ConnectorSpec("fake:bad", lambda: FakeConnector(error=RuntimeError("HTTP 503")))

    report = build_report((good, bad))

    assert report["summary"]["connector_count"] == 2
    assert report["summary"]["healthy_connector_count"] == 1
    assert report["summary"]["hard_filter_source_ready_count"] == 1
    assert report["sources"][1]["status"] == "error"
    assert "HTTP 503" in report["sources"][1]["error"]
    assert report["boundaries"]["database_writes"] is False
    assert report["boundaries"]["hard_filter_authority"] is False
    assert report["boundaries"]["capability_fit_authority"] is False
