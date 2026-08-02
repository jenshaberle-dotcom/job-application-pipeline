from pathlib import Path


RUNNER = Path("scripts/prepare_product_v1_runtime_migration.py")


def test_product_v1_policy_uses_atomic_managed_view_replacement() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    application_drop = source.index(
        "DROP VIEW IF EXISTS gold_product_v1_application_readiness;"
    )
    top_jobs_drop = source.index(
        "DROP VIEW IF EXISTS gold_product_v1_top_jobs;"
    )
    readiness_drop = source.index(
        "DROP VIEW IF EXISTS gold_product_v1_job_readiness;"
    )

    assert application_drop < top_jobs_drop < readiness_drop
    assert "DROP VIEW IF EXISTS gold_product_v1_application_readiness CASCADE" not in source
    assert "DROP VIEW IF EXISTS gold_product_v1_top_jobs CASCADE" not in source
    assert "DROP VIEW IF EXISTS gold_product_v1_job_readiness CASCADE" not in source
    assert "reset_product_v1_managed_views(conn)" in source
    assert "ensure_product_v1_managed_views_exist(conn)" in source
    assert "with conn.transaction():" in source


def test_policy_view_reset_occurs_before_078_sql_execution() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    loop = source[source.index("for migration in pending_targets:") :]

    reset_position = loop.index("reset_product_v1_managed_views(conn)")
    sql_read_position = loop.index(
        'sql = migration.path.read_text(encoding="utf-8")'
    )

    assert reset_position < sql_read_position
    assert "migration.migration_key == POLICY_MIGRATION_KEY" in loop


def test_runner_rejects_inconsistent_077_078_tracking_order() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "ensure_consistent_target_state" in source
    assert "078 is complete while 077 is unresolved" in source


def test_preflight_documents_transactional_view_transition() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "view_transition:" in source
    assert "execute 077 foundation" in source
    assert "three Product V1 managed views without CASCADE" in source
    assert "execute 078 and verify all three views were recreated" in source
    assert "keep the whole bundle in one transaction" in source
