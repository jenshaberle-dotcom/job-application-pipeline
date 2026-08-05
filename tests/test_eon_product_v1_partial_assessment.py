from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.ingestion.eon_controlled_pilot import (
    EXPECTED_EXTERNAL_JOB_ID,
    EXPECTED_TITLE,
    PILOT_KEY,
    PILOT_SOURCE_NAME,
)
from src.search_intelligence.eon_product_v1_assessment import (
    APPROVAL_TOKEN,
    EXPECTED_CANONICAL_SOURCE_TYPE,
    EXPECTED_POST_ASSESSMENT_STATUS,
    bind_eon_job,
    build_partial_assessment,
)
from src.search_intelligence.product_v1 import ProductJob, product_readiness_status

RUNNER = Path("scripts/run_eon_product_v1_partial_assessment.py").read_text(
    encoding="utf-8"
)


def raw_data() -> dict:
    return {
        "source_family": "successfactors",
        "source_target": "eon_germany",
        "source_type": EXPECTED_CANONICAL_SOURCE_TYPE,
        "acquisition_boundary": {
            "listing_pages_fetched": 1,
            "pagination_enabled": False,
            "max_detail_pages": 1,
            "request_count": 2,
            "provider_requests": 0,
            "pipeline_mutation": True,
            "review_output_only_not_pipeline_input": False,
            "explicitly_authorized_pipeline_dataset": True,
        },
        "pilot_ingestion": {
            "pilot_key": PILOT_KEY,
            "authorization_status": "explicitly_authorized_pipeline_dataset",
            "preview_record_payload_used_as_job_data": False,
            "production_activation_allowed": False,
        },
        "job": {
            "title": EXPECTED_TITLE,
            "company_name": "E.ON Digital Technology GmbH",
            "location": "Essen",
            "description": (
                "E.ON Digital Technology GmbH | Permanent | Part or Full time "
                "The role works with AI, cloud platforms and enterprise data capabilities."
            ),
            "employment_metadata": ["Permanent", "Part or Full time"],
        },
        "detail_evidence": {
            "status_code": 200,
            "target_employer_verified": True,
        },
        "observed_at_utc": "2026-08-05T05:35:31+00:00",
    }


def row(payload: dict | None = None) -> dict:
    return {
        "raw_job_id": 26342,
        "silver_job_id": 466,
        "source_name": PILOT_SOURCE_NAME,
        "external_job_id": EXPECTED_EXTERNAL_JOB_ID,
        "raw_data": payload or raw_data(),
        "title": EXPECTED_TITLE,
        "canonical_source_type": EXPECTED_CANONICAL_SOURCE_TYPE,
    }


def ranking_policy() -> dict:
    return {
        "policy_key": "default",
        "status": "approved",
        "policy_version": "product-v1-2026-08-02",
    }


def hard_filter_policy() -> dict:
    return {
        "policy_key": "default",
        "status": "approved",
        "policy_version": "product-v1-2026-08-02",
        "unknown_required_evidence_action": "manual_review_required",
    }


def test_builds_partial_assessment_without_scores_or_silent_hard_filter_pass() -> None:
    binding = bind_eon_job(
        row=row(),
        expected_raw_job_id=26342,
        expected_silver_job_id=466,
    )

    assessment = build_partial_assessment(
        binding=binding,
        ranking_policy=ranking_policy(),
        hard_filter_policy=hard_filter_policy(),
    )

    assert assessment.origin_validation_status == "validated"
    assert assessment.activity_status == "active"
    assert assessment.employment_type == "permanent"
    assert assessment.employment_evidence_status == "observed"
    assert assessment.title_seniority == "senior"
    assert assessment.hard_filter_status == "unknown"
    assert assessment.required_languages == ()
    assert assessment.language_evidence_status == "unknown"
    assert assessment.weekly_hours_min is None
    assert assessment.weekly_hours_max is None
    assert assessment.weekly_hours_evidence_status == "unknown"
    assert assessment.requirements_seniority == "unknown"
    assert assessment.capability_fit_status == "unknown"
    assert assessment.profile_direction_score is None
    assert assessment.data_focus_score is None
    assert assessment.reliability_focus_score is None
    assert assessment.evidence_quality_score is None
    assert assessment.overall_quality_score is None
    assert assessment.ranking_factors["scores_intentionally_omitted"] is True
    assert assessment.explanations[2]["status"] == "permanent_full_time_option"
    assert assessment.explanations[2]["evidence"] == [
        "Permanent",
        "Part or Full time",
    ]


def test_expected_post_assessment_status_matches_canonical_product_v1_gate() -> None:
    binding = bind_eon_job(
        row=row(),
        expected_raw_job_id=26342,
        expected_silver_job_id=466,
    )
    assessment = build_partial_assessment(
        binding=binding,
        ranking_policy=ranking_policy(),
        hard_filter_policy=hard_filter_policy(),
    )
    product_job = ProductJob(
        silver_job_id=assessment.silver_job_id,
        title=EXPECTED_TITLE,
        company_name="E.ON Digital Technology GmbH",
        source_url=None,
        origin_validation_status=assessment.origin_validation_status,
        activity_status=assessment.activity_status,
        hard_filter_status=assessment.hard_filter_status,
        profile_direction_score=assessment.profile_direction_score,
        data_focus_score=assessment.data_focus_score,
        reliability_focus_score=assessment.reliability_focus_score,
        evidence_quality_score=assessment.evidence_quality_score,
        work_model=assessment.work_model,
        commute_minutes=assessment.commute_minutes,
        public_transport_quality=assessment.public_transport_quality,
    )

    assert EXPECTED_POST_ASSESSMENT_STATUS == "hard_filter_evidence_required"
    assert product_readiness_status(product_job) == EXPECTED_POST_ASSESSMENT_STATUS


@pytest.mark.parametrize(
    "full_time_evidence",
    (
        "Full time",
        "Full-time",
        "Part or Full time",
        "Full or Part time",
        "Teilzeit oder Vollzeit",
    ),
)
def test_accepts_source_grounded_full_time_option(full_time_evidence: str) -> None:
    payload = raw_data()
    payload["job"]["employment_metadata"] = ["Permanent", full_time_evidence]
    binding = bind_eon_job(
        row=row(payload),
        expected_raw_job_id=26342,
        expected_silver_job_id=466,
    )

    assessment = build_partial_assessment(
        binding=binding,
        ranking_policy=ranking_policy(),
        hard_filter_policy=hard_filter_policy(),
    )

    assert assessment.employment_type == "permanent"
    assert assessment.weekly_hours_min is None
    assert assessment.weekly_hours_max is None
    assert assessment.weekly_hours_evidence_status == "unknown"


def test_rejects_part_time_only_employment_evidence() -> None:
    payload = raw_data()
    payload["job"]["employment_metadata"] = ["Permanent", "Part time"]
    binding = bind_eon_job(
        row=row(payload),
        expected_raw_job_id=26342,
        expected_silver_job_id=466,
    )

    with pytest.raises(ValueError, match="Full-time-compatible metadata"):
        build_partial_assessment(
            binding=binding,
            ranking_policy=ranking_policy(),
            hard_filter_policy=hard_filter_policy(),
        )


def test_rejects_raw_data_without_exact_pilot_authorization() -> None:
    payload = raw_data()
    payload.pop("pilot_ingestion")

    with pytest.raises(ValueError, match="authorized E.ON pilot"):
        bind_eon_job(
            row=row(payload),
            expected_raw_job_id=26342,
            expected_silver_job_id=466,
        )


def test_rejects_provider_tainted_raw_data() -> None:
    payload = raw_data()
    payload["acquisition_boundary"]["provider_requests"] = 1

    with pytest.raises(ValueError, match="provider requests"):
        bind_eon_job(
            row=row(payload),
            expected_raw_job_id=26342,
            expected_silver_job_id=466,
        )


def test_rejects_missing_permanent_employment_evidence() -> None:
    payload = raw_data()
    payload["job"]["employment_metadata"] = ["Part or Full time"]
    binding = bind_eon_job(
        row=row(payload),
        expected_raw_job_id=26342,
        expected_silver_job_id=466,
    )

    with pytest.raises(ValueError, match="Permanent employment"):
        build_partial_assessment(
            binding=binding,
            ranking_policy=ranking_policy(),
            hard_filter_policy=hard_filter_policy(),
        )


def test_rejects_policy_version_drift() -> None:
    binding = bind_eon_job(
        row=row(),
        expected_raw_job_id=26342,
        expected_silver_job_id=466,
    )
    hard_policy = hard_filter_policy()
    hard_policy["policy_version"] = "unexpected"

    with pytest.raises(ValueError, match="policy versions differ"):
        build_partial_assessment(
            binding=binding,
            ranking_policy=ranking_policy(),
            hard_filter_policy=hard_policy,
        )


def test_runner_contract_is_one_shot_provider_free_and_honest() -> None:
    assert APPROVAL_TOKEN == "EON-PRODUCT-V1-ASSESSMENT-001"
    assert "APPROVAL_TOKEN," in RUNNER
    assert "args.approval_token != APPROVAL_TOKEN" in RUNNER
    assert "EXPECTED_POST_ASSESSMENT_STATUS" in RUNNER
    assert "gold_product_v1_job_readiness" in RUNNER
    assert "gold_product_v1_hard_filter_evaluation" in RUNNER
    assert "assessment_rows_max" in RUNNER
    assert '"provider_requests": 0' in RUNNER
    assert '"network_requests": 0' in RUNNER
    assert '"ranking_scores_created": False' in RUNNER
    assert "requests.get" not in RUNNER
    assert "Top-5" not in RUNNER


def test_payload_is_stable_for_idempotent_replay() -> None:
    binding = bind_eon_job(
        row=row(),
        expected_raw_job_id=26342,
        expected_silver_job_id=466,
    )
    first = build_partial_assessment(
        binding=binding,
        ranking_policy=ranking_policy(),
        hard_filter_policy=hard_filter_policy(),
    )
    second = build_partial_assessment(
        binding=deepcopy(binding),
        ranking_policy=deepcopy(ranking_policy()),
        hard_filter_policy=deepcopy(hard_filter_policy()),
    )

    assert first.canonical_payload() == second.canonical_payload()
