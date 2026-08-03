from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.run_stepstone_baseline_production_cycle import (
    baseline_is_due,
    build_baseline_plan,
)


MIGRATION = Path("db/migrations/082_activate_stepstone_baseline_runtime.sql")
ACTIVATION_SCRIPT = Path("scripts/activate_stepstone_baseline_runtime.py")
PRODUCTION_SCRIPT = Path("scripts/run_stepstone_baseline_production_cycle.py")
NOW = datetime(2026, 8, 3, 7, 0, tzinfo=UTC)


def test_migration_defines_fail_closed_runtime_and_candidate_audit() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stepstone_runtime_activations" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_candidate_persistence_events" in sql
    assert "baseline_only_active" in sql
    assert "full_cycle_active" in sql
    assert "validated_transport_name IS NOT NULL" in sql
    assert "transport_status = 'validated'" in sql
    assert "approved_max_filter_count = requested_filter_count" in sql
    assert "created_discovery_candidate" in sql
    assert "matched_existing_candidate" in sql
    assert "gold_stepstone_runtime_activation" in sql


def test_activation_backfills_without_network_or_source_activation() -> None:
    source = ACTIVATION_SCRIPT.read_text(encoding="utf-8")

    assert "activate_stepstone_baseline_only_and_persist_candidates" in source
    assert "baseline_only_active" in source
    assert "load_unpersisted_review_observations" in source
    assert "created_discovery_candidate" not in source  # action comes from pure planner
    assert "requests.get" not in source
    assert "requests.Session" not in source
    assert "no connector/source activation" in source


def test_production_runner_has_exactly_one_bounded_fetch_call() -> None:
    source = PRODUCTION_SCRIPT.read_text(encoding="utf-8")

    assert source.count("fetch_stepstone_observations(plan)") == 1
    assert "maximum_requests\": 1" in source
    assert "no_pagination\": True" in source
    assert "no_detail_pages\": True" in source
    assert "multi_not_production_status: blocked_pending_transport_and_capacity_validation" in source
    assert "baseline_only_active" in source


def test_initial_scope_runs_baseline() -> None:
    due, reason = baseline_is_due(None, now=NOW, force=False)

    assert due
    assert reason == "no_valid_baseline_exists"


def test_not_due_scope_skips_without_request() -> None:
    due, reason = baseline_is_due(
        {
            "last_baseline_at": NOW - timedelta(hours=1),
            "next_baseline_due_at": NOW + timedelta(hours=23),
            "transport_health_degraded": False,
            "vocabulary_refresh_due": False,
            "novelty_degraded": False,
        },
        now=NOW,
        force=False,
    )

    assert not due
    assert reason == "baseline_not_due"


def test_vocabulary_staleness_brings_baseline_forward() -> None:
    due, reason = baseline_is_due(
        {
            "last_baseline_at": NOW - timedelta(hours=1),
            "next_baseline_due_at": NOW + timedelta(hours=23),
            "transport_health_degraded": False,
            "vocabulary_refresh_due": True,
            "novelty_degraded": False,
        },
        now=NOW,
        force=False,
    )

    assert due
    assert reason == "company_vocabulary_refresh_due"


def test_baseline_plan_never_enables_multi_not_filtering() -> None:
    plan = build_baseline_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Machine Learning Engineer",
        run_reason="no_valid_baseline_exists",
    )

    assert plan.planned_query == "Machine Learning Engineer"
    assert plan.not_company_names == ()
    assert plan.not_company_keys == ()
    assert plan.boundary["maximum_requests"] == 1
    assert plan.boundary["candidate_persistence"] == "discovery_status_only"
    assert (
        plan.boundary["multi_not_filtering"]
        == "blocked_pending_transport_and_capacity_validation"
    )
