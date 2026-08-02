from pathlib import Path

from scripts.recover_product_v1_migration_predecessors import (
    INCOMPATIBLE_VIEW_MARKER,
    taxonomy_repair_without_incompatible_view,
)


RECOVERY = Path("scripts/recover_product_v1_migration_predecessors.py")
MIGRATION_069 = Path(
    "db/migrations/069_repair_origin_observed_pattern_taxonomy_columns.sql"
)
MIGRATION_070 = Path(
    "db/migrations/070_repair_origin_observed_pattern_candidate_taxonomy_columns.sql"
)


def test_predecessor_recovery_is_targeted_and_read_only_by_default() -> None:
    source = RECOVERY.read_text(encoding="utf-8")

    assert "066_harden_origin_pattern_promotion_taxonomy.sql" in source
    assert "069_repair_origin_observed_pattern_taxonomy_columns.sql" in source
    assert (
        "070_repair_origin_observed_pattern_candidate_taxonomy_columns.sql"
        in source
    )
    assert "076_rebaseline_stepstone_ml_data_search_profile.sql" in source
    assert "recover_product_v1_predecessors_066_069_076" in source
    assert "if not args.apply" in source
    assert "mode: read_only" in source
    assert "unexpected_unresolved_predecessors" in source


def test_recovery_strips_only_069_incompatible_view_definition() -> None:
    original = MIGRATION_069.read_text(encoding="utf-8")
    repaired = taxonomy_repair_without_incompatible_view(original)

    assert INCOMPATIBLE_VIEW_MARKER in original
    assert INCOMPATIBLE_VIEW_MARKER not in repaired
    assert "profile_domain_signal" in repaired
    assert "CREATE INDEX IF NOT EXISTS" in repaired


def test_070_preserves_existing_view_columns_and_appends_taxonomy() -> None:
    sql = MIGRATION_070.read_text(encoding="utf-8")
    expected_order = """
    pattern_type,
    pattern_value,
    evidence_count,
    confidence,
    promotion_status,
    evidence,
    updated_at,
    pattern_category,
    usage_scope
""".strip()

    assert expected_order in sql


def test_predecessor_recovery_executes_069_and_reapplies_070() -> None:
    source = RECOVERY.read_text(encoding="utf-8")

    assert "taxonomy_repair_without_incompatible_view" in source
    assert "cur.execute(repair_sql)" in source
    assert "view_repair.path.read_text" in source
    assert "view_repaired_by_070" in source
    assert 'execution_status="success"' in source
    assert 'execution_mode="script_apply"' in source
    assert 'execution_status="bootstrapped"' in source
    assert 'execution_mode="manual_bootstrap"' in source
    assert "superseded_by_069" in source
    assert "base.path.read_text" not in source


def test_predecessor_recovery_keeps_runtime_side_effect_boundaries() -> None:
    source = RECOVERY.read_text(encoding="utf-8")

    assert "no StepStone call" in source
    assert "no provider call" in source
    assert "no source activation" in source
    assert "no scheduler mutation" in source
    assert "no application generation or submission" in source
