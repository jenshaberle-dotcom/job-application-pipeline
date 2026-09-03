from src.search_intelligence.product_v1_demo_origin_guard import (
    evaluate_demo_origin_guard,
)


def test_guard_accepts_current_validated_employer_origin_https() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://jobs.example.com/job/123",
        canonical_source_type="employer_origin_ats_backed_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="rankable",
    )
    assert result.eligible is True
    assert result.employer_origin_url == "https://jobs.example.com/job/123"


def test_guard_rejects_ba_even_if_other_flags_claim_ready() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://www.arbeitsagentur.de/jobsuche/jobdetail/123",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="rankable",
    )
    assert result.eligible is False
    assert result.reason == "aggregator_url_cannot_be_product_action_url"


def test_guard_rejects_discovery_source_type() -> None:
    result = evaluate_demo_origin_guard(
        source_url="https://gute-jobs.de/viewjob-x",
        canonical_source_type=None,
        lifecycle_status="active_confirmed",
        origin_validation_status="validated",
        product_readiness_status="assessment_required",
    )
    assert result.eligible is False
    assert result.employer_origin_url is None


def test_guard_rejects_stale_or_unvalidated_rows() -> None:
    stale = evaluate_demo_origin_guard(
        source_url="https://jobs.example.com/job/123",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="stale_needs_refresh",
        origin_validation_status="validated",
        product_readiness_status="assessment_required",
    )
    unvalidated = evaluate_demo_origin_guard(
        source_url="https://jobs.example.com/job/123",
        canonical_source_type="employer_origin_career_site",
        lifecycle_status="active_confirmed",
        origin_validation_status=None,
        product_readiness_status="assessment_required",
    )
    assert stale.eligible is False
    assert unvalidated.eligible is False
