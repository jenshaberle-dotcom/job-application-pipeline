from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Final


LABEL_CONTRACT_VERSION: Final[str] = "operator-review-relevance/v1"
REVIEW_LABELS: Final[tuple[str, ...]] = (
    "interesting",
    "not_relevant",
    "unsure",
)
TRAINING_LABELS: Final[tuple[str, ...]] = (
    "interesting",
    "not_relevant",
)
SELECTION_REASONS: Final[tuple[str, ...]] = (
    "normal_review",
    "ml_uncertainty",
    "signal_disagreement",
    "exploration_random",
    "tail_sample",
    "blind_holdout",
)
CAPTURE_SURFACES: Final[tuple[str, ...]] = (
    "control_center",
    "cli",
    "operator_import",
)
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class OperatorReviewLabelEvent:
    silver_job_id: int
    label: str
    reviewed_by: str
    reviewed_at: datetime
    evidence_cutoff: datetime
    job_evidence_fingerprint: str
    selection_reason: str = "normal_review"
    capture_surface: str = "control_center"
    deterministic_signal_visible: bool = False
    ml_signal_visible: bool = False
    llm_signal_visible: bool = False
    active_ml_artifact_id: str | None = None
    active_ml_score: float | None = None
    operator_note: str | None = None
    supersedes_label_event_id: int | None = None
    label_contract_version: str = LABEL_CONTRACT_VERSION
    ranking_authority: bool = False
    application_authority: bool = False
    product_authority: bool = False

    def __post_init__(self) -> None:
        violations = validate_operator_review_label_event(self)
        if violations:
            raise ValueError("; ".join(violations))


def validate_operator_review_label_event(event: OperatorReviewLabelEvent) -> list[str]:
    violations: list[str] = []

    if event.silver_job_id <= 0:
        violations.append("silver_job_id must be positive")
    if event.label not in REVIEW_LABELS:
        violations.append(f"label must be one of {REVIEW_LABELS!r}")
    if event.label_contract_version != LABEL_CONTRACT_VERSION:
        violations.append(f"label_contract_version must be {LABEL_CONTRACT_VERSION!r}")
    if not event.reviewed_by.strip():
        violations.append("reviewed_by must be non-empty")

    reviewed_at_is_aware = (
        event.reviewed_at.tzinfo is not None and event.reviewed_at.utcoffset() is not None
    )
    evidence_cutoff_is_aware = (
        event.evidence_cutoff.tzinfo is not None and event.evidence_cutoff.utcoffset() is not None
    )
    if not reviewed_at_is_aware:
        violations.append("reviewed_at must be timezone-aware")
    if not evidence_cutoff_is_aware:
        violations.append("evidence_cutoff must be timezone-aware")
    if reviewed_at_is_aware and evidence_cutoff_is_aware and event.evidence_cutoff > event.reviewed_at:
        violations.append("evidence_cutoff may not be later than reviewed_at")

    if not SHA256_PATTERN.fullmatch(event.job_evidence_fingerprint):
        violations.append("job_evidence_fingerprint must use sha256:<64 lowercase hex>")
    if event.selection_reason not in SELECTION_REASONS:
        violations.append(f"selection_reason must be one of {SELECTION_REASONS!r}")
    if event.capture_surface not in CAPTURE_SURFACES:
        violations.append(f"capture_surface must be one of {CAPTURE_SURFACES!r}")
    if event.active_ml_score is not None and not 0.0 <= event.active_ml_score <= 1.0:
        violations.append("active_ml_score must be between 0 and 1")
    if event.active_ml_artifact_id is not None and not event.active_ml_artifact_id.strip():
        violations.append("active_ml_artifact_id must be non-empty when supplied")
    if event.active_ml_score is not None and event.active_ml_artifact_id is None:
        violations.append("active_ml_score requires active_ml_artifact_id")
    if event.supersedes_label_event_id is not None and event.supersedes_label_event_id <= 0:
        violations.append("supersedes_label_event_id must be positive when supplied")
    if event.ranking_authority:
        violations.append("operator review labels may not claim ranking authority")
    if event.application_authority:
        violations.append("operator review labels may not claim application authority")
    if event.product_authority:
        violations.append("operator review labels may not claim product authority")

    return violations


def supervised_target(label: str) -> int | None:
    if label == "interesting":
        return 1
    if label == "not_relevant":
        return 0
    if label == "unsure":
        return None
    raise ValueError(f"unsupported operator review label: {label!r}")


def training_eligible(label: str) -> bool:
    if label not in REVIEW_LABELS:
        raise ValueError(f"unsupported operator review label: {label!r}")
    return label in TRAINING_LABELS


def canonical_label_payload(event: OperatorReviewLabelEvent) -> dict[str, object]:
    payload = asdict(event)
    payload["reviewed_at"] = event.reviewed_at.isoformat()
    payload["evidence_cutoff"] = event.evidence_cutoff.isoformat()
    return payload


def fingerprint_label_event(event: OperatorReviewLabelEvent) -> str:
    canonical = json.dumps(
        canonical_label_payload(event),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
