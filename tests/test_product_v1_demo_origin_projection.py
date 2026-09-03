from src.search_intelligence.product_v1_demo_origin_projection import (
    filter_demo_actionable_jobs,
    project_demo_origin_truth,
)


def job(**overrides):
    value = {
        "silver_job_id": 1,
        "source_url": "https://jobs.example.com/job/1",
        "canonical_source_type": "employer_origin_career_site",
        "lifecycle_status": "active_confirmed",
        "origin_validation_status": "validated",
        "product_readiness_status": "rankable",
    }
    value.update(overrides)
    return value


def test_projection_keeps_discovery_url_as_provenance_not_action_url() -> None:
    discovery = "https://www.arbeitsagentur.de/jobsuche/jobdetail/123"
    projected = project_demo_origin_truth([job(source_url=discovery)])[0]
    assert projected["discovery_source_url"] == discovery
    assert projected["source_url"] is None
    assert projected["employer_origin_url"] is None
    assert projected["demo_actionable"] is False


def test_actionable_projection_exposes_employer_origin_url() -> None:
    projected = project_demo_origin_truth([job()])[0]
    assert projected["demo_actionable"] is True
    assert projected["employer_origin_url"] == "https://jobs.example.com/job/1"
    assert projected["source_url"] == projected["employer_origin_url"]


def test_filter_returns_only_current_validated_origin_rows() -> None:
    rows = filter_demo_actionable_jobs(
        [
            job(silver_job_id=1),
            job(silver_job_id=2, lifecycle_status="stale_needs_refresh"),
            job(silver_job_id=3, canonical_source_type=None),
        ]
    )
    assert [row["silver_job_id"] for row in rows] == [1]
