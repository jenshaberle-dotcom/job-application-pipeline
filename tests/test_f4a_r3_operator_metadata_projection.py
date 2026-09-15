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
                "status": "source_absent",
                "value": "unknown",
                "source_employment_types": ["FULL_TIME"],
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
                "status": "source_absent",
                "value": "unknown",
            },
            "job_skills": {
                "status": "observed_structured",
                "values": ["Python", "Kubernetes"],
            },
        },
        "display_context": {
            "employment_scope": "full_time",
            "employment_scope_status": "observed_structured",
            "posting_language": "de",
            "posting_language_basis": "bounded_vacancy_text",
            "title_seniority_signal": "senior",
            "title_seniority_basis": "job_title",
            "hard_filter_authority": False,
            "capability_fit_authority": False,
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
    assert projected["source_employment_types"] == ["FULL_TIME"]
    assert projected["employment_scope"] == "full_time"
    assert projected["employment_scope_status"] == "observed_structured"
    assert projected["required_languages"] == ["de", "en"]
    assert projected["posting_language"] == "de"
    assert projected["weekly_hours_min"] == 38.0
    assert projected["weekly_hours_max"] == 38.0
    assert projected["work_model"] == "hybrid"
    assert projected["work_model_resolution"] == "observed_bounded_text"
    assert projected["requirements_seniority"] == "unknown"
    assert projected["title_seniority_signal"] == "senior"
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
                "employment_evidence_status": "source_absent",
                "source_employment_types": ["FULL_TIME"],
                "employment_scope": "full_time",
                "employment_scope_status": "observed_structured",
                "required_languages": ["de"],
                "language_evidence_status": "observed_bounded_text",
                "posting_language": "de",
                "posting_language_basis": "bounded_vacancy_text",
                "weekly_hours_min": 38.0,
                "weekly_hours_max": 38.0,
                "weekly_hours_evidence_status": "observed_bounded_text",
                "requirements_seniority": "unknown",
                "seniority_evidence_status": "source_absent",
                "title_seniority_signal": "unknown",
                "title_seniority_basis": "unknown",
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
    assert projected["employment_scope"] == "full_time"
    assert projected["required_languages"] == ["de"]
    assert projected["posting_language"] == "de"
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


def test_normal_review_surface_consolidates_origin_truth_and_profile_fit() -> None:
    source = (FRONTEND / "JobReviewLabelControls.tsx").read_text(encoding="utf-8")
    css = (FRONTEND / "review-labels.css").read_text(encoding="utf-8")

    assert "Job requirements & fit" in source
    for label in (
        "Location & work model",
        "Skills & capabilities",
        "Level & experience",
        "Employment & language",
    ):
        assert label in source

    assert "Vacancy metadata" not in source
    assert "Requirement seniority" not in source
    assert "Job skills" not in source
    assert "posting language" in source.lower()
    assert "employment_scope" in source
    assert "title_seniority_signal" in source
    assert "r4-score-card" in source
    assert "width: `${bounded}%`" in source
    assert ".r4-review-stack + .ow-facts" in css


def test_pending_fit_is_not_rendered_as_repeated_origin_warning() -> None:
    css = (FRONTEND / "review-labels.css").read_text(encoding="utf-8")

    assert "Missing Candidate-Fit evidence is a pending evaluation state" in css
    assert ".r4-fit-state.warn" in css
    assert "color: var(--muted);" in css
    assert ".r4-review-stack ~ .ow-evidence" in css
    assert ".ow-job-list > button > span:last-child .ow-status:first-child" in css
    assert ".ow-job-list > button > span:last-child .ow-status.warn" in css
