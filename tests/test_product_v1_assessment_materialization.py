from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_product_v1_assessment_materialization import (
    APPROVAL_TOKEN,
    ASSESSED_BY,
    MATERIALIZER_CONTRACT,
    MaterializationStop,
    build_assessment_payload,
    select_rows,
    validate_materialization_authority,
)


SOURCE = "personio:example"
DETAIL_URL = "https://example.jobs.personio.de/job/123?language=de"


def _row(**overrides: object) -> dict[str, object]:
    normalized_evidence = {
        "source_url": DETAIL_URL,
        "raw_evidence": {
            "source_type": "employer_origin_ats_backed_career_site",
            "job": {
                "source_url": DETAIL_URL,
                "title": "Senior Data Engineer",
            },
            "ats_feed_authority": {
                "product_authority": False,
            },
        },
    }
    row: dict[str, object] = {
        "silver_job_id": 123,
        "raw_job_id": 321,
        "source_name": SOURCE,
        "source_url": DETAIL_URL,
        "title": "Senior Data Engineer",
        "origin_validation_status": None,
        "product_readiness_status": "assessment_required",
        "lifecycle_status": "active_confirmed",
        "lifecycle_evidence_reason": "authoritative_verified_ats_feed_observation",
        "latest_health_coverage": "complete_inventory",
        "latest_observation_observed_at": "2026-09-02T12:00:00+00:00",
        "latest_observation_source_url": DETAIL_URL,
        "latest_observation_evidence": normalized_evidence,
    }
    row.update(overrides)
    return row


DETAIL = """
Permanent employment. Fluent German and English are required.
This is a hybrid work model with 35-40 hours per week.
We are looking for a Senior Engineer for a senior-level role.
"""


def test_generic_materialization_uses_source_evidence_without_scores_or_fit() -> None:
    payload = build_assessment_payload(
        row=_row(),
        authorized_sources={SOURCE},
        policy_version="product-v1-2026-08-02",
        final_url=DETAIL_URL,
        detail_text=DETAIL,
    )

    assert payload["origin_validation_status"] == "validated"
    assert payload["activity_status"] == "active"
    assert payload["hard_filter_status"] == "unknown"
    assert payload["employment_type"] == "permanent"
    assert payload["required_languages"] == ["de", "en"]
    assert payload["weekly_hours_min"] == 35.0
    assert payload["weekly_hours_max"] == 40.0
    assert payload["work_model"] == "hybrid"
    assert payload["title_seniority"] == "senior"
    assert payload["requirements_seniority"] == "senior"
    assert payload["capability_fit_status"] == "unknown"
    assert payload["profile_direction_score"] is None
    assert payload["data_focus_score"] is None
    assert payload["reliability_focus_score"] is None
    assert payload["evidence_quality_score"] is None
    assert payload["overall_quality_score"] is None
    assert payload["ranking_factors"]["schema"] == MATERIALIZER_CONTRACT
    assert payload["ranking_factors"]["source_evidence_only"] is True
    assert payload["ranking_factors"]["authority"]["profile_source_role"] == "employer_origin"
    assert len(str(payload["materialization_fingerprint"])) == 64
    assert ASSESSED_BY == "deterministic_assessment_materialization_v1"


def test_source_role_authority_is_required_separately_from_feed_evidence() -> None:
    with pytest.raises(
        MaterializationStop,
        match="active recurring employer-origin profile authority",
    ):
        validate_materialization_authority(_row(), authorized_sources=set())


def test_non_authoritative_lifecycle_reason_is_rejected() -> None:
    with pytest.raises(MaterializationStop, match="lifecycle evidence"):
        validate_materialization_authority(
            _row(lifecycle_evidence_reason="source_local_job_reobserved_after_health_check"),
            authorized_sources={SOURCE},
        )


def test_current_observation_must_be_exact_bound_to_silver_url() -> None:
    with pytest.raises(MaterializationStop, match="observation URL"):
        validate_materialization_authority(
            _row(latest_observation_source_url="https://example.jobs.personio.de/job/other"),
            authorized_sources={SOURCE},
        )


def test_cross_origin_detail_redirect_is_rejected() -> None:
    with pytest.raises(MaterializationStop, match="outside the authorized origin"):
        build_assessment_payload(
            row=_row(),
            authorized_sources={SOURCE},
            policy_version="product-v1-2026-08-02",
            final_url="https://other.example/job/123",
            detail_text=DETAIL,
        )


def test_role_relevant_selection_is_source_neutral() -> None:
    selected = select_rows(
        [
            _row(silver_job_id=1, title="Data Engineer"),
            _row(silver_job_id=2, title="Solution Manager"),
            _row(silver_job_id=3, title="Analytics Engineer"),
        ],
        role_relevant_only=True,
    )

    assert [row["silver_job_id"] for row in selected] == [1, 3]


def test_runner_is_plan_only_by_default_and_insert_only() -> None:
    source = Path("scripts/run_product_v1_assessment_materialization.py").read_text(
        encoding="utf-8"
    )

    assert 'default=DEFAULT_OUTPUT' in source
    assert 'ROOT / ".runtime" / "demo"' in source
    assert 'INSERT INTO job_product_assessments' in source
    assert 'UPDATE job_product_assessments' not in source
    assert '"ranking_scores_created": False' in source
    assert '"capability_fit_created": False' in source
    assert '"top5_forced": False' in source
    assert APPROVAL_TOKEN == "PRODUCT-V1-ASSESSMENT-MATERIALIZE"
