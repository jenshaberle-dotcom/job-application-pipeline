from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.search_intelligence.operator_review_labels import (
    CAPTURE_SURFACES,
    JOB_EVIDENCE_SCHEMA_VERSION,
    LABEL_CONTRACT_VERSION,
    REVIEW_LABELS,
    SELECTION_REASONS,
    OperatorReviewLabelEvent,
    canonical_job_evidence_payload,
    fingerprint_job_evidence,
    fingerprint_label_event,
    supervised_target,
    training_eligible,
)


NOW = datetime(2026, 8, 23, 20, 30, tzinfo=timezone.utc)
FINGERPRINT = "sha256:" + "a" * 64


def _event(**overrides: object) -> OperatorReviewLabelEvent:
    values: dict[str, object] = {
        "silver_job_id": 42,
        "label": "interesting",
        "reviewed_by": "operator",
        "reviewed_at": NOW,
        "evidence_cutoff": NOW - timedelta(minutes=5),
        "job_evidence_fingerprint": FINGERPRINT,
    }
    values.update(overrides)
    return OperatorReviewLabelEvent(**values)  # type: ignore[arg-type]


def _job_evidence(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": 42,
        "raw_job_id": 314,
        "source_name": "example",
        "external_job_id": "abc-42",
        "source_url": "https://example.test/jobs/42",
        "title": "ML Engineer",
        "company_name": "Example GmbH",
        "city": "Hannover",
        "postal_code": "30159",
        "country": "DE",
        "publication_date": date(2026, 8, 22),
        "normalized_title": "ml engineer",
        "normalized_company_name": "example gmbh",
        "normalized_location": "hannover",
        "canonical_status": "active",
        "canonical_source_type": "employer_origin",
        "canonical_key_candidate": "example|ml-engineer|hannover",
        "normalized_at": NOW - timedelta(hours=1),
        "created_at": NOW - timedelta(days=1),
        "updated_at": NOW - timedelta(minutes=10),
    }
    values.update(overrides)
    return values


def test_label_vocabulary_is_small_and_task_specific() -> None:
    assert LABEL_CONTRACT_VERSION == "operator-review-relevance/v1"
    assert REVIEW_LABELS == ("interesting", "not_relevant", "unsure")
    assert SELECTION_REASONS == (
        "normal_review",
        "ml_uncertainty",
        "signal_disagreement",
        "exploration_random",
        "tail_sample",
        "blind_holdout",
    )
    assert CAPTURE_SURFACES == ("control_center", "cli", "operator_import")


def test_only_explicit_binary_labels_become_supervised_targets() -> None:
    assert supervised_target("interesting") == 1
    assert supervised_target("not_relevant") == 0
    assert supervised_target("unsure") is None
    assert training_eligible("interesting") is True
    assert training_eligible("not_relevant") is True
    assert training_eligible("unsure") is False


def test_unknown_or_unreviewed_state_cannot_silently_become_negative() -> None:
    with pytest.raises(ValueError, match="unsupported operator review label"):
        supervised_target("unreviewed")
    with pytest.raises(ValueError, match="unsupported operator review label"):
        training_eligible("unreviewed")


def test_event_requires_historical_evidence_boundary_and_fingerprint() -> None:
    with pytest.raises(ValueError, match="evidence_cutoff may not be later"):
        _event(evidence_cutoff=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="timezone-aware"):
        _event(evidence_cutoff=datetime(2026, 8, 23, 20, 0))
    with pytest.raises(ValueError, match="sha256"):
        _event(job_evidence_fingerprint="not-a-hash")


def test_prediction_can_be_recorded_even_when_hidden_from_operator() -> None:
    event = _event(
        selection_reason="blind_holdout",
        ml_signal_visible=False,
        active_ml_artifact_id="job-review-lightgbm/v1",
        active_ml_score=0.83,
    )

    assert event.ml_signal_visible is False
    assert event.active_ml_artifact_id == "job-review-lightgbm/v1"
    assert event.active_ml_score == 0.83


def test_visible_or_hidden_model_score_is_provenance_not_authority() -> None:
    event = _event(
        ml_signal_visible=True,
        active_ml_artifact_id="job-review-lightgbm/v1",
        active_ml_score=0.63,
    )

    assert event.ranking_authority is False
    assert event.application_authority is False
    assert event.product_authority is False

    with pytest.raises(ValueError, match="may not claim ranking authority"):
        _event(ranking_authority=True)
    with pytest.raises(ValueError, match="may not claim application authority"):
        _event(application_authority=True)
    with pytest.raises(ValueError, match="may not claim product authority"):
        _event(product_authority=True)


def test_ml_score_requires_artifact_identity_and_probability_range() -> None:
    with pytest.raises(ValueError, match="requires active_ml_artifact_id"):
        _event(active_ml_score=0.5)
    with pytest.raises(ValueError, match="between 0 and 1"):
        _event(active_ml_artifact_id="candidate", active_ml_score=1.2)


def test_event_fingerprint_is_stable_and_changes_with_operator_truth() -> None:
    first = _event()
    second = _event()
    changed = _event(label="not_relevant")

    assert fingerprint_label_event(first) == fingerprint_label_event(second)
    assert fingerprint_label_event(first).startswith("sha256:")
    assert fingerprint_label_event(first) != fingerprint_label_event(changed)


def test_job_evidence_fingerprint_binds_exact_mlf_silver_projection() -> None:
    row = _job_evidence()
    same = _job_evidence()
    changed = _job_evidence(title="Senior ML Engineer")

    payload = canonical_job_evidence_payload(row)
    assert payload["schema_version"] == JOB_EVIDENCE_SCHEMA_VERSION
    assert payload["source_relation"] == "silver_jobs"
    assert payload["columns"]["publication_date"] == "2026-08-22"  # type: ignore[index]
    assert payload["columns"]["updated_at"].endswith("Z")  # type: ignore[index,union-attr]
    assert fingerprint_job_evidence(row) == fingerprint_job_evidence(same)
    assert fingerprint_job_evidence(row).startswith("sha256:")
    assert fingerprint_job_evidence(row) != fingerprint_job_evidence(changed)


def test_job_evidence_fingerprint_fails_closed_on_schema_or_timestamp_drift() -> None:
    missing = _job_evidence()
    missing.pop("canonical_status")
    with pytest.raises(ValueError, match="fields mismatch"):
        fingerprint_job_evidence(missing)

    with pytest.raises(ValueError, match="timezone-aware"):
        fingerprint_job_evidence(
            _job_evidence(updated_at=datetime(2026, 8, 23, 20, 0))
        )


def test_migration_is_append_only_and_exposes_latest_training_eligibility() -> None:
    migration = Path("db/migrations/101_create_job_review_relevance_label_events.sql").read_text(
        encoding="utf-8"
    )

    assert "CREATE TABLE IF NOT EXISTS job_review_relevance_label_events" in migration
    assert "REFERENCES silver_jobs(id) ON DELETE RESTRICT" in migration
    assert "interesting', 'not_relevant', 'unsure" in migration
    assert "blind_holdout" in migration
    assert "signal_disagreement" in migration
    assert "active_ml_artifact_id" in migration
    assert "active_ml_score" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "append-only" in migration
    assert "CREATE OR REPLACE VIEW gold_job_review_relevance_labels" in migration
    assert "WHEN label = 'interesting' THEN 1" in migration
    assert "WHEN label = 'not_relevant' THEN 0" in migration
    assert "label IN ('interesting', 'not_relevant') AS training_eligible" in migration
