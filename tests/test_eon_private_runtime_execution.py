from __future__ import annotations

from pathlib import Path

import pytest

from scripts.apply_db_migrations import MigrationFile
from scripts.run_eon_private_runtime_execution import (
    REQUIRED_MIGRATIONS,
    MigrationState,
    unexpected_pending_names,
    validate_expected_sha,
)


def migration(filename: str, version: int) -> MigrationFile:
    return MigrationFile(
        migration_key=filename,
        version_number=version,
        filename=filename,
        path=Path("db/migrations") / filename,
        checksum_sha256="a" * 64,
    )


def state(*pending: str) -> MigrationState:
    return MigrationState(
        table_exists=True,
        migration_file_count=85,
        tracked_migration_count=85 - len(pending),
        pending_names=tuple(pending),
        checksum_mismatch_names=(),
        required_present=REQUIRED_MIGRATIONS,
        required_tracked=tuple(
            name for name in REQUIRED_MIGRATIONS if name not in pending
        ),
    )


def test_required_migrations_are_exactly_the_eon_and_a1_migrations() -> None:
    assert REQUIRED_MIGRATIONS == (
        "084_create_eon_controlled_pilot_profile.sql",
        "085_create_validated_connector_autonomy_a1.sql",
    )


def test_expected_sha_requires_exact_commit() -> None:
    valid = "1e8c578139bd3dadbdf78795ba0ad52621663334"
    assert validate_expected_sha(valid.upper()) == valid
    with pytest.raises(ValueError, match="exact 40-character"):
        validate_expected_sha("main")
    with pytest.raises(ValueError, match="exact 40-character"):
        validate_expected_sha(valid[:-1])


def test_unexpected_pending_migrations_fail_closed() -> None:
    assert unexpected_pending_names(state(*REQUIRED_MIGRATIONS)) == ()
    assert unexpected_pending_names(
        state("083_previous.sql", *REQUIRED_MIGRATIONS)
    ) == ("083_previous.sql",)


def test_migration_fixture_matches_runtime_dataclass() -> None:
    item = migration(REQUIRED_MIGRATIONS[0], 84)
    assert item.version_number == 84
    assert item.filename == REQUIRED_MIGRATIONS[0]


def test_execution_harness_contract_is_one_shot_and_product_safe() -> None:
    script = Path("scripts/run_eon_private_runtime_execution.py").read_text(
        encoding="utf-8"
    )
    assert '"status", "--porcelain", "--untracked-files=normal"' in script
    assert "apply_pending(" in script
    assert "run_dry_run_report(" in script
    assert "run_apply(" in script
    assert "verify_runtime_result(" in script
    assert '"apply_max_records": 1' in script
    assert '"apply_max_http_requests": 2' in script
    assert '"provider_requests": 0' in script
    assert '"scheduler_changed": False' in script
    assert '"assessment_inserted": False' in script
    assert '"application_action_performed": False' in script
    assert "workflow_dispatch" not in script
    assert "repository_dispatch" not in script
