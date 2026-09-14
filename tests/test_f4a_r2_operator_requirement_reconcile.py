from __future__ import annotations

from scripts.run_f4a_r2_current_requirement_origin_diagnostic import (
    _unavailable_origin_proposal,
)
from scripts.run_f4a_r2_requirement_reconcile import build_operator_requirement_lines
from src.search_intelligence.product_v1_contenders import classify_geography


def test_operator_requirement_lines_keep_job_truth_separate_from_profile_fit() -> None:
    verified, unknown = build_operator_requirement_lines(
        {
            "assessment": {
                "title_seniority": "senior",
                "references": [
                    {
                        "field": "required_languages",
                        "evidence": "Fluent German and English",
                    },
                    {
                        "field": "requirements_seniority",
                        "evidence": "senior-level role",
                    },
                ],
            },
            "resolved_assessment_patch": {
                "employment_type": "permanent",
                "required_languages": ["de", "en"],
                "weekly_hours_min": 35.0,
                "weekly_hours_max": 40.0,
                "work_model": "hybrid",
                "requirements_seniority": "senior",
            },
            "job_skills": ["Python", "SQL", "Terraform"],
            "semantic_references": [
                {
                    "field": "remote",
                    "evidence": "hybrid work model",
                }
            ],
            "conflicted_fields": [],
            "unresolved_fields": [],
        }
    )

    assert any(line.startswith("Employment type: permanent") for line in verified)
    assert any(line.startswith("Required languages: de, en") for line in verified)
    assert any(line.startswith("Weekly hours: 35-40 h/week") for line in verified)
    assert any(line.startswith("Work model: hybrid") for line in verified)
    assert any(line.startswith("Requirement seniority: senior") for line in verified)
    assert any("Job skills: Python, SQL, Terraform" in line for line in verified)
    assert any("title signal only" in line for line in verified)
    assert unknown == [
        "Candidate↔Job fit remains separate: job-side requirement evidence does not create capability-fit authority"
    ]


def test_operator_requirement_lines_render_conflicts_as_unknown() -> None:
    verified, unknown = build_operator_requirement_lines(
        {
            "assessment": {"title_seniority": "unknown", "references": []},
            "resolved_assessment_patch": {
                "employment_type": "unknown",
                "required_languages": [],
                "weekly_hours_min": None,
                "weekly_hours_max": None,
                "work_model": "unknown",
                "requirements_seniority": "unknown",
            },
            "job_skills": [],
            "semantic_references": [],
            "conflicted_fields": ["work_model"],
            "unresolved_fields": ["work_model", "required_languages"],
        }
    )

    assert verified == []
    assert any(line.startswith("Conflict: Work model") for line in unknown)
    assert any(line.startswith("Unknown: Required languages") for line in unknown)


def test_unavailable_origin_clears_stale_requirement_assertions() -> None:
    row = {
        "current_silver_job_id": 491,
        "silver_job_id": 491,
        "source_name": "retired_origin:example",
        "source_url": "https://jobs.example.test/old-detail",
        "title": "Senior Data Engineer",
        "assessment_updated_at": "2026-09-14T08:00:00+00:00",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "passed",
        "profile_direction_score": 4,
        "data_focus_score": 5,
        "reliability_focus_score": 4,
        "evidence_quality_score": 4,
        "overall_quality_score": 4.3,
        "work_model": "hybrid",
        "commute_minutes": None,
        "public_transport_quality": "unknown",
        "ranking_factors": {"requirement_evidence": {"stale": True}},
        "explanations": ["stale assertion"],
        "uncertainties": [],
        "policy_key": "default",
        "policy_version": "old-policy",
        "assessed_by": "old",
        "employment_type": "permanent",
        "employment_evidence_status": "explicit",
        "required_languages": ["de", "en"],
        "language_evidence_status": "explicit",
        "weekly_hours_min": 40.0,
        "weekly_hours_max": 40.0,
        "weekly_hours_evidence_status": "explicit",
        "salary_min_gross_eur": None,
        "salary_max_gross_eur": None,
        "salary_evidence_status": "unknown",
        "title_seniority": "senior",
        "requirements_seniority": "senior",
        "capability_fit_status": "passed",
        "seniority_evidence_status": "explicit",
    }

    proposal = _unavailable_origin_proposal(
        row,
        source_authority="operator_review_scope_current_origin",
        ranking_policy_version="ranking-v2",
        hard_filter_policy_version="job-evidence-v3",
        reason="preview detail returned HTTP 404",
    )

    next_payload = proposal["next_payload"]
    assert proposal["origin_detail_unavailable"] is True
    assert proposal["mode"] == "update"
    assert next_payload["employment_type"] == "unknown"
    assert next_payload["required_languages"] == []
    assert next_payload["weekly_hours_min"] is None
    assert next_payload["weekly_hours_max"] is None
    assert next_payload["work_model"] == "unknown"
    assert next_payload["requirements_seniority"] == "unknown"
    assert next_payload["capability_fit_status"] == "unknown"
    assert next_payload["hard_filter_status"] == "unknown"
    assert next_payload["overall_quality_score"] is None
    assert next_payload["explanations"] == []
    assert any("current Origin detail unavailable" in line for line in next_payload["uncertainties"])
    assert "requirement_evidence" not in next_payload["ranking_factors"]
    assert next_payload["ranking_factors"]["f4a_r2_requirement_evidence"]["status"] == "origin_detail_unavailable"


def test_composite_orlando_us_location_is_outside_germany() -> None:
    result = classify_geography(
        {
            "city": "Orlando | FL | 32801 | US",
            "country": None,
            "work_model": "unknown",
            "commute_minutes": None,
        }
    )

    assert result.bucket == "outside_germany"
    assert result.eligible_for_bounded_pool is False
    assert result.reason == "structured_country_outside_germany"


def test_city_state_pair_is_not_misread_as_country() -> None:
    result = classify_geography(
        {
            "city": "Orlando | FL",
            "country": None,
            "work_model": "unknown",
            "commute_minutes": None,
        }
    )

    assert result.bucket == "commute_or_geography_review_required"
    assert result.eligible_for_bounded_pool is True
