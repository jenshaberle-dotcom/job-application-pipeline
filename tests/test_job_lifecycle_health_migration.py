from pathlib import Path


MIGRATION = Path("db/migrations/091_create_job_lifecycle_health_feedback.sql")


def test_lifecycle_migration_keeps_historical_memory_and_adds_health_evidence() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS job_health_observations" in sql
    assert "REFERENCES raw_jobs(id)" in sql
    assert "outcome IN ('seen_active', 'not_seen', 'closed', 'unverifiable')" in sql
    assert "'exact_detail'" in sql
    assert "'complete_inventory'" in sql
    assert "'partial_listing'" in sql
    assert "outcome <> 'closed' OR coverage = 'exact_detail'" in sql
    assert "DELETE FROM raw_jobs" not in sql
    assert "DELETE FROM silver_jobs" not in sql


def test_lifecycle_projection_is_fail_closed_for_legacy_and_weak_absence() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW gold_job_lifecycle_health" in sql
    assert "THEN 'stale_needs_refresh'" in sql
    assert "h.outcome = 'not_seen'" in sql
    assert "h.coverage = 'complete_inventory'" in sql
    assert "THEN 'inactive_confirmed'" in sql
    assert "ELSE 'unverifiable'" in sql
    assert "source_local_job_reobserved_after_health_check" in sql


def test_current_opportunity_projection_contains_only_confirmed_active_jobs() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW gold_current_job_opportunities" in sql
    assert "WHERE lifecycle.lifecycle_status = 'active_confirmed'" in sql


def test_product_readiness_uses_lifecycle_truth_not_stored_assessment_activity() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    readiness = sql[sql.index("CREATE OR REPLACE VIEW gold_product_v1_job_readiness") :]
    assert "WHEN 'active_confirmed' THEN 'active'" in readiness
    assert "WHEN 'inactive_confirmed' THEN 'inactive'" in readiness
    assert "ELSE 'unknown'" in readiness
    assert "a.activity_status AS assessment_activity_status" in readiness
    assert "WHEN activity_status = 'inactive' THEN 'blocked_inactive'" in readiness
    assert "WHEN activity_status = 'unknown'" in readiness
    assert "THEN 'activity_evidence_required'" in readiness


def test_migration_does_not_invent_a_global_freshness_ttl() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "interval '" not in sql
    assert "current_date -" not in sql
    assert "now() -" not in sql
