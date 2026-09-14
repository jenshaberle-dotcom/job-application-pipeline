from __future__ import annotations

from pathlib import Path

from scripts.product_v1_job_presentation_runtime import (
    _latest_observation_query,
    enrich_product_payload_for_operator,
)
from scripts.product_v1_silver_requirement_projection import (
    project_silver_requirement_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "control-center" / "src"


def _silver_requirement_payload() -> dict[str, object]:
    return {
        "schema": "silver_job_requirement_evidence.v1",
        "parser_family": "schema_org_json_ld",
        "fields": {
            "employment_type": {
                "status": "source_absent_or_unresolved",
                "value": "unknown",
            },
            "required_languages": {
                "status": "observed_bounded_text",
                "values": ["de", "en"],
            },
            "weekly_hours": {
                "status": "observed_bounded_text",
                "minimum": 38.0,
                "maximum": 38.0,
            },
            "work_model": {
                "status": "observed_bounded_text",
                "value": "hybrid",
            },
            "requirements_seniority": {
                "status": "source_absent_or_unresolved",
                "value": "unknown",
            },
            "job_skills": {
                "status": "observed_structured",
                "values": ["Python", "Kubernetes"],
            },
        },
        "conflicted_fields": [],
        "unresolved_fields": ["employment_type", "requirements_seniority"],
        "raw_html_persisted": False,
        "authority": {
            "job_source_evidence_only": True,
            "candidate_fact_authority": False,
            "capability_fit_authority": False,
            "hard_filter_authority": False,
            "ranking_authority": False,
            "top5_authority": False,
            "application_authority": False,
        },
    }


def test_silver_requirement_sidecar_flattens_without_fit_authority() -> None:
    projected = project_silver_requirement_evidence(_silver_requirement_payload())

    assert projected is not None
    assert projected["requirement_evidence_source"] == "silver_job_requirement_evidence"
    assert projected["employment_type"] == "unknown"
    assert projected["required_languages"] == ["de", "en"]
    assert projected["weekly_hours_min"] == 38.0
    assert projected["weekly_hours_max"] == 38.0
    assert projected["work_model"] == "hybrid"
    assert projected["work_model_resolution"] == "observed_bounded_text"
    assert projected["requirements_seniority"] == "unknown"
    assert projected["job_skills"] == ["Python", "Kubernetes"]


def test_silver_requirement_sidecar_fails_closed_on_authority_drift() -> None:
    payload = _silver_requirement_payload()
    payload["authority"]["ranking_authority"] = True

    assert project_silver_requirement_evidence(payload) is None


def test_pre_migration_loader_does_not_resolve_optional_sidecar_relation() -> None:
    without_sidecar = _latest_observation_query(
        include_silver_requirement_sidecar=False
    )
    with_sidecar = _latest_observation_query(
        include_silver_requirement_sidecar=True
    )

    assert "NULL::jsonb AS silver_requirement_evidence" in without_sidecar
    assert "silver_job_requirement_evidence" not in without_sidecar
    assert "assessment.ranking_factors -> 'requirement_evidence'" in without_sidecar

    assert "LEFT JOIN silver_job_requirement_evidence" in with_sidecar
    assert (
        "silver_requirement.evidence_payload AS silver_requirement_evidence"
        in with_sidecar
    )
    assert "assessment.ranking_factors -> 'requirement_evidence'" in with_sidecar


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
                "requirement_evidence_source": "silver_job_requirement_evidence",
                "employment_type": "unknown",
                "employment_evidence_status": "source_absent_or_unresolved",
                "required_languages": ["de"],
                "language_evidence_status": "observed_bounded_text",
                "weekly_hours_min": 38.0,
                "weekly_hours_max": 38.0,
                "weekly_hours_evidence_status": "observed_bounded_text",
                "requirements_seniority": "unknown",
                "seniority_evidence_status": "source_absent_or_unresolved",
                "job_skills": ["Python", "Kubernetes"],
                "work_model": "hybrid",
                "work_model_resolution": "observed_bounded_text",
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
    assert projected["work_model_resolution"] == "observed_bounded_text"
    assert projected["requirements_seniority"] == "unknown"
    assert projected["requirement_evidence_source"] == "silver_job_requirement_evidence"
    assert result["boundaries"]["silver_requirement_sidecar_is_primary_job_source_evidence"] is True
    assert result["boundaries"]["silver_requirement_sidecar_is_not_candidate_fact_authority"] is True
    assert result["boundaries"]["silver_requirement_sidecar_is_not_capability_fit_authority"] is True


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
