"""Bounded Listing Discovery booster execution for LLM-BOOST-001.

This controller owns stage order and deterministic revalidation, not provider
transport. Tavily/model callbacks may propose URLs only. Every proposed URL is
boundedly fetched and passed through the canonical Listing Surface Evidence
fusion. No provider output can directly resolve product truth or write state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Sequence
from urllib.parse import urlparse

from src.search_intelligence.adaptive_origin_search import SearchProgressLedger
from src.search_intelligence.connector_feasibility import ProbeFetchResult
from src.search_intelligence.listing_route_hypothesis_provider import (
    ListingRouteHypothesisObservation,
)
from src.search_intelligence.listing_surface_evidence import (
    ListingSurfaceEvidence,
    analyze_listing_surface,
    build_listing_booster_plan,
)
from src.search_intelligence.llm_booster_policy import (
    BoosterPlan,
    BoosterStage,
    PlannedStage,
    TavilyState,
)

SearchCallback = Callable[[str], Sequence[str]]
FetchCallback = Callable[[str], ProbeFetchResult]
ModelCallback = Callable[
    [BoosterStage, tuple[Mapping[str, object], ...], SearchProgressLedger],
    ListingRouteHypothesisObservation,
]


@dataclass(frozen=True)
class ListingBoosterStageEvidence:
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
class ListingBoosterExecution:
    deterministic_evidence_fingerprint: str
    unchanged_evidence_skip: bool
    plan: BoosterPlan
    stages: tuple[ListingBoosterStageEvidence, ...]
    candidate_evidence: tuple[Mapping[str, object], ...]
    resolved_url: str | None
    resolved_listing_evidence: Mapping[str, object] | None
    provider_requests: int
    llm_requests: int
    product_writes: int = 0
    product_authority: bool = False

    @property
    def resolved(self) -> bool:
        return self.resolved_url is not None

    def to_json(self) -> dict[str, object]:
        return {
            "deterministic_evidence_fingerprint": self.deterministic_evidence_fingerprint,
            "unchanged_evidence_skip": self.unchanged_evidence_skip,
            "plan": self.plan.to_json(),
            "stages": [stage.to_json() for stage in self.stages],
            "candidate_evidence": [dict(item) for item in self.candidate_evidence],
            "resolved": self.resolved,
            "resolved_url": self.resolved_url,
            "resolved_listing_evidence": (
                None
                if self.resolved_listing_evidence is None
                else dict(self.resolved_listing_evidence)
            ),
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "product_writes": self.product_writes,
            "product_authority": self.product_authority,
        }


def deterministic_listing_queries(
    *,
    company_name: str,
    origin_url: str,
    maximum: int = 3,
) -> tuple[str, ...]:
    host = (urlparse(origin_url).hostname or "").lower().removeprefix("www.")
    queries = [
        f'"{company_name}" jobs careers',
        f'"{company_name}" Karriere Stellenangebote',
    ]
    if host:
        queries.append(f"site:{host} jobs")
    result: list[str] = []
    for query in queries:
        normalized = " ".join(query.lower().split())
        if normalized and normalized not in {" ".join(item.lower().split()) for item in result}:
            result.append(query)
        if len(result) >= max(0, maximum):
            break
    return tuple(result)


def listing_candidate_resolves(evidence: ListingSurfaceEvidence) -> bool:
    """Return whether a provider hypothesis found a deterministic Listing route.

    A lone JSON-LD ``JobPosting`` may be an individual job detail and therefore
    does not prove a listing route. Existing concrete-link, trusted-route, or
    structural list/search evidence does.
    """

    if evidence.classification in {
        "current_listing_route_proven",
        "deterministic_listing_route_candidate",
    }:
        return True
    if evidence.classification != "dynamic_listing_structure":
        return False
    jsonld = {value.lower() for value in evidence.jsonld_types}
    if jsonld.intersection({"itemlist", "searchresultspage"}):
        return True
    non_jsonld_structure = {
        "html_job_structure_present",
        "classified_job_structure_present",
    }
    return bool(non_jsonld_structure.intersection(evidence.reason_codes))


def _skipped_stage(stage: PlannedStage, reason: str) -> ListingBoosterStageEvidence:
    return ListingBoosterStageEvidence(
        stage=stage.stage,
        attempted=False,
        status="skipped",
        reason_code=reason,
        provider_requests=0,
    )


def _candidate_summary(
    *,
    source_stage: BoosterStage,
    candidate_url: str,
    evidence: ListingSurfaceEvidence,
) -> dict[str, object]:
    return {
        "source_stage": source_stage.value,
        "candidate_url": candidate_url,
        "classification": evidence.classification,
        "current_job_url_count": len(evidence.current_job_urls),
        "route_candidates": list(evidence.route_candidates),
        "delegated_route_candidates": list(evidence.delegated_route_candidates),
        "jsonld_types": list(evidence.jsonld_types),
        "external_search_gap": evidence.external_search_gap,
        "next_action": evidence.next_action,
        "reason_codes": list(evidence.reason_codes),
        "evidence_fingerprint": evidence.evidence_fingerprint,
        "deterministically_resolves_listing": listing_candidate_resolves(evidence),
        "product_authority": False,
    }


def _validate_urls(
    *,
    urls: Sequence[str],
    source_stage: BoosterStage,
    ledger: SearchProgressLedger,
    fetch: FetchCallback,
    candidate_summaries: list[Mapping[str, object]],
) -> tuple[str | None, ListingSurfaceEvidence | None, tuple[str, ...], int]:
    proposed = ledger.novel_urls(urls)
    validated = 0
    for candidate_url in proposed:
        result = fetch(candidate_url)
        evidence = analyze_listing_surface(
            origin_url=candidate_url,
            fetch_result=result,
        )
        validated += 1
        candidate_summaries.append(
            _candidate_summary(
                source_stage=source_stage,
                candidate_url=candidate_url,
                evidence=evidence,
            )
        )
        if listing_candidate_resolves(evidence):
            return candidate_url, evidence, proposed, validated
    return None, None, proposed, validated


def execute_listing_booster(
    *,
    company_name: str,
    deterministic_evidence: ListingSurfaceEvidence,
    tavily_state: TavilyState,
    max_tavily_requests: int,
    search: SearchCallback,
    fetch: FetchCallback,
    model: ModelCallback,
    previous_evidence_fingerprint: str | None = None,
) -> ListingBoosterExecution:
    plan = build_listing_booster_plan(deterministic_evidence, tavily_state=tavily_state)
    stage_records: list[ListingBoosterStageEvidence] = []
    candidate_summaries: list[Mapping[str, object]] = []
    provider_requests = 0
    llm_requests = 0
    ledger = SearchProgressLedger()

    seed_urls = [
        deterministic_evidence.origin_url or "",
        deterministic_evidence.final_url or "",
        *deterministic_evidence.current_job_urls,
        *deterministic_evidence.route_candidates,
        *deterministic_evidence.delegated_route_candidates,
    ]
    ledger.novel_urls(seed_urls)

    deterministic_stage = plan.stages[0]
    stage_records.append(
        ListingBoosterStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=True,
            status=("resolved" if plan.deterministic_resolved else "external_gap"),
            reason_code=deterministic_stage.reason_code,
            provider_requests=0,
            resolved_url=(
                deterministic_evidence.final_url if plan.deterministic_resolved else None
            ),
        )
    )

    if (
        previous_evidence_fingerprint
        and previous_evidence_fingerprint == deterministic_evidence.evidence_fingerprint
    ):
        stage_records.extend(
            _skipped_stage(stage, "unchanged_listing_evidence_fingerprint")
            for stage in plan.stages[1:]
        )
        return ListingBoosterExecution(
            deterministic_evidence_fingerprint=deterministic_evidence.evidence_fingerprint,
            unchanged_evidence_skip=True,
            plan=plan,
            stages=tuple(stage_records),
            candidate_evidence=(),
            resolved_url=None,
            resolved_listing_evidence=None,
            provider_requests=0,
            llm_requests=0,
        )

    if plan.deterministic_resolved:
        stage_records.extend(
            _skipped_stage(stage, "deterministic_result_resolved")
            for stage in plan.stages[1:]
        )
        return ListingBoosterExecution(
            deterministic_evidence_fingerprint=deterministic_evidence.evidence_fingerprint,
            unchanged_evidence_skip=False,
            plan=plan,
            stages=tuple(stage_records),
            candidate_evidence=(),
            resolved_url=deterministic_evidence.final_url,
            resolved_listing_evidence=deterministic_evidence.to_json(),
            provider_requests=0,
            llm_requests=0,
        )

    tavily_stage = plan.stages[1]
    if tavily_stage.eligible and max_tavily_requests > 0:
        all_urls: list[str] = []
        queries = ledger.novel_queries(
            deterministic_listing_queries(
                company_name=company_name,
                origin_url=str(deterministic_evidence.origin_url or ""),
                maximum=max_tavily_requests,
            )
        )
        for query in queries[:max_tavily_requests]:
            all_urls.extend(str(url) for url in search(query))
            provider_requests += 1
        resolved_url, resolved_evidence, proposed, validated = _validate_urls(
            urls=all_urls,
            source_stage=BoosterStage.TAVILY,
            ledger=ledger,
            fetch=fetch,
            candidate_summaries=candidate_summaries,
        )
        stage_records.append(
            ListingBoosterStageEvidence(
                stage=BoosterStage.TAVILY,
                attempted=bool(queries),
                status=("resolved" if resolved_url else "unresolved"),
                reason_code=tavily_stage.reason_code,
                provider_requests=len(queries[:max_tavily_requests]),
                proposed_urls=proposed,
                validated_candidate_count=validated,
                resolved_url=resolved_url,
            )
        )
        if resolved_url and resolved_evidence:
            stage_records.extend(
                _skipped_stage(stage, "prior_stage_resolved")
                for stage in plan.stages[2:]
            )
            return ListingBoosterExecution(
                deterministic_evidence_fingerprint=deterministic_evidence.evidence_fingerprint,
                unchanged_evidence_skip=False,
                plan=plan,
                stages=tuple(stage_records),
                candidate_evidence=tuple(candidate_summaries),
                resolved_url=resolved_url,
                resolved_listing_evidence=resolved_evidence.to_json(),
                provider_requests=provider_requests,
                llm_requests=0,
            )
    else:
        stage_records.append(_skipped_stage(tavily_stage, tavily_stage.reason_code))

    for planned in plan.stages[2:6]:
        observation = model(planned.stage, tuple(candidate_summaries), ledger)
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        llm_requests += request_count
        resolved_url: str | None = None
        resolved_evidence: ListingSurfaceEvidence | None = None
        proposed: tuple[str, ...] = ()
        validated = 0
        if observation.status == "completed" and observation.urls:
            resolved_url, resolved_evidence, proposed, validated = _validate_urls(
                urls=observation.urls,
                source_stage=planned.stage,
                ledger=ledger,
                fetch=fetch,
                candidate_summaries=candidate_summaries,
            )
        stage_records.append(
            ListingBoosterStageEvidence(
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
        if resolved_url and resolved_evidence:
            remaining = plan.stages[plan.stages.index(planned) + 1 :]
            stage_records.extend(
                _skipped_stage(stage, "prior_stage_resolved") for stage in remaining
            )
            return ListingBoosterExecution(
                deterministic_evidence_fingerprint=deterministic_evidence.evidence_fingerprint,
                unchanged_evidence_skip=False,
                plan=plan,
                stages=tuple(stage_records),
                candidate_evidence=tuple(candidate_summaries),
                resolved_url=resolved_url,
                resolved_listing_evidence=resolved_evidence.to_json(),
                provider_requests=provider_requests,
                llm_requests=llm_requests,
            )

    deep = plan.stages[6]
    stage_records.append(
        ListingBoosterStageEvidence(
            stage=BoosterStage.DEEP_EVIDENCE,
            attempted=True,
            status="residual_unresolved",
            reason_code=deep.reason_code,
            provider_requests=0,
        )
    )
    return ListingBoosterExecution(
        deterministic_evidence_fingerprint=deterministic_evidence.evidence_fingerprint,
        unchanged_evidence_skip=False,
        plan=plan,
        stages=tuple(stage_records),
        candidate_evidence=tuple(candidate_summaries),
        resolved_url=None,
        resolved_listing_evidence=None,
        provider_requests=provider_requests,
        llm_requests=llm_requests,
    )


__all__ = [
    "ListingBoosterExecution",
    "ListingBoosterStageEvidence",
    "deterministic_listing_queries",
    "execute_listing_booster",
    "listing_candidate_resolves",
]
