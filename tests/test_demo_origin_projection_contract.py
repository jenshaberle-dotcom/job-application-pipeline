from src.search_intelligence.product_v1_demo_origin_projection import (
    project_demo_origin_truth,
)


def test_discovery_url_is_preserved_as_provenance_but_removed_from_action_slot() -> None:
    row = {
        "silver_job_id": 1,
        "source_url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/123",
        "canonical_source_type": None,
        "lifecycle_status": "active_confirmed",
        "origin_validation_status": None,
        "product_readiness_status": "assessment_required",
    }
    projected = project_demo_origin_truth([row])[0]
    assert projected["discovery_source_url"] == row["source_url"]
    assert projected["source_url"] is None
    assert projected["employer_origin_url"] is None
    assert projected["demo_actionable"] is False
