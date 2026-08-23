from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from typing import Final, Iterable, Mapping

from src.search_intelligence.operator_review_labels import (
    REVIEW_LABELS,
    SELECTION_REASONS,
    training_eligible,
)


DIAGNOSTICS_SCHEMA_VERSION: Final[str] = "operator-review-label-diagnostics/v1"


@dataclass(frozen=True)
class OperatorReviewLabelDiagnosticRow:
    label: str
    selection_reason: str
    deterministic_signal_visible: bool
    ml_signal_visible: bool
    llm_signal_visible: bool
    reviewed_at: datetime

    def __post_init__(self) -> None:
        if self.label not in REVIEW_LABELS:
            raise ValueError(f"label must be one of {REVIEW_LABELS!r}")
        if self.selection_reason not in SELECTION_REASONS:
            raise ValueError(f"selection_reason must be one of {SELECTION_REASONS!r}")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        for field_name in (
            "deterministic_signal_visible",
            "ml_signal_visible",
            "llm_signal_visible",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise ValueError(f"{field_name} must be boolean")


@dataclass(frozen=True)
class OperatorReviewLabelDiagnostics:
    schema_version: str
    reviewed_job_count: int
    historical_event_count: int
    correction_event_count: int
    training_eligible_count: int
    positive_count: int
    negative_count: int
    unsure_count: int
    binary_class_coverage: bool
    label_counts: dict[str, int]
    selection_reason_counts: dict[str, int]
    exposure_profile_counts: dict[str, int]
    deterministic_signal_visible_count: int
    ml_signal_visible_count: int
    llm_signal_visible_count: int
    blind_holdout_count: int
    first_reviewed_at: str | None
    last_reviewed_at: str | None
    product_authority: bool = False
    training_authority: bool = False


def diagnostic_row_from_mapping(row: Mapping[str, object]) -> OperatorReviewLabelDiagnosticRow:
    reviewed_at = row.get("reviewed_at")
    if not isinstance(reviewed_at, datetime):
        raise ValueError("reviewed_at must be a datetime")
    return OperatorReviewLabelDiagnosticRow(
        label=str(row.get("label") or ""),
        selection_reason=str(row.get("selection_reason") or ""),
        deterministic_signal_visible=row.get("deterministic_signal_visible"),  # type: ignore[arg-type]
        ml_signal_visible=row.get("ml_signal_visible"),  # type: ignore[arg-type]
        llm_signal_visible=row.get("llm_signal_visible"),  # type: ignore[arg-type]
        reviewed_at=reviewed_at,
    )


def _exposure_profile(row: OperatorReviewLabelDiagnosticRow) -> str:
    return (
        f"deterministic={int(row.deterministic_signal_visible)}|"
        f"ml={int(row.ml_signal_visible)}|"
        f"llm={int(row.llm_signal_visible)}"
    )


def build_operator_review_label_diagnostics(
    rows: Iterable[OperatorReviewLabelDiagnosticRow],
    *,
    historical_event_count: int,
) -> OperatorReviewLabelDiagnostics:
    materialized = list(rows)
    reviewed_job_count = len(materialized)
    if historical_event_count < reviewed_job_count:
        raise ValueError("historical_event_count may not be smaller than reviewed_job_count")

    label_counter = Counter(row.label for row in materialized)
    selection_counter = Counter(row.selection_reason for row in materialized)
    exposure_counter = Counter(_exposure_profile(row) for row in materialized)

    positive_count = label_counter["interesting"]
    negative_count = label_counter["not_relevant"]
    unsure_count = label_counter["unsure"]
    training_eligible_count = sum(
        count for label, count in label_counter.items() if training_eligible(label)
    )
    reviewed_times = sorted(row.reviewed_at for row in materialized)

    return OperatorReviewLabelDiagnostics(
        schema_version=DIAGNOSTICS_SCHEMA_VERSION,
        reviewed_job_count=reviewed_job_count,
        historical_event_count=historical_event_count,
        correction_event_count=historical_event_count - reviewed_job_count,
        training_eligible_count=training_eligible_count,
        positive_count=positive_count,
        negative_count=negative_count,
        unsure_count=unsure_count,
        binary_class_coverage=positive_count > 0 and negative_count > 0,
        label_counts={label: label_counter[label] for label in REVIEW_LABELS},
        selection_reason_counts={
            reason: selection_counter[reason] for reason in SELECTION_REASONS
        },
        exposure_profile_counts=dict(sorted(exposure_counter.items())),
        deterministic_signal_visible_count=sum(
            row.deterministic_signal_visible for row in materialized
        ),
        ml_signal_visible_count=sum(row.ml_signal_visible for row in materialized),
        llm_signal_visible_count=sum(row.llm_signal_visible for row in materialized),
        blind_holdout_count=selection_counter["blind_holdout"],
        first_reviewed_at=reviewed_times[0].isoformat() if reviewed_times else None,
        last_reviewed_at=reviewed_times[-1].isoformat() if reviewed_times else None,
    )


def canonical_diagnostics_payload(
    diagnostics: OperatorReviewLabelDiagnostics,
) -> dict[str, object]:
    return asdict(diagnostics)


def fingerprint_operator_review_label_diagnostics(
    diagnostics: OperatorReviewLabelDiagnostics,
) -> str:
    canonical = json.dumps(
        canonical_diagnostics_payload(diagnostics),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
