from __future__ import annotations

from pathlib import Path

from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "control-center" / "src"


def test_persisted_requirement_evidence_is_projected_without_fit_authority() -> None:
    job = {
        "silver_job_id": 579,
        "source_name": "finanz_informatik:career",
        "canonical_source_type": "employer_origin_career_site",
        "company_name": "Finanz Informatik GmbH & Co. KG",
        "title": "Data Platform Engineer (m/w/d)",
        "city": "Münster",
        "work_model": "hybrid",
        "lifecycle_status": "active_confirmed",
        "product_readiness_status": "hard_filter_evidence_required",
    }
    evidence = {
        579: {
            "normalized_evidence": {},
            "first_jap_observed_at": "2026-09-10T08:15:00+00:00",
            "job_requirement_evidence": {
                "requirement_evidence_status": "assessed",
                "employment_type": "unknown",
                "employment_evidence_status": "unknown",
                "required_languages": ["de"],
                "language_evidence_status": "observed",
                "weekly_hours_min": 38.0,
                "weekly_hours_max": 38.0,
                "weekly_hours_evidence_status": "observed",
                "requirements_seniority": "unknown",
                "seniority_evidence_status": "unknown",
                "job_skills": ["Python", "Kubernetes"],
                "work_model_resolution": "contextual_fill",
                "requirement_conflicted_fields": [],
                "requirement_unresolved_fields": ["employment_type", "requirements_seniority"],
            },
        }
    }

    result = enrich_product_payload_for_operator(
        {"job_readiness": [job], "top_jobs": [], "summary": {}, "boundaries": {}},
        observation_evidence=evidence,
    )

    projected = result["job_readiness"][0]
    assert projected["employment_type"] == "unknown"
    assert projected["required_languages"] == ["de"]
    assert projected["weekly_hours_min"] == 38.0
    assert projected["weekly_hours_max"] == 38.0
    assert projected["job_skills"] == ["Python", "Kubernetes"]
    assert projected["work_model"] == "hybrid"
    assert projected["work_model_resolution"] == "contextual_fill"
    assert projected["requirements_seniority"] == "unknown"
    assert result["boundaries"]["persisted_requirement_presentation_is_job_source_evidence_only"] is True
    assert result["boundaries"]["persisted_requirement_presentation_is_not_capability_fit_authority"] is True


def test_normal_review_surface_renders_dedicated_requirement_metadata() -> None:
    source = (FRONTEND / "JobReviewLabelControls.tsx").read_text(encoding="utf-8")

    for label in (
        "Job requirements · Origin truth",
        "Employment type",
        "Required languages",
        "Weekly hours",
        "Work model",
        "Requirement seniority",
        "Job skills",
    ):
        assert label in source
    assert "Candidate capability fit and Profile Fit remain separate authorities" in source
    assert "requirement_conflicted_fields" in source
    assert "readProductTruth<ProductRequirementPayload>()" in source
