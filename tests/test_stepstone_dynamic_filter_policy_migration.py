from pathlib import Path


MIGRATION = Path("db/migrations/079_create_stepstone_dynamic_filter_policy.sql")


def test_dynamic_filter_migration_separates_reselection_and_suppression_evidence() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stepstone_company_reselection_state" in sql
    assert "reselection_cooldown_until" in sql
    assert "total_dominance_override_count" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_dynamic_filter_selection_runs" in sql
    assert "predecessor_review_id" in sql
    assert "predecessor_observed_at" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_dynamic_filter_selection_items" in sql
    assert "dominance_override_applied" in sql
    assert "selected_for_next_run" in sql


def test_dynamic_filter_migration_persists_capacity_and_longitudinal_metrics() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stepstone_filter_capacity_experiments" in sql
    assert "transport_status = 'validated'" in sql
    assert "cooldown_not_before" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_filter_capacity_trials" in sql
    assert "same_filter_set_not_permutation_invariant" in sql
    assert "page_fill_count BETWEEN 0 AND 25" in sql
    assert "new_company_count" in sql
    assert "new_job_count" in sql
    assert "job_overlap_count" in sql
    assert "CREATE OR REPLACE VIEW gold_stepstone_company_discovery_longitudinal" in sql
    assert "CREATE OR REPLACE VIEW gold_stepstone_filter_capacity_evidence" in sql


def test_dynamic_filter_migration_keeps_activation_boundaries_explicit() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "does not activate StepStone requests" in sql
    assert "no source activation" in sql
    assert "no scheduler mutation" in sql
    assert "no provider call" in sql
    assert "no candidate creation" in sql
    assert "no pagination" in sql
    assert "no detail-page request" in sql
