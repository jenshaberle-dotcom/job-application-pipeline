from __future__ import annotations

from scripts.apply_db_migrations import TrackedMigration
from scripts.run_product_v1_demo_preflight import (
    DEMO_REQUIRED_MIGRATIONS,
    _required_tracking_state,
)


def _tracked(key: str, status: str) -> TrackedMigration:
    return TrackedMigration(
        migration_key=key,
        version_number=int(key.split("_", 1)[0]),
        filename=key,
        checksum_sha256="a" * 64,
        execution_status=status,
        execution_mode="script_apply",
        applied_by="demo-test",
    )


def test_required_tracking_accepts_only_success_or_bootstrapped() -> None:
    tracked = {
        DEMO_REQUIRED_MIGRATIONS[0]: _tracked(DEMO_REQUIRED_MIGRATIONS[0], "success"),
        DEMO_REQUIRED_MIGRATIONS[1]: _tracked(DEMO_REQUIRED_MIGRATIONS[1], "bootstrapped"),
        DEMO_REQUIRED_MIGRATIONS[2]: _tracked(DEMO_REQUIRED_MIGRATIONS[2], "failed"),
    }

    qualified, failed, statuses = _required_tracking_state(tracked, [])

    assert qualified == {
        DEMO_REQUIRED_MIGRATIONS[0]: True,
        DEMO_REQUIRED_MIGRATIONS[1]: True,
        DEMO_REQUIRED_MIGRATIONS[2]: False,
    }
    assert failed == {DEMO_REQUIRED_MIGRATIONS[2]: "failed"}
    assert statuses[DEMO_REQUIRED_MIGRATIONS[2]] == "failed"


def test_checksum_mismatch_disqualifies_otherwise_successful_tracking() -> None:
    tracked = {
        key: _tracked(key, "success") for key in DEMO_REQUIRED_MIGRATIONS
    }

    qualified, failed, _statuses = _required_tracking_state(
        tracked,
        [DEMO_REQUIRED_MIGRATIONS[1]],
    )

    assert qualified[DEMO_REQUIRED_MIGRATIONS[0]] is True
    assert qualified[DEMO_REQUIRED_MIGRATIONS[1]] is False
    assert qualified[DEMO_REQUIRED_MIGRATIONS[2]] is True
    assert failed == {}
