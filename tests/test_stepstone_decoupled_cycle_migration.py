from pathlib import Path


MIGRATION = Path("db/migrations/081_decouple_stepstone_cooldown_controls.sql")


def test_migration_separates_all_four_control_planes() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stepstone_baseline_cycle_state" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_filter_suppression_sets" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_origin_refresh_state" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_origin_refresh_signals" in sql
    assert "CREATE TABLE IF NOT EXISTS stepstone_company_title_vocabulary" in sql


def test_reselection_cooldown_is_legacy_not_activation_authority() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    approval_contract = sql.split(
        "ADD CONSTRAINT chk_stepstone_dynamic_filter_policy_approval CHECK (",
        maxsplit=1,
    )[1].split("COMMENT ON COLUMN", maxsplit=1)[0]

    assert "control_mode = 'decoupled_baseline_filter'" in approval_contract
    assert "suppression_source_mode = 'last_valid_baseline'" in approval_contract
    assert "baseline_refresh_interval_hours IS NOT NULL" in approval_contract
    assert "origin_refresh_cooldown_hours IS NOT NULL" in approval_contract
    assert "reselection_cooldown_hours IS NOT NULL" not in approval_contract
    assert "Legacy rotation control" in sql


def test_active_suppression_set_requires_validated_transport_and_baseline() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "baseline_review_id IS NOT NULL" in sql
    assert "transport_status = 'validated'" in sql
    assert "WHERE status = 'active'" in sql
    assert "uq_stepstone_active_suppression_set_scope" in sql


def test_origin_refresh_cooldown_cannot_remove_suppression_membership() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "refresh_cooldown_until" in sql
    assert "it never removes a company from the StepStone suppression set" in sql
    assert "deduplicated_refresh_cooldown" in sql


def test_vocabulary_persists_compact_company_title_observations() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "raw_title TEXT NOT NULL" in sql
    assert "normalized_title TEXT NOT NULL" in sql
    assert "observation_count INTEGER NOT NULL DEFAULT 1" in sql
    assert "job_keys JSONB NOT NULL DEFAULT '[]'::jsonb" in sql
    assert "source_mode IN ('baseline', 'filtered')" in sql


def test_readiness_requires_decoupled_mode_and_capacity_contract() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW gold_stepstone_dynamic_filter_policy_readiness" in sql
    assert "p.control_mode = 'decoupled_baseline_filter'" in sql
    assert "p.suppression_source_mode = 'last_valid_baseline'" in sql
    assert "c.recommended_max_filter_count = p.requested_filter_count" in sql
