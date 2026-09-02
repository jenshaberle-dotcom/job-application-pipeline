from scripts.run_demo_live_detail_tranche import qualify_record
from src.connectors.base import RawJobRecord


def _record(*, title: str, location: str, description: str, url: str) -> RawJobRecord:
    return RawJobRecord(
        source_name="personio:example",
        source_url=url,
        external_job_id="example-1",
        raw_data={
            "job": {
                "title": title,
                "company_name": "Example GmbH",
                "location": location,
                "description": description,
            }
        },
    )


def test_profile_remote_job_with_substantive_detail_is_demo_proven() -> None:
    row = qualify_record(
        _record(
            title="ML Engineer (m/f/d)",
            location="Remote Germany",
            description=(
                "Build and operate machine learning systems with Python, model serving, "
                "monitoring, data quality and production reliability. " * 3
            ),
            url="https://example.com/jobs/ml-engineer-1",
        )
    )

    assert row["detail_proven"] is True
    assert row["role_profile_match"] is True
    assert row["location_signal_match"] is True
    assert row["detail_chars"] >= 120


def test_title_only_listing_is_not_detail_proven() -> None:
    row = qualify_record(
        _record(
            title="Data Engineer (m/f/d)",
            location="Hannover",
            description="Short listing card",
            url="https://example.com/jobs/data-engineer-1",
        )
    )

    assert row["role_profile_match"] is True
    assert row["detail_proven"] is False


def test_non_job_root_url_is_not_detail_proven() -> None:
    row = qualify_record(
        _record(
            title="AI Reliability Engineer",
            location="Remote Germany",
            description="Reliability and observability for production AI systems. " * 5,
            url="https://example.com/",
        )
    )

    assert row["detail_proven"] is False
