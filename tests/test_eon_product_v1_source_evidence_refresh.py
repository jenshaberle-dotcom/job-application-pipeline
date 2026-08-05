from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.search_intelligence.eon_product_v1_source_evidence import (
    ALLOWED_CHANGED_FIELDS,
    APPROVAL_TOKEN,
    DEFAULT_ASSESSED_BY,
    EXPECTED_REQUIRED_LANGUAGES,
    REFRESH_KEY,
    assessment_is_refreshed,
    build_eon_assessment_refresh,
    extract_eon_source_evidence,
    normalize_description,
)


MIGRATION = Path(
    "db/migrations/087_create_job_product_assessment_revisions.sql"
).read_text(encoding="utf-8")
RUNNER = Path("scripts/run_eon_product_v1_source_evidence_refresh.py").read_text(
    encoding="utf-8"
)


def source_description() -> str:
    return (
        "<p>Shape the energy transition as a Data Engineer.</p> "
        "<p>You bring several years of professional experience in designing "
        "and operating enterprise data platforms.</p> "
        "<p>You are fluent in English and German and communicate confidently "
        "with technical and business stakeholders.</p> "
        "<p>We support hybrid working and flexible collaboration across our "
        "E.ON locations.</p>"
    )


def raw_data() -> dict:
    return {
        "job": {
            "title": "(Senior) Data Engineer Data & AI (f/m/d)",
            "description": source_description(),
        }
    }


def existing_assessment() -> dict:
    return {
        "silver_job_id": 466,
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "unknown",
        "profile_direction_score": None,
        "data_focus_score": None,
        "reliability_focus_score": None,
        "evidence_quality_score": None,
        "overall_quality_score": None,
        "work_model": "unknown",
        "commute_minutes": None,
        "public_transport_quality": "unknown",
        "ranking_factors": {
            "schema_version": "eon_partial_product_v1_assessment.v1",
            "scores_intentionally_omitted": True,
        },
        "explanations": [
            {
                "factor": "origin_validation",
                "status": "validated",
                "evidence": "authorized exact E.ON SuccessFactors ATS pilot dataset",
            },
            {
                "factor": "activity",
                "status": "active",
                "evidence": "fresh exact-job SuccessFactors detail observation returned HTTP 200",
            },
            {
                "factor": "employment",
                "status": "permanent_full_time_option",
                "evidence": ["Permanent", "Part or Full time"],
            },
            {
                "factor": "title_seniority",
                "status": "senior",
                "evidence": "(Senior) Data Engineer Data & AI (f/m/d)",
            },
        ],
        "uncertainties": [
            {
                "factor": "required_languages",
                "status": "unknown",
                "action": "manual_review_required",
            },
            {
                "factor": "weekly_hours",
                "status": "unknown",
                "action": "manual_review_required",
            },
            {
                "factor": "salary",
                "status": "unknown",
                "action": "soft_signal_only",
            },
            {
                "factor": "work_model",
                "status": "unknown",
                "action": "review_required",
            },
            {
                "factor": "requirements_seniority",
                "status": "unknown",
                "action": "manual_review_required",
            },
            {
                "factor": "candidate_capability_fit",
                "status": "unknown",
                "action": "manual_review_required",
            },
            {
                "factor": "ranking_scores",
                "status": "not_assessed",
                "action": "separate_evidence_bound_slice",
            },
        ],
        "policy_key": "default",
        "policy_version": "product-v1-2026-08-02",
        "assessed_by": "deterministic_eon_partial_product_v1",
        "employment_type": "permanent",
        "employment_evidence_status": "observed",
        "required_languages": [],
        "language_evidence_status": "unknown",
        "weekly_hours_min": None,
        "weekly_hours_max": None,
        "weekly_hours_evidence_status": "unknown",
        "salary_min_gross_eur": None,
        "salary_max_gross_eur": None,
        "salary_evidence_status": "unknown",
        "title_seniority": "senior",
        "requirements_seniority": "unknown",
        "capability_fit_status": "unknown",
        "seniority_evidence_status": "unknown",
    }


def test_normalize_description_removes_markup_and_collapses_whitespace() -> None:
    assert normalize_description("<p>Hello&nbsp; world</p>\n<div>Again</div>") == (
        "Hello world Again"
    )


def test_extracts_exact_bounded_source_evidence() -> None:
    evidence = extract_eon_source_evidence(
        description=source_description(),
        title="(Senior) Data Engineer Data & AI (f/m/d)",
    )

    assert evidence.required_languages == EXPECTED_REQUIRED_LANGUAGES
    assert evidence.work_model == "hybrid"
    assert evidence.requirements_seniority == "senior"
    assert "fluent in English and German" in evidence.language_evidence_text
    assert "hybrid working" in evidence.work_model_evidence_text
    assert "several years of professional experience" in evidence.seniority_evidence_text
    assert len(evidence.description_sha256) == 64


def test_accepts_reversed_fluent_language_order() -> None:
    description = source_description().replace(
        "fluent in English and German",
        "business-fluent in German and English",
    )

    evidence = extract_eon_source_evidence(
        description=description,
        title="(Senior) Data Engineer Data & AI (f/m/d)",
    )

    assert evidence.required_languages == ("de", "en")


def test_rejects_languages_without_fluency_evidence() -> None:
    description = source_description().replace(
        "You are fluent in English and German",
        "The teams use English and German",
    )

    with pytest.raises(ValueError, match="fluent German and English"):
        extract_eon_source_evidence(
            description=description,
            title="(Senior) Data Engineer Data & AI (f/m/d)",
        )


def test_rejects_hybrid_cloud_as_work_model_evidence() -> None:
    description = source_description().replace(
        "We support hybrid working",
        "We operate a hybrid cloud platform",
    )

    with pytest.raises(ValueError, match="hybrid work"):
        extract_eon_source_evidence(
            description=description,
            title="(Senior) Data Engineer Data & AI (f/m/d)",
        )


def test_rejects_missing_multi_year_requirement() -> None:
    description = source_description().replace(
        "several years of professional experience",
        "initial professional experience",
    )

    with pytest.raises(ValueError, match="several years"):
        extract_eon_source_evidence(
            description=description,
            title="(Senior) Data Engineer Data & AI (f/m/d)",
        )


def test_rejects_missing_bounded_senior_title_marker() -> None:
    with pytest.raises(ValueError, match="senior title marker"):
        extract_eon_source_evidence(
            description=source_description(),
            title="Data Engineer Data & AI (f/m/d)",
        )


def test_builds_bounded_refresh_and_preserves_open_hard_filters() -> None:
    refresh = build_eon_assessment_refresh(
        existing_assessment=existing_assessment(),
        raw_data=raw_data(),
    )
    target = refresh.next_payload

    assert tuple(target["required_languages"]) == ("de", "en")
    assert target["language_evidence_status"] == "observed"
    assert target["work_model"] == "hybrid"
    assert target["requirements_seniority"] == "senior"
    assert target["seniority_evidence_status"] == "observed"
    assert target["weekly_hours_min"] is None
    assert target["weekly_hours_max"] is None
    assert target["weekly_hours_evidence_status"] == "unknown"
    assert target["capability_fit_status"] == "unknown"
    assert target["hard_filter_status"] == "unknown"
    assert target["assessed_by"] == DEFAULT_ASSESSED_BY

    for score in (
        "profile_direction_score",
        "data_focus_score",
        "reliability_focus_score",
        "evidence_quality_score",
        "overall_quality_score",
    ):
        assert target[score] is None

    remaining_uncertainties = {
        item["factor"] for item in target["uncertainties"]
    }
    assert "required_languages" not in remaining_uncertainties
    assert "work_model" not in remaining_uncertainties
    assert "requirements_seniority" not in remaining_uncertainties
    assert "weekly_hours" in remaining_uncertainties
    assert "candidate_capability_fit" in remaining_uncertainties
    assert "ranking_scores" in remaining_uncertainties

    assert set(refresh.changed_fields) <= ALLOWED_CHANGED_FIELDS
    assert assessment_is_refreshed(target) is True


def test_refresh_is_stable_for_idempotent_replay() -> None:
    first = build_eon_assessment_refresh(
        existing_assessment=existing_assessment(),
        raw_data=raw_data(),
    )
    second = build_eon_assessment_refresh(
        existing_assessment=deepcopy(first.next_payload),
        raw_data=deepcopy(raw_data()),
    )

    assert second.changed_fields == ()
    assert second.next_payload == first.next_payload
    assert (
        second.source_evidence.canonical_payload()
        == first.source_evidence.canonical_payload()
    )


def test_rejects_existing_capability_fit_decision() -> None:
    existing = existing_assessment()
    existing["capability_fit_status"] = "passed"

    with pytest.raises(ValueError, match="capability fit must remain unknown"):
        build_eon_assessment_refresh(
            existing_assessment=existing,
            raw_data=raw_data(),
        )


def test_rejects_numeric_weekly_hours_inference() -> None:
    existing = existing_assessment()
    existing["weekly_hours_min"] = 35
    existing["weekly_hours_max"] = 40
    existing["weekly_hours_evidence_status"] = "observed"

    with pytest.raises(ValueError, match="weekly hours minimum was inferred"):
        build_eon_assessment_refresh(
            existing_assessment=existing,
            raw_data=raw_data(),
        )


def test_rejects_existing_ranking_score() -> None:
    existing = existing_assessment()
    existing["profile_direction_score"] = 80

    with pytest.raises(ValueError, match="ranking score must remain absent"):
        build_eon_assessment_refresh(
            existing_assessment=existing,
            raw_data=raw_data(),
        )


def test_revision_migration_is_auditable_and_schema_only() -> None:
    assert "CREATE TABLE IF NOT EXISTS job_product_assessment_revisions" in MIGRATION
    assert "UNIQUE (silver_job_id, revision_key)" in MIGRATION
    assert "previous_payload JSONB NOT NULL" in MIGRATION
    assert "next_payload JSONB NOT NULL" in MIGRATION
    assert "source_evidence JSONB NOT NULL" in MIGRATION
    assert "jsonb_typeof(previous_payload) = 'object'" in MIGRATION
    assert "jsonb_typeof(next_payload) = 'object'" in MIGRATION
    assert "jsonb_typeof(source_evidence) = 'object'" in MIGRATION
    assert "UPDATE job_product_assessments" not in MIGRATION
    assert "INSERT INTO job_product_assessments" not in MIGRATION


def test_runner_is_exact_approval_gated_and_provider_free() -> None:
    assert APPROVAL_TOKEN == REFRESH_KEY
    assert "EXPECTED_RAW_JOB_ID = 26342" in RUNNER
    assert "EXPECTED_SILVER_JOB_ID = 466" in RUNNER
    assert "args.approval_token != APPROVAL_TOKEN" in RUNNER
    assert "pg_advisory_xact_lock" in RUNNER
    assert "INSERT INTO job_product_assessment_revisions" in RUNNER
    assert "UPDATE job_product_assessments" in RUNNER
    assert "weekly_hours_evidence_status: unknown" in RUNNER
    assert "capability_fit_status: unknown" in RUNNER
    assert '"network_requests": 0' in RUNNER
    assert '"provider_requests": 0' in RUNNER
    assert '"ranking_scores_created": False' in RUNNER
    assert '"hard_filter_pass_forced": False' in RUNNER
    assert '"application_action_performed": False' in RUNNER
    assert "requests.get" not in RUNNER
    assert "requests.post" not in RUNNER
