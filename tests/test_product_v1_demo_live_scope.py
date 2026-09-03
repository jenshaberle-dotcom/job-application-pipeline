from datetime import UTC, datetime, timedelta

from src.search_intelligence.product_v1_demo_live_scope import (
    evaluate_demo_live_scope,
)


NOW = datetime(2026, 9, 3, 9, 45, tzinfo=UTC)


def base_job(**overrides):
    value = {
        "demo_actionable": True,
        "lifecycle_status": "active_confirmed",
        "last_health_checked_at": NOW - timedelta(minutes=5),
    }
    value.update(overrides)
    return value


def test_fresh_current_origin_job_is_demo_live() -> None:
    result = evaluate_demo_live_scope(base_job(), now=NOW)
    assert result.eligible is True


def test_old_health_truth_requires_refresh() -> None:
    result = evaluate_demo_live_scope(
        base_job(last_health_checked_at=NOW - timedelta(hours=2)),
        now=NOW,
    )
    assert result.eligible is False
    assert result.reason == "live_health_refresh_required"


def test_discovery_only_row_cannot_be_demo_live() -> None:
    result = evaluate_demo_live_scope(
        base_job(demo_actionable=False),
        now=NOW,
    )
    assert result.eligible is False
    assert result.reason == "employer_origin_actionability_required"
