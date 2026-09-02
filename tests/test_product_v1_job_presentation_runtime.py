from __future__ import annotations

from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator


def test_payload_enrichment_preserves_membership_scores_and_top5_authority() -> None:
    job = {
        "silver_job_id": 434,
        "source_name": "personio:1komma5grad",
        "company_name": "Heartbeat AI GmbH",
        "title": "(Junior) Data Engineer - Data Platform (m/f/d)",
        "city": "Remote",
        "work_model": "unknown",
        "commute_minutes": None,
        "overall_quality_score": 70.4,
        "product_readiness_status": "rankable",
    }
    payload = {
        "job_readiness": [dict(job)],
        "top_jobs": [{**job, "product_rank": 1}],
        "boundaries": {"ranking_policy_authoritative": True},
    }
    evidence = {
        434: {
            "raw_evidence": {
                "job": {
                    "company_name": "Heartbeat AI GmbH",
                    "schedule": "Vollzeit",
                }
            }
        }
    }

    result = enrich_product_payload_for_operator(
        payload,
        observation_evidence=evidence,
    )

    assert len(result["job_readiness"]) == 1
    assert len(result["top_jobs"]) == 1
    projected = result["top_jobs"][0]
    assert projected["product_rank"] == 1
    assert projected["overall_quality_score"] == 70.4
    assert projected["product_readiness_status"] == "rankable"
    assert projected["display_company_name"] == "1KOMMA5° GmbH"
    assert projected["legal_entity_name"] == "Heartbeat AI GmbH"
    assert projected["employment_schedule"] == "full_time"
    assert projected["profile_geography_eligible"] is True
    assert result["boundaries"]["job_presentation_enrichment_is_not_ranking_authority"] is True
    assert result["boundaries"]["review_geography_does_not_rewrite_product_truth"] is True


def test_berlin_only_job_is_marked_outside_review_scope_without_deleting_truth() -> None:
    job = {
        "silver_job_id": 174,
        "source_name": "personio:1komma5grad",
        "company_name": "1KOMMA5° GmbH",
        "title": "Senior Analytics Engineer - Growth (m/f/d)",
        "city": "Berlin",
        "work_model": "unknown",
        "commute_minutes": None,
        "product_readiness_status": "hard_filter_evidence_required",
    }
    result = enrich_product_payload_for_operator(
        {"job_readiness": [job], "top_jobs": [], "boundaries": {}},
        observation_evidence={},
    )

    assert len(result["job_readiness"]) == 1
    projected = result["job_readiness"][0]
    assert projected["profile_geography_eligible"] is False
    assert projected["profile_geography_bucket"] == "explicit_outside_target"
    assert projected["product_readiness_status"] == "hard_filter_evidence_required"
