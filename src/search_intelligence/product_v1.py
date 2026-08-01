"""Product V1 domain contracts for job ranking and application assistance.

This module is deliberately provider-free and side-effect-free. It turns approved
product policy plus evidence-backed job assessments into deterministic readiness
and ranking results. Open operator decisions remain explicit blockers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Iterable, Mapping, Sequence


class OperatorDecisionRequired(RuntimeError):
    """Raised when product behavior would require an unapproved operator choice."""


@dataclass(frozen=True)
class ProductJob:
    silver_job_id: int
    title: str
    company_name: str
    source_url: str | None
    origin_validation_status: str
    activity_status: str
    hard_filter_status: str
    profile_direction_score: float | None
    data_focus_score: float | None
    reliability_focus_score: float | None
    evidence_quality_score: float | None
    work_model: str = "unknown"
    commute_minutes: int | None = None
    public_transport_quality: str = "unknown"
    explanations: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()


@dataclass(frozen=True)
class RankingPolicy:
    status: str
    top_job_limit: int | None
    minimum_quality_score: float | None
    factor_weights: Mapping[str, float] = field(default_factory=dict)
    comparable_score_delta: float | None = None
    explanation_mode: str | None = None
    policy_version: str | None = None

    def require_approved(self) -> None:
        missing: list[str] = []
        if self.status != "approved":
            missing.append("ranking policy approval")
        if self.top_job_limit is None:
            missing.append("Top-5 count semantics")
        if self.minimum_quality_score is None:
            missing.append("minimum quality threshold")
        if self.comparable_score_delta is None:
            missing.append("definition of otherwise comparable jobs")
        if not self.factor_weights:
            missing.append("ranking factor weights")
        if self.explanation_mode is None:
            missing.append("ranking explanation mode")
        if missing:
            raise OperatorDecisionRequired(
                "Operator decisions required before authoritative ranking: "
                + ", ".join(missing)
            )
        if not 1 <= int(self.top_job_limit) <= 25:
            raise ValueError("top_job_limit must be between 1 and 25")
        if not 0 <= float(self.minimum_quality_score) <= 100:
            raise ValueError("minimum_quality_score must be between 0 and 100")
        if not 0 <= float(self.comparable_score_delta) <= 100:
            raise ValueError("comparable_score_delta must be between 0 and 100")
        supported = {
            "profile_direction",
            "data_focus",
            "reliability_focus",
            "evidence_quality",
        }
        unknown = set(self.factor_weights) - supported
        if unknown:
            raise ValueError(f"Unsupported ranking factor weights: {sorted(unknown)}")
        if any(float(weight) < 0 for weight in self.factor_weights.values()):
            raise ValueError("Ranking weights must not be negative")
        if sum(float(weight) for weight in self.factor_weights.values()) <= 0:
            raise ValueError("At least one positive ranking weight is required")


@dataclass(frozen=True)
class RankedProductJob:
    rank: int
    job: ProductJob
    overall_quality_score: float
    ranking_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ApplicationSourceDocument:
    document_type: str
    source_label: str
    source_reference: str
    content_sha256: str
    status: str


@dataclass(frozen=True)
class ApplicationSourceManifest:
    status: str
    silver_job_id: int
    documents: tuple[ApplicationSourceDocument, ...]
    blockers: tuple[str, ...]
    manifest_sha256: str | None


def product_readiness_status(job: ProductJob) -> str:
    """Return the product gate state without inventing missing product truth."""
    if job.origin_validation_status == "rejected":
        return "blocked_origin"
    if job.origin_validation_status != "validated":
        return "origin_validation_required"
    if job.activity_status == "inactive":
        return "blocked_inactive"
    if job.activity_status != "active":
        return "activity_evidence_required"
    if job.hard_filter_status == "failed":
        return "blocked_hard_filter"
    if job.hard_filter_status != "passed":
        return "hard_filter_evidence_required"
    required_scores = (
        job.profile_direction_score,
        job.data_focus_score,
        job.reliability_focus_score,
        job.evidence_quality_score,
    )
    if any(score is None for score in required_scores):
        return "assessment_required"
    return "rankable"


def _score(job: ProductJob, policy: RankingPolicy) -> float:
    values = {
        "profile_direction": job.profile_direction_score,
        "data_focus": job.data_focus_score,
        "reliability_focus": job.reliability_focus_score,
        "evidence_quality": job.evidence_quality_score,
    }
    numerator = 0.0
    denominator = 0.0
    for factor, weight in policy.factor_weights.items():
        value = values[factor]
        if value is None:
            raise ValueError(f"Missing required score {factor} for job {job.silver_job_id}")
        if not 0 <= float(value) <= 100:
            raise ValueError(f"Score {factor} outside 0..100 for job {job.silver_job_id}")
        numerator += float(value) * float(weight)
        denominator += float(weight)
    return round(numerator / denominator, 2)


def _work_model_preference(value: str) -> int:
    # Approved product truth: hybrid is a preference only between otherwise
    # comparable jobs. Onsite and remote have no global order yet.
    return 0 if value == "hybrid" else 1


def _public_transport_preference(value: str) -> int:
    return {"good": 0, "acceptable": 1, "unknown": 2, "poor": 3}.get(value, 2)


def _comparable_preference_key(item: tuple[ProductJob, float]) -> tuple[object, ...]:
    job, score = item
    commute = job.commute_minutes if job.commute_minutes is not None else 10**9
    return (
        _work_model_preference(job.work_model),
        commute,
        _public_transport_preference(job.public_transport_quality),
        -float(job.evidence_quality_score or 0),
        -score,
        job.silver_job_id,
    )


def rank_product_jobs(
    jobs: Iterable[ProductJob],
    policy: RankingPolicy,
) -> tuple[RankedProductJob, ...]:
    """Rank only fully eligible jobs under an explicitly approved policy.

    For each rank position, the highest remaining score establishes the current
    comparison window. Jobs no more than the approved delta below that score are
    treated as otherwise comparable; only inside that window may hybrid, commute
    and public-transport preferences reorder candidates.
    """
    policy.require_approved()
    assert policy.minimum_quality_score is not None
    assert policy.top_job_limit is not None
    assert policy.comparable_score_delta is not None

    remaining: list[tuple[ProductJob, float]] = []
    for job in jobs:
        if product_readiness_status(job) != "rankable":
            continue
        score = _score(job, policy)
        if score < policy.minimum_quality_score:
            continue
        remaining.append((job, score))

    ordered: list[tuple[ProductJob, float]] = []
    while remaining and len(ordered) < policy.top_job_limit:
        highest_score = max(score for _, score in remaining)
        comparable = [
            item
            for item in remaining
            if item[1] >= highest_score - float(policy.comparable_score_delta)
        ]
        selected = min(comparable, key=_comparable_preference_key)
        ordered.append(selected)
        remaining.remove(selected)

    ranked: list[RankedProductJob] = []
    for index, (job, score) in enumerate(ordered, start=1):
        reasons = [
            f"Profile direction score: {job.profile_direction_score}",
            f"Data focus score: {job.data_focus_score}",
            f"Reliability focus score: {job.reliability_focus_score}",
            f"Origin/evidence quality score: {job.evidence_quality_score}",
        ]
        if job.work_model == "hybrid":
            reasons.append(
                "Hybrid preference applied only within the approved comparable-score range."
            )
        if job.commute_minutes is not None:
            reasons.append(
                f"Observed commute estimate: {job.commute_minutes} minutes per direction."
            )
        reasons.extend(job.explanations)
        reasons.extend(f"Uncertainty: {item}" for item in job.uncertainties)
        ranked.append(
            RankedProductJob(
                rank=index,
                job=job,
                overall_quality_score=score,
                ranking_reasons=tuple(reasons),
            )
        )
    return tuple(ranked)


def build_application_source_manifest(
    *,
    job: ProductJob,
    source_documents: Sequence[ApplicationSourceDocument],
) -> ApplicationSourceManifest:
    """Build a review-safe source manifest; never generate or submit text."""
    blockers: list[str] = []
    readiness = product_readiness_status(job)
    if readiness != "rankable":
        blockers.append(f"job_not_eligible:{readiness}")

    approved_documents = tuple(
        document for document in source_documents if document.status == "approved"
    )
    document_types = {document.document_type for document in approved_documents}
    if "base_cv" not in document_types:
        blockers.append("missing_approved_base_cv")
    if "base_application_letter" not in document_types:
        blockers.append("missing_approved_base_application_letter")

    if blockers:
        return ApplicationSourceManifest(
            status="blocked",
            silver_job_id=job.silver_job_id,
            documents=approved_documents,
            blockers=tuple(blockers),
            manifest_sha256=None,
        )

    canonical_lines = [
        f"job:{job.silver_job_id}",
        f"source:{job.source_url or ''}",
        *sorted(
            f"document:{document.document_type}:{document.content_sha256}:{document.source_reference}"
            for document in approved_documents
        ),
    ]
    digest = sha256("\n".join(canonical_lines).encode("utf-8")).hexdigest()
    return ApplicationSourceManifest(
        status="ready_for_generation",
        silver_job_id=job.silver_job_id,
        documents=approved_documents,
        blockers=(),
        manifest_sha256=digest,
    )
