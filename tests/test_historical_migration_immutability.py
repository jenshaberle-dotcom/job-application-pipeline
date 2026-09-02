from __future__ import annotations

import hashlib
from pathlib import Path


MIGRATION_078 = Path("db/migrations/078_activate_product_v1_operator_policy.sql")
ATOMIC_RUNNER = Path("scripts/prepare_product_v1_runtime_migration.py")
EXPECTED_SHA256 = "2052adfb1376526af92eeee7ece14759347a92c1f2cb54fc73613a8e54a95d0c"


def test_historical_migration_078_remains_byte_immutable() -> None:
    """078 is already tracked in live runtimes and must never be rewritten in place."""
    digest = hashlib.sha256(MIGRATION_078.read_bytes()).hexdigest()

    assert digest == EXPECTED_SHA256


def test_078_type_transition_stays_in_atomic_runner_not_historical_sql() -> None:
    """PR #297 resolved 077->078 view type changes without mutating migration bytes."""
    source = ATOMIC_RUNNER.read_text(encoding="utf-8")

    assert "DROP VIEW IF EXISTS gold_product_v1_application_readiness;" in source
    assert "DROP VIEW IF EXISTS gold_product_v1_top_jobs;" in source
    assert "DROP VIEW IF EXISTS gold_product_v1_job_readiness;" in source
    assert "migration.migration_key == POLICY_MIGRATION_KEY" in source
    assert "DROP VIEW IF EXISTS gold_product_v1_job_readiness CASCADE" not in source
