from scripts.run_f4b_cohort_reconciliation import ReconciliationStop, reconcile


def _row() -> dict[str, object]:
    return {
        "silver_job_id": 9,
        "title": "Example",
        "company_name": "Example Co",
        "source_name": "generic_origin:example",
        "lifecycle_status": "active_confirmed",
        "origin_validation_status": "validated",
        "hard_filter_status": "manual_review_required",
        "hard_filter_reasons": {"weekly_hours": "manual_review_required"},
        "product_readiness_status": "hard_filter_evidence_required",
        "profile_fit_decision": "unknown",
        "profile_fit_coverage_status": "insufficient_evidence",
        "profile_fit_factors": {name: {"status": "unknown", "reason": "missing"} for name in (
            "geography_work_model_commute", "skills_capabilities", "seniority", "hard_requirements"
        )},
        "profile_fit_missing_factors": ["skills_capabilities"],
        "profile_fit_failed_factors": [],
        "profile_direction_score": 90,
        "data_focus_score": 80,
        "reliability_focus_score": 70,
        "evidence_quality_score": 60,
        "statement": "PRIVATE",
    }


def _payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "job_readiness": [row],
        "top_jobs": [],
        "ranking_policy": {
            "status": "approved", "minimum_quality_score": 70,
            "ranking_weights": {
                "profile_direction": 0.4, "data_focus": 0.2,
                "reliability_focus": 0.25, "evidence_quality": 0.15,
            },
        },
    }


def test_unknown_fit_keeps_both_combined_candidates_unscored_and_private_fields_out() -> None:
    report = reconcile(_payload(_row()), source_sha="abc")
    item = report["rows"][0]
    assert item["affinity_proxy_score"] == 78.5
    assert item["candidate_numeric_fit_score"] is None
    assert item["candidate_combined_arithmetic_60_40"] is None
    assert item["candidate_combined_geometric_60_40"] is None
    assert item["first_blocker"] == "hard_filter_evidence_required"
    assert "PRIVATE" not in str(report)


def test_failed_hard_requirement_precedes_affinity_and_fit() -> None:
    row = _row()
    row["hard_filter_status"] = "failed"
    row["hard_filter_reasons"] = {"weekly_hours": "failed"}
    row["profile_fit_decision"] = "failed"
    row["profile_fit_failed_factors"] = ["hard_requirements"]
    row["profile_fit_factors"]["hard_requirements"] = {"status": "failed", "reason": "hard_requirement_failed"}
    report = reconcile(_payload(row), source_sha="abc")
    assert report["rows"][0]["first_blocker"] == "hard_filter_failed:weekly_hours"
    assert report["rows"][0]["candidate_numeric_fit_score"] is None


def test_duplicate_current_identity_stops() -> None:
    payload = _payload(_row())
    payload["job_readiness"].append(dict(_row()))
    try:
        reconcile(payload, source_sha="abc")
    except ReconciliationStop as exc:
        assert "DUPLICATE" in str(exc)
    else:
        raise AssertionError("duplicate current identity was admitted")
