"""Narrowly allowlisted operator-review label capture for Product V1.

The action records append-only operator ground truth for the scoped
``operator_review_relevance`` target. The client may choose only the Silver job
and one frozen label. Reviewer identity, timestamps, evidence fingerprint,
sampling reason and signal-exposure provenance are owned by the server.

This action does not train or execute a model and cannot mutate ranking, Top-5,
lifecycle, sources, providers, schedulers or applications.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

import psycopg
from psycopg.rows import dict_row

from scripts.product_v1_control_center_actions import ControlCenterActionStop
from src.config import get_database_config
from src.search_intelligence.ml_snapshot_plan import (
    default_training_snapshot_plan,
    snapshot_column_names,
)
from src.search_intelligence.operator_review_labels import (
    LABEL_CONTRACT_VERSION,
    REVIEW_LABELS,
    OperatorReviewLabelEvent,
    fingerprint_job_evidence,
    supervised_target,
    training_eligible,
)


JOB_REVIEW_LABEL_ACTION_PATH: Final[str] = "/api/v1/product-v1/job-review-label"
JOB_REVIEW_LABEL_ACTION_SCHEMA_VERSION: Final[str] = (
    "product_v1.control_center.job_review_label_action.v1"
)
JOB_REVIEW_LABEL_REVIEWED_BY: Final[str] = "product_v1_control_center_operator"
JOB_REVIEW_LABEL_SELECTION_REASON: Final[str] = "normal_review"
JOB_REVIEW_LABEL_CAPTURE_SURFACE: Final[str] = "control_center"
ALLOWED_JOB_REVIEW_LABEL_ACTION_FIELDS: Final[frozenset[str]] = frozenset(
    {"silver_job_id", "label"}
)


@dataclass(frozen=True)
class LatestJobReviewLabel:
    label_event_id: int
    label: str
    job_evidence_fingerprint: str


class JobReviewLabelRepository:
    """Small DB boundary for one append-only operator label action."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def ensure_contract_available(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('public.job_review_relevance_label_events')"
            )
            row = cursor.fetchone()
        relation = next(iter(row.values())) if isinstance(row, Mapping) else row[0]
        if relation is None:
            raise RuntimeError(
                "job review label contract is not available in PostgreSQL; apply migration 101"
            )

    def load_job_evidence(self, silver_job_id: int) -> Mapping[str, object] | None:
        columns = snapshot_column_names(default_training_snapshot_plan())
        selected = ", ".join(columns)
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {selected} FROM silver_jobs WHERE id = %s FOR SHARE",
                (silver_job_id,),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def load_latest_label(self, silver_job_id: int) -> LatestJobReviewLabel | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, label, job_evidence_fingerprint
                FROM job_review_relevance_label_events
                WHERE silver_job_id = %s
                ORDER BY reviewed_at DESC, id DESC
                LIMIT 1
                """,
                (silver_job_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return LatestJobReviewLabel(
            label_event_id=int(row["id"]),
            label=str(row["label"]),
            job_evidence_fingerprint=str(row["job_evidence_fingerprint"]),
        )

    def load_assessed_by(self, silver_job_id: int) -> str | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT assessed_by FROM job_product_assessments WHERE silver_job_id = %s",
                (silver_job_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        value = row["assessed_by"]
        return str(value) if value is not None else None

    def insert_event(self, event: OperatorReviewLabelEvent) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO job_review_relevance_label_events (
                    silver_job_id,
                    label,
                    label_contract_version,
                    reviewed_by,
                    reviewed_at,
                    evidence_cutoff,
                    job_evidence_fingerprint,
                    selection_reason,
                    capture_surface,
                    deterministic_signal_visible,
                    ml_signal_visible,
                    llm_signal_visible,
                    active_ml_artifact_id,
                    active_ml_score,
                    operator_note,
                    supersedes_label_event_id
                )
                VALUES (
                    %(silver_job_id)s,
                    %(label)s,
                    %(label_contract_version)s,
                    %(reviewed_by)s,
                    %(reviewed_at)s,
                    %(evidence_cutoff)s,
                    %(job_evidence_fingerprint)s,
                    %(selection_reason)s,
                    %(capture_surface)s,
                    %(deterministic_signal_visible)s,
                    %(ml_signal_visible)s,
                    %(llm_signal_visible)s,
                    %(active_ml_artifact_id)s,
                    %(active_ml_score)s,
                    %(operator_note)s,
                    %(supersedes_label_event_id)s
                )
                RETURNING id
                """,
                {
                    "silver_job_id": event.silver_job_id,
                    "label": event.label,
                    "label_contract_version": event.label_contract_version,
                    "reviewed_by": event.reviewed_by,
                    "reviewed_at": event.reviewed_at,
                    "evidence_cutoff": event.evidence_cutoff,
                    "job_evidence_fingerprint": event.job_evidence_fingerprint,
                    "selection_reason": event.selection_reason,
                    "capture_surface": event.capture_surface,
                    "deterministic_signal_visible": event.deterministic_signal_visible,
                    "ml_signal_visible": event.ml_signal_visible,
                    "llm_signal_visible": event.llm_signal_visible,
                    "active_ml_artifact_id": event.active_ml_artifact_id,
                    "active_ml_score": event.active_ml_score,
                    "operator_note": event.operator_note,
                    "supersedes_label_event_id": event.supersedes_label_event_id,
                },
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("job review label insert did not return an event id")
        return int(row["id"])


def parse_job_review_label_action_payload(payload: object) -> tuple[int, str]:
    """Validate the exact low-authority label action shape."""

    if not isinstance(payload, Mapping):
        raise ControlCenterActionStop("action payload must be a JSON object")
    keys = {str(key) for key in payload}
    if keys != ALLOWED_JOB_REVIEW_LABEL_ACTION_FIELDS:
        unexpected = sorted(keys - ALLOWED_JOB_REVIEW_LABEL_ACTION_FIELDS)
        missing = sorted(ALLOWED_JOB_REVIEW_LABEL_ACTION_FIELDS - keys)
        detail: list[str] = []
        if unexpected:
            detail.append(f"unexpected fields: {', '.join(unexpected)}")
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        raise ControlCenterActionStop("; ".join(detail) or "invalid action fields")

    raw_job_id = payload.get("silver_job_id")
    if isinstance(raw_job_id, bool) or not isinstance(raw_job_id, int) or raw_job_id <= 0:
        raise ControlCenterActionStop("silver_job_id must be a positive integer")

    raw_label = payload.get("label")
    if not isinstance(raw_label, str) or raw_label not in REVIEW_LABELS:
        raise ControlCenterActionStop(f"label must be one of {REVIEW_LABELS!r}")
    return raw_job_id, raw_label


def _validate_evidence_cutoff(
    evidence: Mapping[str, object],
    *,
    evidence_cutoff: datetime,
) -> None:
    for field_name in ("normalized_at", "created_at", "updated_at"):
        value = evidence.get(field_name)
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError(f"{field_name} is not timezone-aware in Silver evidence")
        if value.astimezone(UTC) > evidence_cutoff:
            raise RuntimeError(
                f"Silver evidence crossed the review cutoff through {field_name}"
            )


def _result(
    *,
    status: str,
    event_id: int,
    event: OperatorReviewLabelEvent,
    recorded: bool,
) -> dict[str, object]:
    return {
        "schema_version": JOB_REVIEW_LABEL_ACTION_SCHEMA_VERSION,
        "action": "job_review_relevance_label",
        "status": status,
        "label_event": {
            "label_event_id": event_id,
            "silver_job_id": event.silver_job_id,
            "label": event.label,
            "label_contract_version": LABEL_CONTRACT_VERSION,
            "reviewed_by": event.reviewed_by,
            "reviewed_at": event.reviewed_at.isoformat(),
            "evidence_cutoff": event.evidence_cutoff.isoformat(),
            "job_evidence_fingerprint": event.job_evidence_fingerprint,
            "selection_reason": event.selection_reason,
            "capture_surface": event.capture_surface,
            "deterministic_signal_visible": event.deterministic_signal_visible,
            "ml_signal_visible": event.ml_signal_visible,
            "llm_signal_visible": event.llm_signal_visible,
            "supersedes_label_event_id": event.supersedes_label_event_id,
            "supervised_target": supervised_target(event.label),
            "training_eligible": training_eligible(event.label),
            "recorded": recorded,
        },
        "boundary": {
            "database_writes": 1 if recorded else 0,
            "provider_requests_performed": False,
            "model_training_started": False,
            "external_execution_started": False,
            "gpu_execution_started": False,
            "ranking_mutation_performed": False,
            "top5_mutation_performed": False,
            "lifecycle_mutation_performed": False,
            "source_activation_performed": False,
            "application_action_performed": False,
            "product_authority": False,
        },
    }


def apply_job_review_label_action(
    *,
    silver_job_id: int,
    label: str,
) -> dict[str, object]:
    """Record one explicit operator label against exact current Silver evidence."""

    parsed_job_id, parsed_label = parse_job_review_label_action_payload(
        {"silver_job_id": silver_job_id, "label": label}
    )
    reviewed_at = datetime.now(UTC)

    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        repo = JobReviewLabelRepository(conn)
        repo.ensure_contract_available()
        evidence = repo.load_job_evidence(parsed_job_id)
        if evidence is None:
            raise RuntimeError(f"Silver job {parsed_job_id} does not exist")
        _validate_evidence_cutoff(evidence, evidence_cutoff=reviewed_at)
        evidence_fingerprint = fingerprint_job_evidence(evidence)
        latest = repo.load_latest_label(parsed_job_id)
        assessed_by = repo.load_assessed_by(parsed_job_id)
        deterministic_visible = assessed_by == "deterministic_product_v1"

        event = OperatorReviewLabelEvent(
            silver_job_id=parsed_job_id,
            label=parsed_label,
            reviewed_by=JOB_REVIEW_LABEL_REVIEWED_BY,
            reviewed_at=reviewed_at,
            evidence_cutoff=reviewed_at,
            job_evidence_fingerprint=evidence_fingerprint,
            selection_reason=JOB_REVIEW_LABEL_SELECTION_REASON,
            capture_surface=JOB_REVIEW_LABEL_CAPTURE_SURFACE,
            deterministic_signal_visible=deterministic_visible,
            ml_signal_visible=False,
            llm_signal_visible=False,
            supersedes_label_event_id=(latest.label_event_id if latest is not None else None),
        )

        if (
            latest is not None
            and latest.label == parsed_label
            and latest.job_evidence_fingerprint == evidence_fingerprint
        ):
            return _result(
                status="unchanged",
                event_id=latest.label_event_id,
                event=event,
                recorded=False,
            )

        event_id = repo.insert_event(event)
        conn.commit()

    return _result(status="applied", event_id=event_id, event=event, recorded=True)


__all__ = [
    "ALLOWED_JOB_REVIEW_LABEL_ACTION_FIELDS",
    "JOB_REVIEW_LABEL_ACTION_PATH",
    "JOB_REVIEW_LABEL_ACTION_SCHEMA_VERSION",
    "JOB_REVIEW_LABEL_REVIEWED_BY",
    "JobReviewLabelRepository",
    "LatestJobReviewLabel",
    "apply_job_review_label_action",
    "parse_job_review_label_action_payload",
]
