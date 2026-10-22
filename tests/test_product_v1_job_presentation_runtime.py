from __future__ import annotations

from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator
from scripts.product_v1_job_presentation_runtime import _canonical_review_url, _deduplicate_origin_rows, _annotate_related_vacancies


def test_tracking_attribution_aliases_merge_but_job_query_ids_do_not():
    a = {"silver_job_id": 1, "source_url": "https://jobs.example/view?id=42&utm_source=email"}
    b = {"silver_job_id": 2, "source_url": "https://jobs.example/view?id=42&gclid=ad"}
    c = {"silver_job_id": 3, "source_url": "https://jobs.example/view?id=43"}
    unique, duplicates = _deduplicate_origin_rows([a, b, c])
    assert [r["silver_job_id"] for r in unique] == [1, 3]
    assert [r["silver_job_id"] for r in duplicates] == [2]
    assert _canonical_review_url("https://jobs.example/view?tenant=a&language=de&id=42") != _canonical_review_url("https://jobs.example/view?tenant=b&language=de&id=42")


def test_jobleads_distinct_personio_requisitions_remain_separate_related_roles():
    rows = [
        {"silver_job_id": 677, "company_name": "JobLeads Careers", "title": "Data Engineer - fully remote (working hours 5am-2pm CEST) (m/f/d)", "source_url": "https://jobleads.jobs.personio.com/job/2746946", "origin_vacancy_identifier": "2746946-224991", "origin_identifier_evidence_kind": "schema_org"},
        {"silver_job_id": 678, "company_name": "JobLeads Careers", "title": "Data Engineer - fully remote within Europe (m/f/d)", "source_url": "https://jobleads.jobs.personio.com/job/2791723", "origin_vacancy_identifier": "2791723-224991", "origin_identifier_evidence_kind": "schema_org"},
    ]
    unique, duplicates = _deduplicate_origin_rows(rows)
    assert len(unique) == 2 and duplicates == []
    annotated = _annotate_related_vacancies(unique)
    assert annotated[0]["related_vacancy_ids"] == [678]
    assert annotated[1]["related_vacancy_ids"] == [677]
    assert "related_vacancy_ids" not in rows[0]
    different_employer = [{**rows[0]}, {**rows[1], "company_name": "Other Employer"}]
    assert all(not r["related_vacancy_ids"] for r in _annotate_related_vacancies(different_employer))


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
        "lifecycle_status": "active_confirmed",
    }
    payload = {
        "job_readiness": [dict(job)],
        "top_jobs": [{**job, "product_rank": 1}],
        "summary": {},
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
    assert result["out_of_profile_jobs"] == []
    assert result["historical_jobs"] == []
    assert result["discovery_source_jobs"] == []
    assert len(result["top_jobs"]) == 1
    projected = result["top_jobs"][0]
    assert projected["product_rank"] == 1
    assert projected["overall_quality_score"] == 70.4
    assert projected["product_readiness_status"] == "rankable"
    assert projected["display_company_name"] == "1KOMMA5°"
    assert projected["legal_entity_name"] == "Heartbeat AI GmbH"
    assert projected["employment_schedule"] == "full_time"
    assert projected["profile_geography_eligible"] is True
    assert result["summary"]["review_scope_current_active_job_count"] == 1
    assert result["boundaries"]["job_presentation_enrichment_is_not_ranking_authority"] is True
    assert result["boundaries"]["review_geography_does_not_rewrite_product_truth"] is True
    assert result["boundaries"]["top5_membership_not_filtered_by_presentation"] is True


def test_berlin_only_job_moves_out_of_normal_review_scope_but_remains_auditable() -> None:
    job = {
        "silver_job_id": 174,
        "source_name": "personio:1komma5grad",
        "company_name": "1KOMMA5° GmbH",
        "title": "Senior Analytics Engineer - Growth (m/f/d)",
        "city": "Berlin",
        "work_model": "unknown",
        "commute_minutes": None,
        "product_readiness_status": "hard_filter_evidence_required",
        "lifecycle_status": "active_confirmed",
    }
    result = enrich_product_payload_for_operator(
        {"job_readiness": [job], "top_jobs": [], "summary": {}, "boundaries": {}},
        observation_evidence={},
    )

    assert result["job_readiness"] == []
    assert len(result["out_of_profile_jobs"]) == 1
    projected = result["out_of_profile_jobs"][0]
    assert projected["profile_geography_eligible"] is False
    assert projected["profile_geography_bucket"] == "explicit_outside_target"
    assert projected["product_readiness_status"] == "hard_filter_evidence_required"
    assert result["summary"]["out_of_profile_job_count"] == 1


def test_stale_origin_job_is_historical_not_normal_review_truth() -> None:
    stale = {
        "silver_job_id": 500,
        "source_name": "generic_origin:example",
        "canonical_source_type": "employer_origin_career_site",
        "company_name": "Example GmbH",
        "title": "Old Data Engineer",
        "city": "Hannover",
        "work_model": "unknown",
        "lifecycle_status": "stale_needs_refresh",
        "product_readiness_status": "activity_evidence_required",
    }

    result = enrich_product_payload_for_operator(
        {"job_readiness": [stale], "top_jobs": [], "summary": {}, "boundaries": {}},
        observation_evidence={},
    )

    assert result["job_readiness"] == []
    assert [item["silver_job_id"] for item in result["historical_jobs"]] == [500]
    assert result["summary"]["historical_review_excluded_job_count"] == 1


def test_market_sensor_job_is_discovery_evidence_not_normal_review_truth() -> None:
    sensor = {
        "silver_job_id": 501,
        "source_name": "bundesagentur_fuer_arbeit",
        "canonical_source_type": "unknown",
        "company_name": "Example GmbH",
        "title": "Sensor Data Engineer",
        "city": "Hannover",
        "work_model": "unknown",
        "lifecycle_status": "active_confirmed",
        "product_readiness_status": "assessment_required",
    }

    result = enrich_product_payload_for_operator(
        {"job_readiness": [sensor], "top_jobs": [], "summary": {}, "boundaries": {}},
        observation_evidence={},
    )

    assert result["job_readiness"] == []
    assert [item["silver_job_id"] for item in result["discovery_source_jobs"]] == [501]
    assert result["summary"]["discovery_source_review_excluded_job_count"] == 1
    assert result["boundaries"]["market_sensor_jobs_remain_discovery_evidence_only"] is True


def test_first_jap_observed_is_projected_independently_from_published_date() -> None:
    job = {
        "silver_job_id": 502,
        "source_name": "generic_origin:example",
        "canonical_source_type": "employer_origin_career_site",
        "company_name": "Example GmbH",
        "title": "Fresh Data Engineer",
        "city": "Hannover",
        "publication_date": "2026-09-01",
        "work_model": "unknown",
        "lifecycle_status": "active_confirmed",
        "product_readiness_status": "assessment_required",
    }
    evidence = {
        502: {
            "normalized_evidence": {"raw_evidence": {"job": {"company_name": "Example GmbH"}}},
            "first_jap_observed_at": "2026-09-10T08:15:00+00:00",
        }
    }

    result = enrich_product_payload_for_operator(
        {"job_readiness": [job], "top_jobs": [], "summary": {}, "boundaries": {}},
        observation_evidence=evidence,
    )

    projected = result["job_readiness"][0]
    assert projected["publication_date"] == "2026-09-01"
    assert projected["first_jap_observed_at"] == "2026-09-10T08:15:00+00:00"
    assert result["boundaries"]["first_jap_observed_is_observation_history_not_source_publish_time"] is True



def test_sensor_discovered_job_enters_all_jobs_after_normal_employer_origin_gold_promotion() -> None:
    promoted = {
        "silver_job_id": 777,
        "source_name": "generic_origin:encavis",
        "canonical_source_type": "employer_origin_career_site",
        "company_name": "Encavis GmbH",
        "title": "Data Engineer",
        "city": "Hannover",
        "work_model": "hybrid",
        "lifecycle_status": "active_confirmed",
        "product_readiness_status": "assessment_required",
    }

    result = enrich_product_payload_for_operator(
        {"job_readiness": [promoted], "top_jobs": [], "summary": {}, "boundaries": {}},
        observation_evidence={},
    )

    assert [item["silver_job_id"] for item in result["job_readiness"]] == [777]
    assert result["discovery_source_jobs"] == []
    assert result["historical_jobs"] == []
    assert result["out_of_profile_jobs"] == []
    assert result["summary"]["review_scope_current_active_job_count"] == 1
