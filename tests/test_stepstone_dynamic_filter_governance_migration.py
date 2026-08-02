from pathlib import Path


MIGRATION = Path("db/migrations/080_create_stepstone_dynamic_filter_governance.sql")


def test_dynamic_filter_governance_requires_explicit_approval() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stepstone_dynamic_filter_policy" in sql
    assert "operator_decision_required" in sql
    assert "dominance_override_min_cards" in sql
    assert "dominance_override_min_share" in sql
    assert "reselection_cooldown_hours" in sql
    assert "validated_transport_name" in sql
    assert "transport_status = 'validated'" in sql
    assert "approved_by IS NOT NULL" in sql
    assert "approved_at IS NOT NULL" in sql
    assert "No default policy row is inserted" in sql


def test_capacity_policy_is_evidence_backed_and_separate() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stepstone_filter_capacity_policy" in sql
    assert "recommended_max_filter_count" in sql
    assert "supporting_completed_experiment_count" in sql
    assert "supporting_stable_trial_count" in sql
    assert "last_supporting_experiment_id" in sql
    assert "status IN ('diagnostic_only', 'candidate', 'approved', 'superseded')" in sql
    assert "supporting_completed_experiment_count >= 1" in sql
    assert "supporting_stable_trial_count >= 1" in sql


def test_policy_readiness_requires_transport_and_capacity_alignment() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW gold_stepstone_dynamic_filter_policy_readiness" in sql
    assert "p.transport_status = 'validated'" in sql
    assert "c.status = 'approved'" in sql
    assert "c.recommended_max_filter_count = p.requested_filter_count" in sql
    assert "ready_for_explicit_activation" in sql
    assert "ELSE 'blocked'" in sql
