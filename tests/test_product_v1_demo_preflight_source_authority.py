from __future__ import annotations

from scripts.run_product_v1_demo_preflight import _top_job_candidate


def _payload(*, source_name: str, canonical_source_type: str) -> dict[str, object]:
    return {
        "top_jobs": [
            {
                "silver_job_id": 434,
                "product_rank": 1,
                "source_name": source_name,
                "title": "(Junior) Data Engineer - Data Platform (m/f/d)",
                "company_name": "Heartbeat AI GmbH",
                "canonical_source_type": canonical_source_type,
                "origin_validation_status": "validated",
                "activity_status": "active",
                "hard_filter_status": "passed",
                "product_readiness_status": "rankable",
                "overall_quality_score": 70.4,
            }
        ]
    }


def test_authorized_personio_source_is_accepted_even_with_unknown_silver_projection() -> None:
    payload = _payload(
        source_name="personio:1komma5grad",
        canonical_source_type="unknown",
    )

    selected = _top_job_candidate(
        payload,
        authorized_employer_origin_sources={"personio:1komma5grad"},
    )

    assert selected is not None
    assert selected["silver_job_id"] == 434


def test_origin_like_projection_does_not_bypass_missing_profile_authority() -> None:
    payload = _payload(
        source_name="sensor:example",
        canonical_source_type="employer_origin_ats_backed_career_site",
    )

    selected = _top_job_candidate(
        payload,
        authorized_employer_origin_sources=set(),
    )

    assert selected is None


def test_authorized_source_still_requires_all_downstream_product_gates() -> None:
    payload = _payload(
        source_name="personio:1komma5grad",
        canonical_source_type="unknown",
    )
    payload["top_jobs"][0]["hard_filter_status"] = "unknown"

    selected = _top_job_candidate(
        payload,
        authorized_employer_origin_sources={"personio:1komma5grad"},
    )

    assert selected is None
