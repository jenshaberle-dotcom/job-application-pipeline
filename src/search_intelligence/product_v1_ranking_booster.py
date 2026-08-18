"""Bounded AI evidence helper for Product V1 ranking factors.

The deterministic ranking rubric always owns numeric component scores. Models may
only identify exact same-detail quotes and one controlled signal category for a
still-weak fit factor. A deterministic validator then verifies the quote, signal
category and fixed point value before any component score can change.

The approved Product V1 weights, minimum score, Top-5/no-fill semantics and
3-point tie-break remain outside this module. No model can assign numeric scores,
overall quality, rank, Top-5 membership, Candidate Facts or product authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Callable, Mapping, Sequence

import requests

from src.search_intelligence.detail_semantics_grounding import locate_unique_evidence_span
from src.search_intelligence.llm_booster_policy import (
    BoosterStage,
    HARD_COST_CEILING_USD,
    MODEL_CONFIG,
)
from src.search_intelligence.origin_llm_adjudication import OPENAI_RESPONSES_URL
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    ProductV1RankingEvidence,
    RankingSignalReference,
)


FIT_FACTORS = ("profile_direction", "data_focus", "reliability_focus")
MODEL_STAGES = (
    BoosterStage.LUNA_MEDIUM,
    BoosterStage.TERRA_MEDIUM,
    BoosterStage.SOL_MEDIUM,
    BoosterStage.LUNA_MAX,
)
MAX_DETAIL_TEXT_CHARS = 16_000
MAX_HYPOTHESES = 6
MAX_EVIDENCE_CHARS = 900


@dataclass(frozen=True)
class _BoosterSignalRule:
    factor: str
    points: float
    pattern: re.Pattern[str]


BOOSTER_SIGNAL_RULES: Mapping[str, _BoosterSignalRule] = {
    "predictive_modeling_context": _BoosterSignalRule(
        factor="profile_direction",
        points=10.0,
        pattern=re.compile(
            r"\b(?:predictive\s+model(?:s|ing)?|model\s+training|train(?:ing)?\s+(?:ml\s+)?models?|model\s+inference)\b",
            re.IGNORECASE,
        ),
    ),
    "model_lifecycle_context": _BoosterSignalRule(
        factor="profile_direction",
        points=10.0,
        pattern=re.compile(
            r"\b(?:model\s+deployment|deploy(?:ing)?\s+(?:ml\s+)?models?|model\s+serving|model\s+monitoring)\b",
            re.IGNORECASE,
        ),
    ),
    "ingestion_orchestration_context": _BoosterSignalRule(
        factor="data_focus",
        points=15.0,
        pattern=re.compile(
            r"\b(?:data\s+ingestion|data\s+orchestration|orchestrat(?:e|ing|ion)\s+(?:data\s+)?workflows?|data\s+transformation\s+workflows?)\b",
            re.IGNORECASE,
        ),
    ),
    "streaming_data_context": _BoosterSignalRule(
        factor="data_focus",
        points=15.0,
        pattern=re.compile(
            r"\b(?:streaming\s+(?:data|workloads?|pipelines?)|event[- ]driven\s+data)\b",
            re.IGNORECASE,
        ),
    ),
    "resilience_context": _BoosterSignalRule(
        factor="reliability_focus",
        points=20.0,
        pattern=re.compile(
            r"\b(?:resilien(?:t|ce)|fault[- ]toleran(?:t|ce)|incident\s+recovery|disaster\s+recovery)\b",
            re.IGNORECASE,
        ),
    ),
    "availability_context": _BoosterSignalRule(
        factor="reliability_focus",
        points=20.0,
        pattern=re.compile(
            r"\b(?:high\s+availability|uptime|service\s+level\s+objectives?|\bSLOs?\b|\bSLIs?\b)\b",
            re.IGNORECASE,
        ),
    ),
}

SYSTEM_INSTRUCTIONS = """You are an evidence locator for an already-authoritative employer-origin job detail page.
For requested ranking fit factors, return only exact contiguous quotes from detail_text plus one allowed signal enum.
Never return a numeric score, overall score, rank, Top-5 decision, Candidate Fact, capability judgment or product
decision. Use only these signals: predictive_modeling_context, model_lifecycle_context,
ingestion_orchestration_context, streaming_data_context, resilience_context, availability_context. Omit a factor
when no exact supporting quote exists. Do not use employer prestige, title prestige, outside knowledge, salary,
years of experience or inferred seniority as ranking evidence.
"""

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]
]


@dataclass(frozen=True)
class RankingHypothesisObservation:
    status: str
    request_attempted: bool
    references: tuple[RankingSignalReference, ...]
    model: str | None = None
    response_id: str | None = None
    estimated_cost_usd: float = 0.0
    rationale: str = ""
    ranking_authority: bool = False
    product_authority: bool = False


@dataclass(frozen=True)
class RankingBoosterStageEvidence:
    stage: BoosterStage
    attempted: bool
    status: str
    reason_code: str
    provider_requests: int
    accepted_signals: tuple[str, ...] = ()
    hypothesis_fingerprint: str | None = None
    estimated_cost_usd: float = 0.0
    ranking_authority: bool = False
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        payload["accepted_signals"] = list(self.accepted_signals)
        return payload


@dataclass(frozen=True)
class ProductV1RankingBoosterExecution:
    deterministic_evidence: ProductV1RankingEvidence
    profile_direction_score: float
    data_focus_score: float
    reliability_focus_score: float
    evidence_quality_score: float
    evidence_references: tuple[RankingSignalReference, ...]
    requested_factors: tuple[str, ...]
    unresolved_factors: tuple[str, ...]
    stages: tuple[RankingBoosterStageEvidence, ...]
    provider_requests: int
    llm_requests: int
    tavily_requests: int = 0
    database_writes: int = 0
    ranking_writes: int = 0
    top5_writes: int = 0
    application_writes: int = 0
    product_writes: int = 0
    candidate_fact_authority: bool = False
    capability_fit_authority: bool = False
    ranking_authority: bool = False
    top5_authority: bool = False
    product_authority: bool = False

    @property
    def estimated_model_cost_usd(self) -> float:
        return sum(stage.estimated_cost_usd for stage in self.stages)

    def score_patch(self) -> dict[str, float]:
        return {
            "profile_direction_score": self.profile_direction_score,
            "data_focus_score": self.data_focus_score,
            "reliability_focus_score": self.reliability_focus_score,
            "evidence_quality_score": self.evidence_quality_score,
        }

    def to_json(self) -> dict[str, object]:
        return {
            **self.score_patch(),
            "deterministic_evidence": self.deterministic_evidence.canonical_payload(),
            "evidence_references": [reference.canonical_payload() for reference in self.evidence_references],
            "requested_factors": list(self.requested_factors),
            "unresolved_factors": list(self.unresolved_factors),
            "stages": [stage.to_json() for stage in self.stages],
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "tavily_requests": self.tavily_requests,
            "estimated_model_cost_usd": round(self.estimated_model_cost_usd, 8),
            "database_writes": self.database_writes,
            "ranking_writes": self.ranking_writes,
            "top5_writes": self.top5_writes,
            "application_writes": self.application_writes,
            "product_writes": self.product_writes,
            "candidate_fact_authority": self.candidate_fact_authority,
            "capability_fit_authority": self.capability_fit_authority,
            "ranking_authority": self.ranking_authority,
            "top5_authority": self.top5_authority,
            "product_authority": self.product_authority,
        }


def _transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, object],
    timeout_seconds: float,
) -> Mapping[str, object]:
    response = requests.post(url, headers=dict(headers), json=dict(payload), timeout=timeout_seconds)
    response.raise_for_status()
    decoded = response.json()
    if not isinstance(decoded, Mapping):
        raise ValueError("OpenAI response root must be an object")
    return decoded


def _extract_output_text(response: Mapping[str, object]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    output = response.get("output")
    if not isinstance(output, list):
        raise ValueError("response contains no output array")
    parts: list[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, Mapping) and block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(str(block["text"]))
    if not parts:
        raise ValueError("response contains no output_text")
    return "".join(parts)


def _estimated_cost(model: str, usage: Mapping[str, object] | None) -> float:
    prices = MODEL_PRICES_USD_PER_MILLION.get(model)
    if prices is None or usage is None:
        return 0.0
    input_price, output_price = prices
    return (
        int(usage.get("input_tokens") or 0) * input_price / 1_000_000
        + int(usage.get("output_tokens") or 0) * output_price / 1_000_000
    )


def _safe_message(exc: BaseException) -> str:
    text = " ".join(str(exc).split()) or type(exc).__name__
    return re.sub(r"Bearer\s+\S+", "Bearer ***", text, flags=re.IGNORECASE)[:500]


def _requested_factors(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        factor = str(value or "").strip().lower()
        if factor not in FIT_FACTORS:
            raise ValueError(f"unsupported ranking booster factor: {factor or '<empty>'}")
        if factor not in seen:
            result.append(factor)
            seen.add(factor)
    if not result:
        raise ValueError("at least one ranking booster factor is required")
    return tuple(result)


def _schema(requested: tuple[str, ...]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["hypotheses", "rationale"],
        "properties": {
            "hypotheses": {
                "type": "array",
                "maxItems": MAX_HYPOTHESES,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["factor", "signal", "evidence"],
                    "properties": {
                        "factor": {"type": "string", "enum": list(requested)},
                        "signal": {"type": "string", "enum": sorted(BOOSTER_SIGNAL_RULES)},
                        "evidence": {"type": "string", "minLength": 1, "maxLength": MAX_EVIDENCE_CHARS},
                    },
                },
            },
            "rationale": {"type": "string", "maxLength": 600},
        },
    }


def _validated_reference(
    *,
    factor: str,
    signal: str,
    evidence_quote: str,
    detail_text: str,
) -> RankingSignalReference:
    if signal not in BOOSTER_SIGNAL_RULES:
        raise ValueError(f"unsupported ranking booster signal: {signal}")
    rule = BOOSTER_SIGNAL_RULES[signal]
    if rule.factor != factor:
        raise ValueError(f"ranking booster signal/factor mismatch: {signal}/{factor}")
    if not rule.pattern.search(evidence_quote):
        raise ValueError(f"quote does not deterministically support ranking signal: {signal}")
    start, end = locate_unique_evidence_span(detail_text=detail_text, evidence=evidence_quote)
    return RankingSignalReference(
        factor=factor,
        signal=signal,
        source_surface="description",
        evidence=evidence_quote,
        span_start=start,
        span_end=end,
        points=rule.points,
    )


def request_product_v1_ranking_hypotheses(
    *,
    company_name: str,
    detail_url: str,
    title: str,
    detail_text: str,
    requested_factors: Sequence[str],
    api_key: str,
    model: str,
    reasoning_effort: str = "medium",
    max_output_tokens: int = 600,
    timeout_seconds: float = 60.0,
    transport: Transport = _transport,
) -> RankingHypothesisObservation:
    """Request exact ranking-factor quotes and deterministically validate them."""

    requested = _requested_factors(requested_factors)
    bounded_text = str(detail_text or "")[:MAX_DETAIL_TEXT_CHARS]
    if not bounded_text.strip():
        raise ValueError("bounded detail text must be non-empty")
    packet = {
        "company_name": str(company_name or "").strip(),
        "detail_url": str(detail_url or "").strip(),
        "title": str(title or "").strip(),
        "requested_factors": list(requested),
        "detail_text": bounded_text,
        "authority_constraints": {
            "exact_quote_only": True,
            "numeric_scores_from_model": False,
            "overall_score_from_model": False,
            "rank_from_model": False,
            "top5_from_model": False,
            "candidate_facts_allowed": False,
            "product_authority": False,
        },
    }
    packet_json = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    packet_sha = hashlib.sha256(packet_json.encode("utf-8")).hexdigest()
    payload: dict[str, object] = {
        "model": model,
        "store": False,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_INSTRUCTIONS}]},
            {"role": "user", "content": [{"type": "input_text", "text": packet_json}]},
        ],
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "product_v1_ranking_evidence_hypotheses",
                "strict": True,
                "schema": _schema(requested),
            },
        },
    }

    try:
        response = transport(
            OPENAI_RESPONSES_URL,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload,
            timeout_seconds,
        )
        decoded = json.loads(_extract_output_text(response))
        if not isinstance(decoded, Mapping):
            raise ValueError("ranking hypothesis response must be an object")
        raw = decoded.get("hypotheses")
        if not isinstance(raw, list) or len(raw) > MAX_HYPOTHESES:
            raise ValueError("ranking response requires bounded hypotheses array")
        references: list[RankingSignalReference] = []
        seen: set[tuple[str, str]] = set()
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("ranking hypothesis must be an object")
            factor = str(item.get("factor") or "").strip().lower()
            signal = str(item.get("signal") or "").strip()
            evidence_quote = str(item.get("evidence") or "")
            if factor not in requested:
                raise ValueError(f"unrequested ranking factor returned: {factor or '<empty>'}")
            if not evidence_quote or len(evidence_quote) > MAX_EVIDENCE_CHARS:
                raise ValueError("ranking evidence is empty or oversized")
            key = (factor, signal)
            if key in seen:
                raise ValueError(f"duplicate ranking signal returned: {factor}/{signal}")
            seen.add(key)
            references.append(
                _validated_reference(
                    factor=factor,
                    signal=signal,
                    evidence_quote=evidence_quote,
                    detail_text=bounded_text,
                )
            )
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        return RankingHypothesisObservation(
            status="completed",
            request_attempted=True,
            references=tuple(references),
            model=str(response.get("model") or model),
            response_id=str(response.get("id") or "") or None,
            estimated_cost_usd=_estimated_cost(model, usage_map),
            rationale=f"packet_sha256={packet_sha}; {str(decoded.get('rationale') or '').strip()[:600]}",
        )
    except (json.JSONDecodeError, requests.RequestException, TypeError, ValueError) as exc:
        return RankingHypothesisObservation(
            status="failed_closed",
            request_attempted=True,
            references=(),
            model=model,
            estimated_cost_usd=0.0,
            rationale=f"packet_sha256={packet_sha}; failure={type(exc).__name__}: {_safe_message(exc)}"[:700],
        )


def _factor_scores(evidence: ProductV1RankingEvidence) -> dict[str, float]:
    return {
        "profile_direction": evidence.profile_direction_score,
        "data_focus": evidence.data_focus_score,
        "reliability_focus": evidence.reliability_focus_score,
    }


def _weak_factors(scores: Mapping[str, float]) -> tuple[str, ...]:
    return tuple(factor for factor in FIT_FACTORS if float(scores[factor]) < 100.0)


def _fingerprint(references: Sequence[RankingSignalReference]) -> str:
    payload = [
        reference.canonical_payload()
        for reference in sorted(
            references,
            key=lambda item: (item.factor, item.signal, item.span_start, item.span_end),
        )
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


ModelCallback = Callable[[BoosterStage, tuple[str, ...]], RankingHypothesisObservation]


def execute_product_v1_ranking_booster(
    *,
    deterministic_evidence: ProductV1RankingEvidence,
    model: ModelCallback,
) -> ProductV1RankingBoosterExecution:
    """Apply only fixed deterministic signal points from validated model quotes."""

    scores = _factor_scores(deterministic_evidence)
    requested = _weak_factors(scores)
    references = list(deterministic_evidence.references)
    seen_signals = {(reference.factor, reference.signal) for reference in references}
    seen_fingerprints: set[str] = set()
    stages: list[RankingBoosterStageEvidence] = [
        RankingBoosterStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=True,
            status="resolved" if not requested else "residual",
            reason_code="deterministic_ranking_evidence_first",
            provider_requests=0,
        ),
        RankingBoosterStageEvidence(
            stage=BoosterStage.TAVILY,
            attempted=False,
            status="skipped",
            reason_code="external_search_not_indicated_same_detail_ranking",
            provider_requests=0,
        ),
    ]
    provider_requests = 0

    for stage in MODEL_STAGES:
        unresolved = _weak_factors(scores)
        if not unresolved:
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=False,
                    status="skipped",
                    reason_code="ranking_fit_evidence_saturated",
                    provider_requests=0,
                )
            )
            continue
        observation = model(stage, unresolved)
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        cost = float(observation.estimated_cost_usd or 0.0)
        if observation.ranking_authority or observation.product_authority:
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_ranking_or_product_authority_claim_rejected",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break
        if observation.status == "failed_closed":
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="provider_hypothesis_failed_closed",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break
        if cost < 0 or cost > HARD_COST_CEILING_USD[stage]:
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_cost_ceiling_exceeded",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break
        if any(reference.factor not in unresolved for reference in observation.references):
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_broadened_requested_factors",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            break
        if not observation.references:
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="unresolved",
                    reason_code="no_grounded_ranking_evidence",
                    provider_requests=request_count,
                    estimated_cost_usd=cost,
                )
            )
            continue

        fingerprint = _fingerprint(observation.references)
        if fingerprint in seen_fingerprints:
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="unresolved",
                    reason_code="repeated_ranking_hypothesis",
                    provider_requests=request_count,
                    hypothesis_fingerprint=fingerprint,
                    estimated_cost_usd=cost,
                )
            )
            continue
        seen_fingerprints.add(fingerprint)

        accepted: list[RankingSignalReference] = []
        for reference in observation.references:
            key = (reference.factor, reference.signal)
            if key in seen_signals:
                continue
            rule = BOOSTER_SIGNAL_RULES.get(reference.signal)
            if rule is None or rule.factor != reference.factor or reference.points != rule.points:
                continue
            seen_signals.add(key)
            scores[reference.factor] = min(100.0, round(scores[reference.factor] + rule.points, 2))
            accepted.append(reference)
            references.append(reference)

        if not accepted:
            stages.append(
                RankingBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="unresolved",
                    reason_code="no_new_deterministic_ranking_signal",
                    provider_requests=request_count,
                    hypothesis_fingerprint=fingerprint,
                    estimated_cost_usd=cost,
                )
            )
            continue
        stages.append(
            RankingBoosterStageEvidence(
                stage=stage,
                attempted=observation.request_attempted,
                status="progressed",
                reason_code="fixed_points_from_validated_ranking_signal",
                provider_requests=request_count,
                accepted_signals=tuple(sorted(reference.signal for reference in accepted)),
                hypothesis_fingerprint=fingerprint,
                estimated_cost_usd=cost,
            )
        )

    stages.append(
        RankingBoosterStageEvidence(
            stage=BoosterStage.DEEP_EVIDENCE,
            attempted=False,
            status="skipped",
            reason_code="deep_external_evidence_not_activated_for_same_page_ranking",
            provider_requests=0,
        )
    )
    return ProductV1RankingBoosterExecution(
        deterministic_evidence=deterministic_evidence,
        profile_direction_score=scores["profile_direction"],
        data_focus_score=scores["data_focus"],
        reliability_focus_score=scores["reliability_focus"],
        evidence_quality_score=deterministic_evidence.evidence_quality_score,
        evidence_references=tuple(references),
        requested_factors=requested,
        unresolved_factors=_weak_factors(scores),
        stages=tuple(stages),
        provider_requests=provider_requests,
        llm_requests=provider_requests,
    )


def openai_ranking_model_callback(
    *,
    company_name: str,
    detail_url: str,
    title: str,
    detail_text: str,
    api_key: str,
    transport: Transport = _transport,
) -> ModelCallback:
    def callback(stage: BoosterStage, requested: tuple[str, ...]) -> RankingHypothesisObservation:
        model, reasoning_effort = MODEL_CONFIG[stage]
        return request_product_v1_ranking_hypotheses(
            company_name=company_name,
            detail_url=detail_url,
            title=title,
            detail_text=detail_text,
            requested_factors=requested,
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort,
            transport=transport,
        )

    return callback


__all__ = [
    "BOOSTER_SIGNAL_RULES",
    "RankingHypothesisObservation",
    "ProductV1RankingBoosterExecution",
    "execute_product_v1_ranking_booster",
    "openai_ranking_model_callback",
    "request_product_v1_ranking_hypotheses",
]
