from datetime import UTC, datetime, timedelta

import pytest

from src.search_intelligence.job_lifecycle import (
    JobHealthObservation,
    effective_product_activity,
    resolve_job_lifecycle,
    validate_job_health_observation,
)


NOW = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)


def observation(
    *,
    outcome: str,
    coverage: str,
    observed_at: datetime = NOW,
) -> JobHealthObservation:
    return JobHealthObservation(
        raw_job_id=42,
        source_name="employer_origin:test",
        external_job_id="job-42",
        source_url="https://jobs.example.test/job/42",
        outcome=outcome,
        coverage=coverage,
        evidence_reason="fixture evidence",
        observed_by="test_sensor",
        observed_at=observed_at,
    )


def test_historical_job_without_explicit_health_baseline_is_stale() -> None:
    assert (
        resolve_job_lifecycle(
            None,
            last_positive_observed_at=NOW - timedelta(days=2),
        )
        == "stale_needs_refresh"
    )


def test_positive_health_observation_confirms_active() -> None:
    assert (
        resolve_job_lifecycle(
            observation(outcome="seen_active", coverage="partial_listing")
        )
        == "active_confirmed"
    )


def test_later_source_reobservation_reactivates_after_health_check() -> None:
    health = observation(
        outcome="closed",
        coverage="exact_detail",
        observed_at=NOW - timedelta(hours=2),
    )
    assert (
        resolve_job_lifecycle(
            health,
            last_positive_observed_at=NOW - timedelta(hours=1),
        )
        == "active_confirmed"
    )


def test_partial_listing_absence_is_unverifiable_not_inactive() -> None:
    assert (
        resolve_job_lifecycle(
            observation(outcome="not_seen", coverage="partial_listing")
        )
        == "unverifiable"
    )


def test_failed_or_ambiguous_fetch_is_unverifiable() -> None:
    assert (
        resolve_job_lifecycle(
            observation(outcome="unverifiable", coverage="unknown")
        )
        == "unverifiable"
    )


def test_exact_detail_closure_confirms_inactive() -> None:
    assert (
        resolve_job_lifecycle(
            observation(outcome="closed", coverage="exact_detail")
        )
        == "inactive_confirmed"
    )


def test_complete_inventory_absence_confirms_inactive() -> None:
    assert (
        resolve_job_lifecycle(
            observation(outcome="not_seen", coverage="complete_inventory")
        )
        == "inactive_confirmed"
    )


def test_closed_requires_exact_detail_authority() -> None:
    with pytest.raises(ValueError, match="requires exact_detail"):
        validate_job_health_observation(
            observation(outcome="closed", coverage="partial_listing")
        )


def test_optional_future_freshness_cutoff_can_mark_active_as_stale() -> None:
    health = observation(
        outcome="seen_active",
        coverage="exact_detail",
        observed_at=NOW - timedelta(days=2),
    )
    assert (
        resolve_job_lifecycle(
            health,
            freshness_cutoff=NOW - timedelta(days=1),
        )
        == "stale_needs_refresh"
    )


def test_product_activity_mapping_fails_closed_for_non_current_states() -> None:
    assert effective_product_activity("active_confirmed") == "active"
    assert effective_product_activity("inactive_confirmed") == "inactive"
    assert effective_product_activity("stale_needs_refresh") == "unknown"
    assert effective_product_activity("unverifiable") == "unknown"
