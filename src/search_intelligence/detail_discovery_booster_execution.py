"""Bounded Detail Discovery booster execution for LLM-BOOST-001.

The controller owns only canonical stage order, progress accounting and routing.
Search/model callbacks may propose HTTPS URLs, but a proposal can resolve Detail
Discovery only after the supplied deterministic validator accepts it.  The
validator is expected to enforce the existing same-employer/source and concrete
job-detail contracts; provider/model output has no such authority.

No database, gate, lifecycle, ranking, application or product write exists here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Sequence
from urllib.parse import urlparse

from src.search_intelligence.detail_discovery_gap import DetailDiscoveryGapDecision
from src.search_intelligence.listing_booster_progress import ListingProgressLedger
from src.search_intelligence.llm_booster_policy import BoosterStage, PlannedStage

SearchCallback = Callable[[str], Sequence[str]]


@dataclass(frozen=True)
class DetailCandidateValidationObservation:
    """Compact result from the existing deterministic concrete-detail validator."""

    candidate_url: str
    accepted: bool
    final_url: str | None
    classification: str
    failure_reason: str | None = None
    evidence: Mapping[str, object] | None = None
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "candidate_url": self.candidate_url,
            "accepted": self.accepted,
            "final_url": self.final_url,
            "classification": self.classification,
            "failure_reason": self.failure_reason,
            "evidence": dict(self.evidence or {}),
            "product_authority": self.product_authority,
        }


@dataclass(frozen=True)
class DetailDiscoveryHypothesisObservation:
    status: str
    request_attempted: bool
    urls: tuple[str, ...]
    model: str | None = None
    response_id: str | None = None
    estimated_cost_usd: float = 0.0
    rationale: str = ""
    product_authority: bool = False


ValidateCallback = Callable[[str], DetailCandidateValidationObservation]
ModelCallback = Callable[
    [BoosterStage, tuple[Mapping[str, object], ...], ListingProgressLedger],
    DetailDiscoveryHypothesisObservation,
]


@dataclass(frozen=True)
class DetailDiscoveryBoosterStageEvidence:
    stage: BoosterStage
    attempted: bool
    status: str
    reason_code: str
    provider_requests: int
    proposed_urls: tuple[str, ...] = ()
    validated_candidate_count: int = 0
    resolved_url: str | None = None
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        payload["proposed_urls"] = list(self.proposed_urls)
        return payload


@dataclass(frozen=True)
class DetailDiscoveryBoosterExecution:
    gap_fingerprint: str
    unchanged_gap_skip: bool
    stages: tuple[DetailDiscoveryBoosterStageEvidence, ...]
    candidate_evidence: tuple[Mapping[str, object], ...]
    resolved_url: str | None
    resolved_validation: Mapping[str, object] | None
    provider_requests: int
    llm_requests: int
    product_writes: int = 0
    product_authority: bool = False

    @property
    def resolved(self) -> bool:
        return self.resolved_url is not None

    def to_json(self) -> dict[str, object]:
        return {
            "gap_fingerprint": self.gap_fingerprint,
            "unchanged_gap_skip": self.unchanged_gap_skip,
            "stages": [item.to_json() for item in self.stages],
            "candidate_evidence": [dict(item) for item in self.candidate_evidence],
            "resolved": self.resolved,
            "resolved_url": self.resolved_url,
            "resolved_validation": (
                None if self.resolved_validation is None else dict(self.resolved_validation)
            ),
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "product_writes": self.product_writes,
            "product_authority": self.product_authority,
        }


def deterministic_detail_search_queries(
    *,
    company_name: str,
    candidate_url: str,
    maximum: int = 3,
) -> tuple[str, ...]:
    """Build bounded external-search queries after a true no-candidate D0 miss."""

    host = (urlparse(candidate_url).hostname or "").lower().removeprefix("www.")
    queries = [
        f'"{company_name}" jobs Stellenangebote',
        f'"{company_name}" job vacancy Karriere',
    ]
    if host:
        queries.append(f"site:{host} job OR jobs OR vacancy")
    result: list[str] = []
    seen: set[str] = set()
    for raw in queries:
        normalized = " ".join(raw.lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(raw)
        if len(result) >= max(0, maximum):
            break
    return tuple(result)


def _skipped_stage(stage: PlannedStage, reason: str) -> DetailDiscoveryBoosterStageEvidence:
    return DetailDiscoveryBoosterStageEvidence(
        stage=stage.stage,
        attempted=False,
        status="skipped",
        reason_code=reason,
        provider_requests=0,
    )


def _validate_urls(
    *,
    urls: Sequence[str],
    source_stage: BoosterStage,
    ledger: ListingProgressLedger,
    validate: ValidateCallback,
    summaries: list[Mapping[str, object]],
) -> tuple[
    str | None,
    DetailCandidateValidationObservation | None,
    tuple[str, ...],
    int,
]:
    proposed = ledger.novel_urls(urls)
    validated = 0
    for candidate_url in proposed:
        observation = validate(candidate_url)
        validated += 1
        summary = observation.to_json()
        summary["source_stage"] = source_stage.value
        summary["deterministic_validation_required"] = True
        summaries.append(summary)
        if observation.accepted and observation.final_url:
            return observation.final_url, observation, proposed, validated
    return None, None, proposed, validated


def execute_detail_discovery_booster(
    *,
    company_name: str,
    candidate_url: str,
    decision: DetailDiscoveryGapDecision,
    max_tavily_requests: int,
    search: SearchCallback,
    validate: ValidateCallback,
    model: ModelCallback,
    seed_urls: Sequence[str] = (),
) -> DetailDiscoveryBoosterExecution:
    """Execute search-first Detail Discovery without granting provider authority."""

    stage_records: list[DetailDiscoveryBoosterStageEvidence] = []
    summaries: list[Mapping[str, object]] = []
    provider_requests = 0
    llm_requests = 0
    ledger = ListingProgressLedger()
    ledger.novel_urls((candidate_url, *seed_urls))

    deterministic = decision.booster_plan.stages[0]
    stage_records.append(
        DetailDiscoveryBoosterStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=decision.deterministic_attempted,
            status=(
                "resolved"
                if decision.deterministic_resolved
                else decision.classification
            ),
            reason_code=deterministic.reason_code,
            provider_requests=0,
            resolved_url=(candidate_url if decision.deterministic_resolved else None),
        )
    )

    if not decision.semantic_booster_eligible:
        reason = (
            "unchanged_detail_discovery_gap_fingerprint"
            if decision.unchanged_gap_skip
            else "detail_semantic_booster_not_eligible"
        )
        stage_records.extend(
            _skipped_stage(stage, reason)
            for stage in decision.booster_plan.stages[1:]
        )
        return DetailDiscoveryBoosterExecution(
            gap_fingerprint=decision.evidence_fingerprint,
            unchanged_gap_skip=decision.unchanged_gap_skip,
            stages=tuple(stage_records),
            candidate_evidence=(),
            resolved_url=(candidate_url if decision.deterministic_resolved else None),
            resolved_validation=None,
            provider_requests=0,
            llm_requests=0,
        )

    tavily = decision.booster_plan.stages[1]
    if tavily.eligible and max_tavily_requests > 0:
        urls: list[str] = []
        queries = ledger.novel_queries(
            deterministic_detail_search_queries(
                company_name=company_name,
                candidate_url=candidate_url,
                maximum=max_tavily_requests,
            )
        )[:max_tavily_requests]
        for query in queries:
            urls.extend(str(item) for item in search(query))
            provider_requests += 1
        resolved_url, validation, proposed, validated = _validate_urls(
            urls=urls,
            source_stage=BoosterStage.TAVILY,
            ledger=ledger,
            validate=validate,
            summaries=summaries,
        )
        stage_records.append(
            DetailDiscoveryBoosterStageEvidence(
                stage=BoosterStage.TAVILY,
                attempted=bool(queries),
                status="resolved" if resolved_url else "unresolved",
                reason_code=tavily.reason_code,
                provider_requests=len(queries),
                proposed_urls=proposed,
                validated_candidate_count=validated,
                resolved_url=resolved_url,
            )
        )
        if resolved_url and validation:
            stage_records.extend(
                _skipped_stage(stage, "prior_stage_resolved")
                for stage in decision.booster_plan.stages[2:]
            )
            return DetailDiscoveryBoosterExecution(
                gap_fingerprint=decision.evidence_fingerprint,
                unchanged_gap_skip=False,
                stages=tuple(stage_records),
                candidate_evidence=tuple(summaries),
                resolved_url=resolved_url,
                resolved_validation=validation.to_json(),
                provider_requests=provider_requests,
                llm_requests=0,
            )
    else:
        stage_records.append(_skipped_stage(tavily, tavily.reason_code))

    for planned_index, planned in enumerate(
        decision.booster_plan.stages[2:6], start=2
    ):
        observation = model(planned.stage, tuple(summaries), ledger)
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        llm_requests += request_count
        resolved_url: str | None = None
        validation: DetailCandidateValidationObservation | None = None
        proposed: tuple[str, ...] = ()
        validated = 0
        if observation.status == "completed" and observation.urls:
            resolved_url, validation, proposed, validated = _validate_urls(
                urls=observation.urls,
                source_stage=planned.stage,
                ledger=ledger,
                validate=validate,
                summaries=summaries,
            )
        stage_records.append(
            DetailDiscoveryBoosterStageEvidence(
                stage=planned.stage,
                attempted=observation.request_attempted,
                status=(
                    "resolved"
                    if resolved_url
                    else observation.status
                    if observation.status != "completed"
                    else "unresolved"
                ),
                reason_code=planned.reason_code,
                provider_requests=request_count,
                proposed_urls=proposed,
                validated_candidate_count=validated,
                resolved_url=resolved_url,
            )
        )
        if resolved_url and validation:
            stage_records.extend(
                _skipped_stage(stage, "prior_stage_resolved")
                for stage in decision.booster_plan.stages[planned_index + 1 :]
            )
            return DetailDiscoveryBoosterExecution(
                gap_fingerprint=decision.evidence_fingerprint,
                unchanged_gap_skip=False,
                stages=tuple(stage_records),
                candidate_evidence=tuple(summaries),
                resolved_url=resolved_url,
                resolved_validation=validation.to_json(),
                provider_requests=provider_requests,
                llm_requests=llm_requests,
            )

    deep = decision.booster_plan.stages[6]
    stage_records.append(
        DetailDiscoveryBoosterStageEvidence(
            stage=BoosterStage.DEEP_EVIDENCE,
            attempted=True,
            status="residual_unresolved",
            reason_code=deep.reason_code,
            provider_requests=0,
        )
    )
    return DetailDiscoveryBoosterExecution(
        gap_fingerprint=decision.evidence_fingerprint,
        unchanged_gap_skip=False,
        stages=tuple(stage_records),
        candidate_evidence=tuple(summaries),
        resolved_url=None,
        resolved_validation=None,
        provider_requests=provider_requests,
        llm_requests=llm_requests,
    )


__all__ = [
    "DetailCandidateValidationObservation",
    "DetailDiscoveryBoosterExecution",
    "DetailDiscoveryBoosterStageEvidence",
    "DetailDiscoveryHypothesisObservation",
    "deterministic_detail_search_queries",
    "execute_detail_discovery_booster",
]
