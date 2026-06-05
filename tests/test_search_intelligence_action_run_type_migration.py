from pathlib import Path


MIGRATION = Path("db/migrations/060_extend_search_intelligence_action_run_types_for_next_safe_action.sql")


def test_next_safe_action_migration_extends_action_run_type_constraint() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "DROP CONSTRAINT IF EXISTS chk_search_intelligence_action_runs_action_type" in sql
    assert "ADD CONSTRAINT chk_search_intelligence_action_runs_action_type" in sql
    assert "'run_next_safe_action'" in sql


def test_next_safe_action_migration_preserves_existing_action_run_types() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    for action_type in (
        "'rerun_evidence_repair'",
        "'continue_candidate_review'",
        "'run_connector_validation'",
        "'approve_connector_build'",
        "'approve_connector_registration'",
    ):
        assert action_type in sql
