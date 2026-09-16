from __future__ import annotations

from scripts.run_f4c_data_layer_reconciliation import classify_non_current_gold


def test_non_representative_identity_member_is_explained_before_lifecycle() -> None:
    row = {
        "is_representative": False,
        "lifecycle_status": "active_confirmed",
    }
    assert classify_non_current_gold(row) == "non_representative_identity_member"


def test_non_current_lifecycle_is_explicitly_classified() -> None:
    row = {
        "is_representative": True,
        "lifecycle_status": "inactive_confirmed",
    }
    assert classify_non_current_gold(row) == "lifecycle_inactive_confirmed"


def test_active_representative_gap_is_not_silently_explained() -> None:
    row = {
        "is_representative": True,
        "lifecycle_status": "active_confirmed",
    }
    assert classify_non_current_gold(row) == "unexplained_active_representative_gap"
