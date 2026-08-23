from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from scripts import product_v1_job_review_actions as actions
from scripts.product_v1_control_center_actions import ControlCenterActionStop


NOW = datetime(2026, 8, 23, 20, 30, tzinfo=timezone.utc)


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


class FakeConnection:
    def __init__(self) -> None:
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1


class FakeRepository:
    def __init__(
        self,
        *,
        evidence: dict[str, object] | None = None,
        latest: actions.LatestJobReviewLabel | None = None,
        assessed_by: str | None = "deterministic_product_v1",
    ) -> None:
        self.evidence = evidence if evidence is not None else _job_evidence()
        self.latest = latest
        self.assessed_by = assessed_by
        self.contract_checks = 0
        self.inserted = []

    def ensure_contract_available(self) -> None:
        self.contract_checks += 1

    def load_job_evidence(self, silver_job_id: int):
        assert silver_job_id == 42
        return self.evidence

    def load_latest_label(self, silver_job_id: int):
        assert silver_job_id == 42
        return self.latest

    def load_assessed_by(self, silver_job_id: int):
        assert silver_job_id == 42
        return self.assessed_by

    def insert_event(self, event):
        self.inserted.append(event)
        return 91


def _install_runtime(monkeypatch, repository: FakeRepository) -> FakeConnection:
    connection = FakeConnection()
    monkeypatch.setattr(actions, "get_database_config", lambda: {})
    monkeypatch.setattr(actions.psycopg, "connect", lambda **kwargs: connection)
    monkeypatch.setattr(actions, "JobReviewLabelRepository", lambda conn: repository)
    return connection


def test_payload_is_exact_and_operator_cannot_forge_provenance() -> None:
    assert actions.parse_job_review_label_action_payload(
        {"silver_job_id": 42, "label": "interesting"}
    ) == (42, "interesting")

    with pytest.raises(ControlCenterActionStop, match="unexpected fields: reviewed_by"):
        actions.parse_job_review_label_action_payload(
            {
                "silver_job_id": 42,
                "label": "interesting",
                "reviewed_by": "forged",
            }
        )
    with pytest.raises(ControlCenterActionStop, match="positive integer"):
        actions.parse_job_review_label_action_payload(
            {"silver_job_id": True, "label": "interesting"}
        )
    with pytest.raises(ControlCenterActionStop, match="label must be one of"):
        actions.parse_job_review_label_action_payload(
            {"silver_job_id": 42, "label": "apply"}
        )


def test_first_label_records_exact_evidence_and_no_product_authority(monkeypatch) -> None:
    repository = FakeRepository()
    connection = _install_runtime(monkeypatch, repository)

    result = actions.apply_job_review_label_action(
        silver_job_id=42,
        label="interesting",
    )

    assert result["status"] == "applied"
    assert repository.contract_checks == 1
    assert len(repository.inserted) == 1
    event = repository.inserted[0]
    assert event.silver_job_id == 42
    assert event.label == "interesting"
    assert event.reviewed_by == actions.JOB_REVIEW_LABEL_REVIEWED_BY
    assert event.selection_reason == "normal_review"
    assert event.capture_surface == "control_center"
    assert event.deterministic_signal_visible is True
    assert event.ml_signal_visible is False
    assert event.llm_signal_visible is False
    assert event.supersedes_label_event_id is None
    assert event.job_evidence_fingerprint.startswith("sha256:")
    assert connection.commits == 1
    assert result["label_event"]["training_eligible"] is True
    boundary = result["boundary"]
    assert boundary["database_writes"] == 1
    assert boundary["model_training_started"] is False
    assert boundary["gpu_execution_started"] is False
    assert boundary["ranking_mutation_performed"] is False
    assert boundary["application_action_performed"] is False
    assert boundary["product_authority"] is False


def test_same_label_on_same_evidence_is_idempotent(monkeypatch) -> None:
    evidence = _job_evidence()
    fingerprint = actions.fingerprint_job_evidence(evidence)
    repository = FakeRepository(
        evidence=evidence,
        latest=actions.LatestJobReviewLabel(
            label_event_id=77,
            label="interesting",
            job_evidence_fingerprint=fingerprint,
        ),
    )
    connection = _install_runtime(monkeypatch, repository)

    result = actions.apply_job_review_label_action(
        silver_job_id=42,
        label="interesting",
    )

    assert result["status"] == "unchanged"
    assert repository.inserted == []
    assert connection.commits == 0
    assert result["label_event"]["label_event_id"] == 77
    assert result["boundary"]["database_writes"] == 0


def test_correction_appends_superseding_event(monkeypatch) -> None:
    evidence = _job_evidence()
    repository = FakeRepository(
        evidence=evidence,
        latest=actions.LatestJobReviewLabel(
            label_event_id=77,
            label="not_relevant",
            job_evidence_fingerprint=actions.fingerprint_job_evidence(evidence),
        ),
    )
    connection = _install_runtime(monkeypatch, repository)

    result = actions.apply_job_review_label_action(
        silver_job_id=42,
        label="interesting",
    )

    assert result["status"] == "applied"
    assert len(repository.inserted) == 1
    assert repository.inserted[0].supersedes_label_event_id == 77
    assert connection.commits == 1


def test_unsure_is_recorded_but_not_training_eligible(monkeypatch) -> None:
    repository = FakeRepository()
    _install_runtime(monkeypatch, repository)

    result = actions.apply_job_review_label_action(
        silver_job_id=42,
        label="unsure",
    )

    assert result["status"] == "applied"
    assert result["label_event"]["supervised_target"] is None
    assert result["label_event"]["training_eligible"] is False


def test_evidence_newer_than_review_cutoff_fails_closed(monkeypatch) -> None:
    repository = FakeRepository(
        evidence=_job_evidence(updated_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
    )
    connection = _install_runtime(monkeypatch, repository)

    with pytest.raises(RuntimeError, match="crossed the review cutoff"):
        actions.apply_job_review_label_action(
            silver_job_id=42,
            label="interesting",
        )

    assert repository.inserted == []
    assert connection.commits == 0
