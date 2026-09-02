from __future__ import annotations

from src.search_intelligence.product_v1_job_presentation import (
    authoritative_employer_name,
    canonical_employment_schedule,
    classify_review_geography,
    decorate_job_for_operator,
)


def test_reviewed_personio_tenant_projects_authoritative_employer_brand() -> None:
    assert (
        authoritative_employer_name("personio:1komma5grad", "Heartbeat AI GmbH")
        == "1KOMMA5°"
    )


def test_unreviewed_source_keeps_observed_company_name() -> None:
    assert authoritative_employer_name("personio:unknown", "Example GmbH") == "Example GmbH"


def test_full_time_is_schedule_evidence_not_numeric_hours() -> None:
    assert canonical_employment_schedule("Vollzeit") == "full_time"
    assert canonical_employment_schedule("Full-time") == "full_time"
    decorated = decorate_job_for_operator(
        {
            "silver_job_id": 434,
            "source_name": "personio:1komma5grad",
            "company_name": "Heartbeat AI GmbH",
            "city": "Remote",
            "work_model": "unknown",
            "commute_minutes": None,
            "explanations": ["employment_type: source_observed — Festanstellung"],
        },
        normalized_observation_evidence={
            "raw_evidence": {
                "job": {
                    "company_name": "Heartbeat AI GmbH",
                    "schedule": "Vollzeit",
                }
            }
        },
    )
    assert decorated["display_company_name"] == "1KOMMA5°"
    assert decorated["legal_entity_name"] == "Heartbeat AI GmbH"
    assert decorated["employment_schedule"] == "full_time"
    assert decorated["employment_schedule_evidence_status"] == "observed"
    assert decorated["numeric_weekly_hours_inferred_from_schedule"] is False
    assert (
        "employment_schedule: source_observed — Full-time; numeric weekly hours not published"
        in decorated["explanations"]
    )


def test_remote_literal_is_kept_in_hannover_remote_review_scope() -> None:
    geography = classify_review_geography(
        {"city": "Remote", "work_model": "unknown", "commute_minutes": None}
    )
    assert geography.eligible is True
    assert geography.bucket == "remote_explicit"


def test_multi_location_with_remote_stays_eligible() -> None:
    geography = classify_review_geography(
        {
            "city": "Hamburg, München, Düsseldorf, remote",
            "work_model": "unknown",
            "commute_minutes": None,
        }
    )
    assert geography.eligible is True
    assert geography.bucket == "remote_explicit"


def test_berlin_only_without_remote_or_commute_is_outside_normal_review_list() -> None:
    geography = classify_review_geography(
        {"city": "Berlin", "work_model": "unknown", "commute_minutes": None}
    )
    assert geography.eligible is False
    assert geography.bucket == "explicit_outside_target"


def test_ambiguous_or_nearby_location_is_not_silently_excluded() -> None:
    geography = classify_review_geography(
        {"city": "Peine", "work_model": "unknown", "commute_minutes": None}
    )
    assert geography.eligible is True
    assert geography.bucket == "geography_review_required"


def test_observed_acceptable_commute_preserves_local_candidate() -> None:
    geography = classify_review_geography(
        {"city": "Peine", "work_model": "unknown", "commute_minutes": 42}
    )
    assert geography.eligible is True
    assert geography.bucket == "commute_observed_acceptable"
