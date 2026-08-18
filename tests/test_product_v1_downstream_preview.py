from __future__ import annotations

import socket

import pytest

from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    build_product_v1_downstream_preview,
    validate_public_https_url,
)


DETAIL = (
    "Senior Data Engineer. Permanent employment. Hybrid work model. "
    "Fluent German and English. 35-40 hours per week. "
    "We require a senior-level professional. Build data pipelines with SQL and "
    "reliability, test automation and observability."
)


def _resolver(address: str):
    def resolve(_host: str, port: int, *, type: int):
        assert type == socket.SOCK_STREAM
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    return resolve


def _row(**overrides):
    values = {
        "silver_job_id": 42,
        "title": "Senior Data Engineer",
        "company_name": "Example GmbH",
        "source_url": "https://jobs.example.com/42",
        "canonical_source_type": "employer_origin",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "product_readiness_status": "hard_filter_decision_required",
        "employment_type": "unknown",
        "employment_evidence_status": "unknown",
        "required_languages": [],
        "language_evidence_status": "unknown",
        "weekly_hours_min": None,
        "weekly_hours_max": None,
        "weekly_hours_evidence_status": "unknown",
        "work_model": "unknown",
        "title_seniority": "unknown",
        "requirements_seniority": "unknown",
        "seniority_evidence_status": "unknown",
        "capability_fit_status": "unknown",
        "capability_fit_evidence_status": "unknown",
        "profile_direction_score": None,
        "data_focus_score": None,
        "reliability_focus_score": None,
        "evidence_quality_score": None,
    }
    values.update(overrides)
    return values


def test_public_https_validation_rejects_private_loopback_and_credentials() -> None:
    with pytest.raises(DownstreamPreviewStop, match="HTTPS"):
        validate_public_https_url(
            "http://jobs.example.com/42",
            resolver=_resolver("93.184.216.34"),
        )
    with pytest.raises(DownstreamPreviewStop, match="credentials"):
        validate_public_https_url(
            "https://user:secret@jobs.example.com/42",
            resolver=_resolver("93.184.216.34"),
        )
    with pytest.raises(DownstreamPreviewStop, match="non-public"):
        validate_public_https_url(
            "https://jobs.example.com/42",
            resolver=_resolver("127.0.0.1"),
        )
    with pytest.raises(DownstreamPreviewStop, match="non-public"):
        validate_public_https_url(
            "https://jobs.example.com/42",
            resolver=_resolver("10.0.0.5"),
        )

    assert (
        validate_public_https_url(
            "https://jobs.example.com/42",
            resolver=_resolver("93.184.216.34"),
        )
        == "https://jobs.example.com/42"
    )


def test_preview_materializes_generic_assessment_and_ranking_without_authority() -> None:
    preview = build_product_v1_downstream_preview(
        row=_row(),
        final_url="https://jobs.example.com/42",
        fetched_title="Senior Data Engineer | Example",
        detail_text=DETAIL,
    )

    assert preview["status"] == "preview_ready"
    assert preview["assessment"]["employment_type"] == "permanent"
    assert preview["assessment"]["required_languages"] == ["de", "en"]
    assert preview["assessment"]["weekly_hours_min"] == 35
    assert preview["assessment"]["weekly_hours_max"] == 40
    assert preview["assessment"]["work_model"] == "hybrid"
    assert preview["assessment"]["requirements_seniority"] == "senior"
    assert preview["ranking"]["profile_direction_score"] == 85
    assert preview["ranking"]["data_focus_score"] == 50
    assert preview["ranking"]["reliability_focus_score"] == 60
    assert preview["ranking"]["evidence_quality_score"] == 100

    capability = preview["capability_fit_review"]
    assert capability == {
        "status": "unknown",
        "evidence_status": "unknown",
        "review_required": True,
        "reason": "candidate_fact_or_operator_evidence_required",
        "auto_pass_from_tag_overlap": False,
    }
    assert preview["boundaries"] == {
        "provider_requests": 0,
        "llm_requests": 0,
        "tavily_requests": 0,
        "database_writes": 0,
        "hard_filter_writes": 0,
        "ranking_writes": 0,
        "application_writes": 0,
        "hard_filter_authority": False,
        "ranking_authority": False,
        "top5_authority": False,
        "application_authority": False,
        "product_authority": False,
    }
    assert preview["target"]["raw_html_persisted"] is False
    assert preview["delta"]["employment_type"] == {
        "stored": "unknown",
        "preview": "permanent",
    }


def test_preview_requires_validated_active_employer_origin_authority() -> None:
    for overrides, message in (
        ({"canonical_source_type": "stepstone"}, "employer-origin"),
        ({"origin_validation_status": "pending"}, "validated origin"),
        ({"activity_status": "unknown"}, "current active"),
    ):
        with pytest.raises(DownstreamPreviewStop, match=message):
            build_product_v1_downstream_preview(
                row=_row(**overrides),
                final_url="https://jobs.example.com/42",
                fetched_title="",
                detail_text=DETAIL,
            )


def test_existing_capability_fit_is_reported_but_preview_never_decides_it() -> None:
    preview = build_product_v1_downstream_preview(
        row=_row(
            capability_fit_status="passed",
            capability_fit_evidence_status="observed",
        ),
        final_url="https://jobs.example.com/42",
        fetched_title="",
        detail_text=DETAIL,
    )

    capability = preview["capability_fit_review"]
    assert capability["status"] == "passed"
    assert capability["review_required"] is False
    assert capability["auto_pass_from_tag_overlap"] is False
    assert preview["boundaries"]["hard_filter_authority"] is False
