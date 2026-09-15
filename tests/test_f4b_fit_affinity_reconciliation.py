from __future__ import annotations

import math

from scripts.run_f4b_fit_affinity_reconciliation import reconcile_payload


def _job(job_id: int, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "silver_job_id": job_id,
        "company_name": "Example GmbH",
        "title": "Machine Learning Engineer",
        "source_name": "example-origin",
        "source_url": f"https://example.test/jobs/{job_id}",
        "lifecycle_status": "active_confirmed",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "passed",
        "hard_filter_reasons": {
            "employment": "passed",
            "languages": "passed",
            "weekly_hours": "passed",
            "seniority_and_capability_fit": "passed",
        },
        "product_readiness_status": "rankable",
        "product_overall_quality_score": 80.0,
        "overall_quality_score": 80.0,
        "display_fit_score": 80.0,
        "display_fit_scope": "authoritative_product_score",
        "review_fit_score": 90.0,
        "profile_direction_score": 82.0,
        "reliability_focus_score": 78.0,
        "data_focus_score": 81.0,
        "evidence_quality_score": 79.0,
        "requirement_evidence_source": "silver_job_requirement_evidence",
        "employment_type": "permanent",
        "employment_evidence_status": "observed_structured",
        "required_languages": ["de", "en"],
        "language_evidence_status": "observed_contextual",
        "weekly_hours_min": 38,
        "weekly_hours_max": 38,
        "weekly_hours_evidence_status": "observed_contextual",
        "requirements_seniority": "mid",
        "seniority_evidence_status": "observed_contextual",
        "job_skills": ["Python", "SQL"],
        "work_model": "hybrid",
        "requirement_conflicted_fields": [],
        "requirement_unresolved_fields": [],
        "profile_fit_coverage_status": "profile_fit_complete",
        "profile_fit_decision": "passed",
        "profile_fit_factors": {
            "geography_work_model_commute": {
                "status": "passed",
                "reason": "approved_candidate_geography_policy_matches_job_evidence",
            },
            "skills_capabilities": {
                "status": "passed",
                "reason": "exact_current_candidate_fact_capability_review_passed",
            },
            "seniority": {
                "status": "passed",
                "reason": "seniority_requirements_and_capability_fit_passed",
            },
            "hard_requirements": {
                "status": "passed",
                "reason": "current_hard_filter_passed",
            },
        },
        "profile_fit_missing_factors": [],
        "profile_fit_failed_factors": [],
    }
    row.update(overrides)
    return row


def _payload(*jobs: dict[str, object], top_ids: tuple[int, ...] = ()) -> dict[str, object]:
    by_id = {int(job["silver_job_id"]): job for job in jobs}
    return {
        "job_readiness": list(jobs),
        "top_jobs": [by_id[job_id] for job_id in top_ids],
    }


def test_read_only_combined_candidates_use_only_pd052_and_complete_fit() -> None:
    report = reconcile_payload(_payload(_job(1), top_ids=(1,)))
    row = report["rows"][0]

    assert row["fit"]["coverage_pct"] == 100.0
    assert row["fit"]["diagnostic_equal_factor_score"] == 100.0
    assert row["affinity"]["pd052_product_score"] == 80.0
    assert row["combined_calibration"]["eligible"] is True
    assert row["combined_calibration"]["arithmetic_60_fit_40_affinity"] == 92.0
    assert math.isclose(
        row["combined_calibration"]["geometric_60_fit_40_affinity"],
        91.46,
        abs_tol=0.01,
    )
    assert row["current_top5_member"] is True
    assert row["first_exclusion_reason"] is None
    assert report["boundaries"]["ranking_authority_created"] is False
    assert report["boundaries"]["pd052_production_authority_unchanged"] is True


def test_sidecar_diagnostic_reports_source_evidence_without_creating_authority() -> None:
    report = reconcile_payload(_payload(_job(1)))
    row = report["rows"][0]
    sidecar = row["sidecar_requirement_evidence"]
    summary = report["summary"]

    assert sidecar["is_primary_silver_sidecar"] is True
    assert sidecar["employment_value_present"] is True
    assert sidecar["language_values_present"] is True
    assert sidecar["weekly_hours_numeric_present"] is True
    assert sidecar["seniority_value_present"] is True
    assert sidecar["job_skills_present"] is True
    assert sidecar["work_model_present"] is True
    assert sidecar["hard_filter_authority"] is False
    assert summary["silver_sidecar_primary_count"] == 1
    assert summary["silver_sidecar_employment_value_count"] == 1
    assert summary["silver_sidecar_language_values_count"] == 1
    assert summary["silver_sidecar_weekly_hours_numeric_count"] == 1
    assert summary["silver_sidecar_seniority_value_count"] == 1
    assert summary["silver_sidecar_job_skills_count"] == 1
    assert summary["silver_sidecar_work_model_count"] == 1
    assert report["boundaries"]["sidecar_diagnostic_creates_no_hard_filter_authority"] is True


def test_unknown_fit_factor_never_receives_midpoint_or_combined_score() -> None:
    factors = dict(_job(1)["profile_fit_factors"])
    factors["skills_capabilities"] = {
        "status": "unknown",
        "reason": "exact_current_candidate_fact_capability_review_missing",
    }
    report = reconcile_payload(
        _payload(
            _job(
                1,
                profile_fit_coverage_status="insufficient_evidence",
                profile_fit_decision="unknown",
                profile_fit_factors=factors,
                profile_fit_missing_factors=["skills_capabilities"],
            )
        )
    )
    row = report["rows"][0]

    assert row["fit"]["coverage_pct"] == 75.0
    assert row["fit"]["diagnostic_equal_factor_score"] is None
    assert row["combined_calibration"]["eligible"] is False
    assert row["combined_calibration"]["arithmetic_60_fit_40_affinity"] is None
    assert row["first_exclusion_reason"] == "fit_evidence_required:skills_capabilities"
    assert row["exclusion_kind"] == "evidence_gap"
    assert report["summary"]["population_blocker"].startswith(
        "evidence_gap:fit_evidence_required:skills_capabilities:1"
    )


def test_hard_filter_failure_is_valid_exclusion_not_evidence_gap() -> None:
    factors = dict(_job(1)["profile_fit_factors"])
    factors["hard_requirements"] = {
        "status": "failed",
        "reason": "deterministic_hard_requirement_failed",
    }
    report = reconcile_payload(
        _payload(
            _job(
                1,
                hard_filter_status="failed",
                hard_filter_reasons={
                    "employment": "failed",
                    "languages": "passed",
                    "weekly_hours": "failed",
                    "seniority_and_capability_fit": "passed",
                },
                product_readiness_status="blocked_hard_filter",
                profile_fit_decision="failed",
                profile_fit_factors=factors,
                profile_fit_failed_factors=["hard_requirements"],
            )
        )
    )
    row = report["rows"][0]

    assert row["first_exclusion_reason"] == "hard_filter_failed"
    assert row["exclusion_kind"] == "valid_exclusion"
    assert report["summary"]["evidence_gap_counts"] == {}
    assert report["summary"]["valid_exclusion_counts"] == {"hard_filter_failed": 1}


def test_missing_pd052_authority_does_not_promote_review_preview() -> None:
    report = reconcile_payload(
        _payload(
            _job(
                1,
                product_overall_quality_score=None,
                overall_quality_score=94.0,
                display_fit_score=94.0,
                display_fit_scope="review_preview",
                review_fit_score=94.0,
            )
        )
    )
    row = report["rows"][0]

    assert row["affinity"]["pd052_product_score"] is None
    assert row["affinity"]["review_preview_score"] == 94.0
    assert row["combined_calibration"]["eligible"] is False
    assert row["first_exclusion_reason"] == "affinity_pd052_score_required"
    assert row["exclusion_kind"] == "evidence_gap"


def test_multiple_positive_rows_expose_binary_fit_granularity_blocker() -> None:
    report = reconcile_payload(_payload(_job(1), _job(2, product_overall_quality_score=90.0)))

    assert report["summary"]["combined_calibration_eligible_count"] == 2
    assert report["summary"]["combined_fit_score_distinct_values"] == [100.0]
    assert (
        report["summary"]["population_blocker"]
        == "fit_signal_not_granular_enough_for_combined_ranking"
    )


def test_issue_884_highlight_is_diagnostic_only_and_normalizes_company_spacing() -> None:
    factors = dict(_job(599)["profile_fit_factors"])
    factors["hard_requirements"] = {
        "status": "failed",
        "reason": "deterministic_hard_requirement_failed",
    }
    report = reconcile_payload(
        _payload(
            _job(
                599,
                company_name="hannoverre",
                title="Working Student Taxation and Tax Reporting Economics",
                hard_filter_status="failed",
                profile_fit_decision="failed",
                profile_fit_factors=factors,
                profile_fit_failed_factors=["hard_requirements"],
            )
        )
    )

    highlighted = report["issue_884_highlight"]["rows"]
    assert len(highlighted) == 1
    assert highlighted[0]["diagnostic_classification"] == "truthful_conclusive_negative_candidate"
    assert report["issue_884_highlight"]["production_exception_created"] is False
    assert report["boundaries"]["employer_specific_production_exception_created"] is False
