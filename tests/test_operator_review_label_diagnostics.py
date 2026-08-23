from datetime import datetime, timedelta, timezone

import pytest

from src.search_intelligence.operator_review_label_diagnostics import (
    DIAGNOSTICS_SCHEMA_VERSION,
    OperatorReviewLabelDiagnosticRow,
    build_operator_review_label_diagnostics,
    fingerprint_operator_review_label_diagnostics,
)


NOW = datetime(2026, 8, 23, 20, 0, tzinfo=timezone.utc)


def _row(**overrides: object) -> OperatorReviewLabelDiagnosticRow:
    values: dict[str, object] = {
        "label": "interesting",
        "selection_reason": "normal_review",
        "deterministic_signal_visible": True,
        "ml_signal_visible": False,
        "llm_signal_visible": False,
        "reviewed_at": NOW,
    }
    values.update(overrides)
    return OperatorReviewLabelDiagnosticRow(**values)  # type: ignore[arg-type]


def test_diagnostics_count_labels_sampling_and_exposure_without_authority() -> None:
    rows = [
        _row(label="interesting", reviewed_at=NOW - timedelta(hours=2)),
        _row(
            label="not_relevant",
            selection_reason="exploration_random",
            deterministic_signal_visible=False,
            reviewed_at=NOW - timedelta(hours=1),
        ),
        _row(
            label="unsure",
            selection_reason="blind_holdout",
            deterministic_signal_visible=False,
            ml_signal_visible=False,
            reviewed_at=NOW,
        ),
    ]

    diagnostics = build_operator_review_label_diagnostics(
        rows,
        historical_event_count=4,
    )

    assert diagnostics.schema_version == DIAGNOSTICS_SCHEMA_VERSION
    assert diagnostics.reviewed_job_count == 3
    assert diagnostics.historical_event_count == 4
    assert diagnostics.correction_event_count == 1
    assert diagnostics.training_eligible_count == 2
    assert diagnostics.positive_count == 1
    assert diagnostics.negative_count == 1
    assert diagnostics.unsure_count == 1
    assert diagnostics.binary_class_coverage is True
    assert diagnostics.label_counts == {
        "interesting": 1,
        "not_relevant": 1,
        "unsure": 1,
    }
    assert diagnostics.selection_reason_counts["normal_review"] == 1
    assert diagnostics.selection_reason_counts["exploration_random"] == 1
    assert diagnostics.selection_reason_counts["blind_holdout"] == 1
    assert diagnostics.deterministic_signal_visible_count == 1
    assert diagnostics.ml_signal_visible_count == 0
    assert diagnostics.llm_signal_visible_count == 0
    assert diagnostics.blind_holdout_count == 1
    assert diagnostics.product_authority is False
    assert diagnostics.training_authority is False
    assert diagnostics.first_reviewed_at == (NOW - timedelta(hours=2)).isoformat()
    assert diagnostics.last_reviewed_at == NOW.isoformat()


def test_diagnostics_do_not_invent_binary_class_coverage() -> None:
    diagnostics = build_operator_review_label_diagnostics(
        [_row(label="interesting"), _row(label="unsure")],
        historical_event_count=2,
    )

    assert diagnostics.positive_count == 1
    assert diagnostics.negative_count == 0
    assert diagnostics.binary_class_coverage is False


def test_empty_diagnostics_are_valid_and_explicit() -> None:
    diagnostics = build_operator_review_label_diagnostics([], historical_event_count=0)

    assert diagnostics.reviewed_job_count == 0
    assert diagnostics.training_eligible_count == 0
    assert diagnostics.label_counts == {
        "interesting": 0,
        "not_relevant": 0,
        "unsure": 0,
    }
    assert diagnostics.binary_class_coverage is False
    assert diagnostics.first_reviewed_at is None
    assert diagnostics.last_reviewed_at is None


def test_historical_event_count_cannot_be_smaller_than_latest_job_count() -> None:
    with pytest.raises(ValueError, match="historical_event_count"):
        build_operator_review_label_diagnostics(
            [_row(), _row(label="not_relevant")],
            historical_event_count=1,
        )


def test_diagnostic_rows_fail_closed_on_contract_drift() -> None:
    with pytest.raises(ValueError, match="label must be one of"):
        _row(label="maybe")
    with pytest.raises(ValueError, match="selection_reason"):
        _row(selection_reason="model_preferred")
    with pytest.raises(ValueError, match="timezone-aware"):
        _row(reviewed_at=datetime(2026, 8, 23, 20, 0))
    with pytest.raises(ValueError, match="must be boolean"):
        _row(ml_signal_visible=1)


def test_diagnostics_fingerprint_is_stable_and_changes_with_evidence() -> None:
    first = build_operator_review_label_diagnostics([_row()], historical_event_count=1)
    same = build_operator_review_label_diagnostics([_row()], historical_event_count=1)
    changed = build_operator_review_label_diagnostics(
        [_row(label="not_relevant")],
        historical_event_count=1,
    )

    first_fingerprint = fingerprint_operator_review_label_diagnostics(first)
    assert first_fingerprint.startswith("sha256:")
    assert first_fingerprint == fingerprint_operator_review_label_diagnostics(same)
    assert first_fingerprint != fingerprint_operator_review_label_diagnostics(changed)
