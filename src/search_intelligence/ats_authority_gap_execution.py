"""Bounded ATS authority-gap booster execution for LLM-BOOST-001.

The controller consumes an ``ATSAuthorityGapDecision`` and owns only stage order,
progress and candidate routing. Search/model callbacks may propose HTTPS ATS
URLs. A candidate can stop evidence acquisition, but can never establish tenant
authority or delegation permission; it must return to provider-specific
deterministic authority validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse

from src.search_intelligence.ats_authority_gap import ATSAuthorityGapDecision
from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.connector_feasibility import is_public_https_origin_url
from src.search_intelligence.llm_booster_policy import BoosterStage

SearchCallback = Callable[[str], Sequence[str]]
ModelCallback = Callable[
    [BoosterStage, tuple[Mapping[str, object], ...], "ATSAuthorityProgressLedger"],
    "ATSAuthorityHypothesisObservation",
]

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "msclkid",
    "ref",
    "referrer",
    "source",
}


@dataclass
class ATSAuthorityProgressLedger:
    attempted_queries: set[str] = field(default_factory=set)
    attempted_urls: set[str] = field(default_factory=set)

    def novel_queries(self, queries: Sequence[str]) -> tuple[str, ...]:
        result: list[str] = []
        for raw in queries:
            normalized = " ".join(str(raw or "").strip().lower().split())
            if not normalized or normalized in self.attempted_queries:
                continue
            self.attempted_queries.add(normalized)
            result.append(str(raw).strip())
        return tuple(result)

    def novel_urls(self, urls: Sequence[str]) -> tuple[str, ...]:
        result: list[str] = []
        for raw in urls:
            normalized = normalize_ats_authority_candidate_url(raw)
            if normalized is None or normalized in self.attempted_urls:
                continue
            self.attempted_urls.add(normalized)
            result.append(normalized)
        return tuple(result)

    def seed_urls(self, urls: Sequence[str]) -> None:
        for raw in urls:
            normalized = normalize_ats_authority_candidate_url(raw)
            if normalized is not None:
                self.attempted_urls.add(normalized)

    def clone(self) -> "ATSAuthorityProgressLedger":
        return ATSAuthorityProgressLedger(
            attempted_queries=set(self.attempted_queries),
            attempted_urls=set(self.attempted_urls),
        )


@dataclass(frozen=True)
class ATSAuthorityHypothesisObservation:
    status: str
    request_attempted: bool
    urls: tuple[str, ...]
    model: str | None = None
    response_id: str | None = None
    estimated_cost_usd: float = 0.0
    rationale: str = ""
    product_authority: bool = False


@dataclass(frozen=True)
class ATSAuthorityCandidateEvidence:
    source_stage: BoosterStage
    candidate_url: str
    provider: str
    target_hint: str | None
    expected_provider_match: bool
    deterministic_validation_required: bool = True
    tenant_authority: bool = False
    delegation_permitted: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["source_stage"] = self.source_stage.value
        return payload


@dataclass(frozen=True)
class ATSAuthorityBoosterStageEvidence:
    stage: BoosterStage
    attempted: bool
    status: str
    reason_code: str
    provider_requests: int
    proposed_urls: tuple[str, ...] = ()
    accepted_candidate_url: str | None = None
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        payload["proposed_urls"] = list(self.proposed_urls)
        return payload


@dataclass(frozen=True)
class ATSAuthorityGapExecution:
    gap_fingerprint: str
    unchanged_gap_skip: bool
    stages: tuple[ATSAuthorityBoosterStageEvidence, ...]
    candidate_evidence: tuple[ATSAuthorityCandidateEvidence, ...]
    selected_candidate_url: str | None
    provider_requests: int
    llm_requests: int
    product_writes: int = 0
    tenant_authority: bool = False
    delegation_permitted: bool = False
    product_authority: bool = False

    @property
    def candidate_found(self) -> bool:
        return self.selected_candidate_url is not None

    def to_json(self) -> dict[str, object]:
        return {
            "gap_fingerprint": self.gap_fingerprint,
            "unchanged_gap_skip": self.unchanged_gap_skip,
            "stages": [stage.to_json() for stage in self.stages],
            "candidate_evidence": [item.to_json() for item in self.candidate_evidence],
            "candidate_found": self.candidate_found,
            "selected_candidate_url": self.selected_candidate_url,
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "product_writes": self.product_writes,
            "tenant_authority": self.tenant_authority,
            "delegation_permitted": self.delegation_permitted,
            "product_authority": self.product_authority,
        }


def normalize_ats_authority_candidate_url(url: str) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().strip(".")
    if parsed.scheme.lower() != "https" or not host:
        return None
    if not is_public_https_origin_url(raw):
        return None
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query_pairs = []
    for key, value in parse_qsl(parsed.query or "", keep_blank_values=True):
        normalized_key = key.strip().lower()
        if normalized_key.startswith("utm_") or normalized_key in _TRACKING_QUERY_KEYS:
            continue
        query_pairs.append((key, value))
    return parsed._replace(
        scheme="https",
        netloc=host,
        path=path,
        params="",
        query=urlencode(sorted(query_pairs)),
        fragment="",
    ).geturl()


def deterministic_ats_authority_queries(
    *,
    company_name: str,
    expected_provider: str | None,
    maximum: int = 3,
) -> tuple[str, ...]:
    provider = str(expected_provider or "ATS").strip()
    queries = [
        f'"{company_name}" {provider} jobs careers',
        f'"{company_name}" {provider} Karriere Stellenangebote',
        f'"{company_name}" {provider} recruiting',
    ]
    result: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = " ".join(query.lower().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(query)
        if len(result) >= max(0, maximum):
            break
    return tuple(result)


def _candidate_evidence(
    *,
    source_stage: BoosterStage,
    candidate_url: str,
    expected_provider: str | None,
) -> ATSAuthorityCandidateEvidence | None:
    recognition = recognize_ats_provider(candidate_url)
    if recognition is None:
        return None
    provider_match = expected_provider is None or recognition.provider == expected_provider
    if not provider_match:
        return None
    return ATSAuthorityCandidateEvidence(
        source_stage=source_stage,
        candidate_url=candidate_url,
        provider=recognition.provider,
        target_hint=recognition.target_hint,
        expected_provider_match=provider_match,
    )


def _first_plausible_candidate(
    *,
    stage: BoosterStage,
    urls: Sequence[str],
    expected_provider: str | None,
    ledger: ATSAuthorityProgressLedger,
    collected: list[ATSAuthorityCandidateEvidence],
) -> tuple[str | None, tuple[str, ...]]:
    proposed = ledger.novel_urls(urls)
    for candidate_url in proposed:
        evidence = _candidate_evidence(
            source_stage=stage,
            candidate_url=candidate_url,
            expected_provider=expected_provider,
        )
        if evidence is None:
            continue
        collected.append(evidence)
        return candidate_url, proposed
    return None, proposed


def _skipped_stage(stage: BoosterStage, reason: str) -> ATSAuthorityBoosterStageEvidence:
    return ATSAuthorityBoosterStageEvidence(
        stage=stage,
        attempted=False,
        status="skipped",
        reason_code=reason,
        provider_requests=0,
    )


def execute_ats_authority_gap_booster(
    *,
    company_name: str,
    decision: ATSAuthorityGapDecision,
    expected_provider: str | None,
    max_tavily_requests: int,
    search: SearchCallback,
    model: ModelCallback,
    blocked_candidate_urls: Sequence[str] = (),
) -> ATSAuthorityGapExecution:
    """Run bounded search-first acquisition for alternate ATS authority evidence."""

    stages: list[ATSAuthorityBoosterStageEvidence] = []
    candidates: list[ATSAuthorityCandidateEvidence] = []
    ledger = ATSAuthorityProgressLedger()
    ledger.seed_urls(blocked_candidate_urls)
    provider_requests = 0
    llm_requests = 0

    deterministic = decision.booster_plan.stages[0]
    stages.append(
        ATSAuthorityBoosterStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=True,
            status=decision.classification,
            reason_code=deterministic.reason_code,
            provider_requests=0,
        )
    )

    if not decision.semantic_booster_eligible:
        reason = (
            "unchanged_ats_authority_gap_fingerprint"
            if decision.unchanged_gap_skip
            else "ats_semantic_booster_not_eligible"
        )
        stages.extend(
            _skipped_stage(planned.stage, reason)
            for planned in decision.booster_plan.stages[1:]
        )
        return ATSAuthorityGapExecution(
            gap_fingerprint=decision.evidence_fingerprint,
            unchanged_gap_skip=decision.unchanged_gap_skip,
            stages=tuple(stages),
            candidate_evidence=(),
            selected_candidate_url=None,
            provider_requests=0,
            llm_requests=0,
        )

    tavily = decision.booster_plan.stages[1]
    if tavily.eligible and max_tavily_requests > 0:
        urls: list[str] = []
        queries = ledger.novel_queries(
            deterministic_ats_authority_queries(
                company_name=company_name,
                expected_provider=expected_provider,
                maximum=max_tavily_requests,
            )
        )[:max_tavily_requests]
        for query in queries:
            urls.extend(str(item) for item in search(query))
            provider_requests += 1
        selected, proposed = _first_plausible_candidate(
            stage=BoosterStage.TAVILY,
            urls=urls,
            expected_provider=expected_provider,
            ledger=ledger,
            collected=candidates,
        )
        stages.append(
            ATSAuthorityBoosterStageEvidence(
                stage=BoosterStage.TAVILY,
                attempted=bool(queries),
                status="candidate_found" if selected else "unresolved",
                reason_code=tavily.reason_code,
                provider_requests=len(queries),
                proposed_urls=proposed,
                accepted_candidate_url=selected,
            )
        )
        if selected:
            stages.extend(
                _skipped_stage(planned.stage, "prior_stage_found_candidate_evidence")
                for planned in decision.booster_plan.stages[2:]
            )
            return ATSAuthorityGapExecution(
                gap_fingerprint=decision.evidence_fingerprint,
                unchanged_gap_skip=False,
                stages=tuple(stages),
                candidate_evidence=tuple(candidates),
                selected_candidate_url=selected,
                provider_requests=provider_requests,
                llm_requests=0,
            )
    else:
        stages.append(_skipped_stage(BoosterStage.TAVILY, tavily.reason_code))

    for index, planned in enumerate(decision.booster_plan.stages[2:6], start=2):
        observation = model(planned.stage, tuple(item.to_json() for item in candidates), ledger)
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        llm_requests += request_count
        selected: str | None = None
        proposed: tuple[str, ...] = ()
        if observation.status == "completed" and observation.urls:
            selected, proposed = _first_plausible_candidate(
                stage=planned.stage,
                urls=observation.urls,
                expected_provider=expected_provider,
                ledger=ledger,
                collected=candidates,
            )
        stages.append(
            ATSAuthorityBoosterStageEvidence(
                stage=planned.stage,
                attempted=observation.request_attempted,
                status=(
                    "candidate_found"
                    if selected
                    else observation.status
                    if observation.status != "completed"
                    else "unresolved"
                ),
                reason_code=planned.reason_code,
                provider_requests=request_count,
                proposed_urls=proposed,
                accepted_candidate_url=selected,
            )
        )
        if selected:
            stages.extend(
                _skipped_stage(item.stage, "prior_stage_found_candidate_evidence")
                for item in decision.booster_plan.stages[index + 1 :]
            )
            return ATSAuthorityGapExecution(
                gap_fingerprint=decision.evidence_fingerprint,
                unchanged_gap_skip=False,
                stages=tuple(stages),
                candidate_evidence=tuple(candidates),
                selected_candidate_url=selected,
                provider_requests=provider_requests,
                llm_requests=llm_requests,
            )

    deep = decision.booster_plan.stages[6]
    stages.append(
        ATSAuthorityBoosterStageEvidence(
            stage=BoosterStage.DEEP_EVIDENCE,
            attempted=True,
            status="residual_unresolved",
            reason_code=deep.reason_code,
            provider_requests=0,
        )
    )
    return ATSAuthorityGapExecution(
        gap_fingerprint=decision.evidence_fingerprint,
        unchanged_gap_skip=False,
        stages=tuple(stages),
        candidate_evidence=tuple(candidates),
        selected_candidate_url=None,
        provider_requests=provider_requests,
        llm_requests=llm_requests,
    )


__all__ = [
    "ATSAuthorityBoosterStageEvidence",
    "ATSAuthorityCandidateEvidence",
    "ATSAuthorityGapExecution",
    "ATSAuthorityHypothesisObservation",
    "ATSAuthorityProgressLedger",
    "deterministic_ats_authority_queries",
    "execute_ats_authority_gap_booster",
    "normalize_ats_authority_candidate_url",
]
