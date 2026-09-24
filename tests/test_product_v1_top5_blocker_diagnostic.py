from scripts.run_product_v1_top5_blocker_diagnostic import build_report


def test_top5_blocker_report_keeps_diagnostic_read_only_and_exposes_component_truth() -> None:
    rows = [
        {
            "silver_job_id": 613,
            "company_name": "VALUNY GmbH",
            "title": "Machine Learning Engineer / Data Scientist (m/w/d)",
            "source_name": "personio:valuny",
            "overall_quality_score": 90,
            "affinity_authority_status": "authoritative",
            "lifecycle_status": "active_confirmed",
            "origin_validation_status": "validated",
            "product_readiness_status": "hard_filter_evidence_required",
            "hard_filter_status": "unknown",
            "capability_fit_status": "passed",
            "employment_status": "manual_review_required",
            "language_status": "passed",
            "weekly_hours_status": "manual_review_required",
            "seniority_status": "passed",
            "deterministic_hard_filter_status": "unknown",
            "operator_review_decision": None,
            "operator_review_valid": False,
            "hard_filter_reasons": ["employment evidence missing", "hours evidence missing"],
            "policy_version": "product-v1-2026-08-02",
        },
        {
            "silver_job_id": 999,
            "company_name": "Example",
            "title": "Blocked role",
            "source_name": "personio:example",
            "overall_quality_score": 95,
            "affinity_authority_status": "authoritative",
            "lifecycle_status": "active_confirmed",
            "origin_validation_status": "validated",
            "product_readiness_status": "blocked_hard_filter",
            "hard_filter_status": "failed",
            "capability_fit_status": "failed",
            "employment_status": "passed",
            "language_status": "passed",
            "weekly_hours_status": "failed",
            "seniority_status": "failed",
            "deterministic_hard_filter_status": "failed",
            "operator_review_decision": None,
            "operator_review_valid": False,
            "hard_filter_reasons": ["weekly hours conflict"],
            "policy_version": "product-v1-2026-08-02",
        },
    ]

    report = build_report(
        rows=rows,
        ranking_policy={
            "status": "approved",
            "policy_version": "product-v1-2026-09-16-affinity-v1",
            "minimum_quality_score": 70,
            "top_job_limit": 5,
            "comparable_score_delta": 3,
        },
        top_job_count=0,
        detail_limit=10,
    )

    assert report["summary"] == {
        "review_scope_job_count": 2,
        "current_active_count": 2,
        "rankable_count": 0,
        "top_job_count": 0,
        "hard_filter_evidence_required_count": 1,
        "assessment_required_count": 0,
        "blocked_hard_filter_count": 1,
        "affinity_authoritative_count": 2,
    }
    assert report["valuny"][0]["silver_job_id"] == 613
    assert report["valuny"][0]["unknown_components"] == [
        "employment",
        "weekly_hours",
    ]
    assert report["highest_affinity_hard_filter_blocked"][0]["silver_job_id"] == 613
    assert report["hard_filter_component_counts"]["weekly_hours"] == {
        "failed": 1,
        "manual_review_required": 1,
    }
    assert report["boundaries"]["database_writes"] is False
    assert report["boundaries"]["network_requests"] == 0
    assert report["boundaries"]["provider_requests"] == 0
    assert report["boundaries"]["hard_filter_reviews_written"] == 0
    assert report["boundaries"]["ranking_or_top5_writes"] == 0
    assert report["boundaries"]["application_or_submission_actions"] == 0
