from src.search_intelligence.product_v1_demo_origin_guard import evaluate_demo_origin_guard


def test_ats_backed_origin_is_actionable_when_current_and_validated() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://example.jobs.personio.de/job/123",
        canonical_source_type="employer_origin_ats_backed_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="hard_filter_evidence_required",
    )
    assert result.eligible is True
