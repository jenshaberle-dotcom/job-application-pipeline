from __future__ import annotations

from pathlib import Path

from scripts.prepare_product_v1_demo_operator_test import (
    EXACT_104,
    RepositoryState,
    qualifies_exact_104,
)


BASE_SCHEMA = {
    "tracking_table_exists": True,
    "pending_migrations": [EXACT_104],
    "checksum_mismatches": [],
    "failed_required_tracking": {},
    "missing_repo_migration_files": [],
    "required_migration_tracking": {
        "102_create_product_v1_hard_filter_operator_reviews.sql": True,
        "103_create_product_v1_capability_fit_reviews.sql": True,
        EXACT_104: False,
    },
}


def test_exact_104_qualifies_only_as_clean_sole_pending_target() -> None:
    assert qualifies_exact_104(BASE_SCHEMA) is True


def test_exact_104_rejects_multiple_pending_or_checksum_mismatch() -> None:
    multiple = {**BASE_SCHEMA, "pending_migrations": [EXACT_104, "105_other.sql"]}
    mismatch = {**BASE_SCHEMA, "checksum_mismatches": [EXACT_104]}

    assert qualifies_exact_104(multiple) is False
    assert qualifies_exact_104(mismatch) is False


def test_exact_104_rejects_failed_or_missing_prerequisite_tracking() -> None:
    failed = {**BASE_SCHEMA, "failed_required_tracking": {EXACT_104: "failed"}}
    missing_tracking = {
        **BASE_SCHEMA,
        "required_migration_tracking": {
            **BASE_SCHEMA["required_migration_tracking"],
            "103_create_product_v1_capability_fit_reviews.sql": False,
        },
    }

    assert qualifies_exact_104(failed) is False
    assert qualifies_exact_104(missing_tracking) is False


def test_repository_state_requires_clean_exact_origin_main() -> None:
    ready = RepositoryState(head="abc", branch="main", origin_main="abc", dirty=False)
    dirty = RepositoryState(head="abc", branch="main", origin_main="abc", dirty=True)
    stale = RepositoryState(head="abc", branch="main", origin_main="def", dirty=False)
    feature = RepositoryState(head="abc", branch="feature", origin_main="abc", dirty=False)

    assert ready.exact_main is True
    assert dirty.exact_main is False
    assert stale.exact_main is False
    assert feature.exact_main is False


def test_operator_helper_has_no_broad_migration_apply_path() -> None:
    text = Path("scripts/prepare_product_v1_demo_operator_test.py").read_text(encoding="utf-8")

    assert '"--apply-exact"' in text
    assert '"--require-sole-pending"' in text
    assert '"--apply"' not in text
    assert "run_product_v1_live_demo.py" in text
    assert "--preflight-only" in text
