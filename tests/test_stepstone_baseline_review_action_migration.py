from pathlib import Path

from scripts.run_stepstone_baseline_production_cycle import build_baseline_plan


MIGRATION = Path(
    "db/migrations/083_allow_stepstone_production_baseline_review_action.sql"
)
EXPECTED_ACTIONS = (
    "run_baseline_only",
    "run_baseline_learning",
    "run_fetch_time_company_not_probe",
    "skip_empty_exclusion_wave",
    "run_production_baseline_census",
)


def test_production_baseline_plan_uses_persistable_review_action() -> None:
    plan = build_baseline_plan(
        source_name="stepstone",
        search_profile_name="stepstone_data_engineer_hannover",
        search_term="Machine Learning Engineer",
        run_reason="no_valid_baseline_exists",
    )

    assert plan.action == "run_production_baseline_census"


def test_migration_aligns_review_action_constraint_with_runtime() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "DROP CONSTRAINT IF EXISTS chk_stepstone_company_cycle_action" in sql
    assert "ADD CONSTRAINT chk_stepstone_company_cycle_action CHECK" in sql
    for action in EXPECTED_ACTIONS:
        assert f"'{action}'" in sql


def test_hotfix_is_forward_only_and_preserves_runtime_boundaries() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "historical migrations remain checksum-stable" in sql
    assert "no network request" in sql
    assert "source activation" in sql
    assert "scheduler mutation" in sql
