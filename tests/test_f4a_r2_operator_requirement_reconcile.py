from __future__ import annotations

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
