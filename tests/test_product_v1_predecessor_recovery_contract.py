from pathlib import Path


RECOVERY = Path("scripts/recover_product_v1_migration_predecessors.py")


def test_predecessor_recovery_is_targeted_and_read_only_by_default() -> None:
    source = RECOVERY.read_text(encoding="utf-8")

    assert "066_harden_origin_pattern_promotion_taxonomy.sql" in source
    assert "069_repair_origin_observed_pattern_taxonomy_columns.sql" in source
    assert "076_rebaseline_stepstone_ml_data_search_profile.sql" in source
    assert "recover_product_v1_predecessors_066_069_076" in source
    assert "if not args.apply" in source
    assert "mode: read_only" in source
    assert "unexpected_unresolved_predecessors" in source


def test_predecessor_recovery_executes_069_and_bootstraps_superseded_066() -> None:
    source = RECOVERY.read_text(encoding="utf-8")

    assert "cur.execute(repair.path.read_text" in source
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
