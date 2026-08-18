"""Bounded AI booster for unresolved Product V1 assessment evidence.

The deterministic assessment-evidence core always runs first. For remaining
same-detail gaps the canonical Luna -> Terra -> Sol -> Luna-max model sequence
may identify exact source quotes. Models do not return canonical assessment
values: deterministic code re-parses every exact quote before accepting it.

Tavily and deep external evidence are intentionally not activated for ordinary
same-page assessment ambiguity. Candidate Facts, capability fit, hard-filter,
ranking, persistence and product authority remain outside this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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
from src.search_intelligence.product_v1_assessment_evidence import (
    AssessmentEvidenceReference,
    ProductV1AssessmentEvidence,
    extract_product_v1_assessment_evidence,
)


ASSESSMENT_BOOSTER_FIELDS = (
    "employment_type",
    "required_languages",
    "weekly_hours",
    "work_model",
    "requirements_seniority",
)
MODEL_STAGES = (
    BoosterStage.LUNA_MEDIUM,
    BoosterStage.TERRA_MEDIUM,
    BoosterStage.SOL_MEDIUM,
    BoosterStage.LUNA_MAX,
)
MAX_DETAIL_TEXT_CHARS = 16_000
MAX_HYPOTHESES = 8
MAX_EVIDENCE_CHARS = 1_200

SYSTEM_INSTRUCTIONS = """You locate exact evidence on one already-authoritative employer-origin job detail page.
Return hypotheses only for the explicitly requested assessment fields: employment_type, required_languages,
weekly_hours, work_model, requirements_seniority. For each hypothesis, quote one exact contiguous substring
from detail_text that directly states the requested fact. Do not return or infer canonical values. Do not infer
seniority from years of experience, extensive experience, responsibility, salary or job importance. Home Office
alone is not a work-model classification. Omit a field when no exact supporting quote exists. Never use outside
knowledge, another URL, Candidate Facts, capability fit, ranking, gate pass or product authority.
"""

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]
]


@dataclass(frozen=True)
class AssessmentHypothesisObservation:
    status: str
    request_attempted: bool
    field_values: Mapping[str, object]
    evidence_references: tuple[AssessmentEvidenceReference, ...]
    model: str | None = None
    response_id: str | None = None
    estimated_cost_usd: float = 0.0
    rationale: str = ""
    product_authority: bool = False


@dataclass(frozen=True)
class AssessmentBoosterStageEvidence:
    stage: BoosterStage
    attempted: bool
    status: str
    reason_code: str
    provider_requests: int
    accepted_fields: tuple[str, ...] = ()
    evidence_reference_count: int = 0
    hypothesis_fingerprint: str | None = None
    progressed: bool = False
    estimated_cost_usd: float = 0.0
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        payload["accepted_fields"] = list(self.accepted_fields)
        return payload


@dataclass(frozen=True)
class ProductV1AssessmentBoosterExecution:
    source_url: str
    deterministic_evidence: ProductV1AssessmentEvidence
    assessment_patch: Mapping[str, object]
    evidence_references: tuple[AssessmentEvidenceReference, ...]
    requested_fields: tuple[str, ...]
    unresolved_fields: tuple[str, ...]
    stages: tuple[AssessmentBoosterStageEvidence, ...]
    provider_requests: int
    llm_requests: int
    tavily_requests: int = 0
    database_writes: int = 0
    hard_filter_writes: int = 0
    ranking_writes: int = 0
    application_writes: int = 0
    product_writes: int = 0
    candidate_fact_authority: bool = False
    capability_fit_authority: bool = False
    hard_filter_authority: bool = False
    ranking_authority: bool = False
    product_authority: bool = False

    @property
    def estimated_model_cost_usd(self) -> float:
        return sum(stage.estimated_cost_usd for stage in self.stages)

    def to_json(self) -> dict[str, object]:
        return {
            "source_url": self.source_url,
            "deterministic_evidence": self.deterministic_evidence.canonical_payload(),
            "assessment_patch": dict(self.assessment_patch),
            "evidence_references": [
                reference.canonical_payload() for reference in self.evidence_references
            ],
            "requested_fields": list(self.requested_fields),
            "unresolved_fields": list(self.unresolved_fields),
            "stages": [stage.to_json() for stage in self.stages],
            "provider_requests": self.provider_requests,
            "llm_requests": self.llm_requests,
            "tavily_requests": self.tavily_requests,
            "estimated_model_cost_usd": round(self.estimated_model_cost_usd, 8),
            "database_writes": self.database_writes,
            "hard_filter_writes": self.hard_filter_writes,
            "ranking_writes": self.ranking_writes,
            "application_writes": self.application_writes,
            "product_writes": self.product_writes,
            "candidate_fact_authority": self.candidate_fact_authority,
            "capability_fit_authority": self.capability_fit_authority,
            "hard_filter_authority": self.hard_filter_authority,
            "ranking_authority": self.ranking_authority,
            "product_authority": self.product_authority,
        }


def _transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, object],
    timeout_seconds: float,
) -> Mapping[str, object]:
    response = requests.post(
        url,
        headers=dict(headers),
        json=dict(payload),
        timeout=timeout_seconds,
    )
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
            if (
                isinstance(block, Mapping)
                and block.get("type") == "output_text"
                and isinstance(block.get("text"), str)
            ):
                parts.append(str(block["text"]))
    if not parts:
        raise ValueError("response contains no output_text")
    return "".join(parts)


def _safe_message(exc: BaseException) -> str:
    text = " ".join(str(exc).split()) or type(exc).__name__
    return re.sub(r"Bearer\s+\S+", "Bearer ***", text, flags=re.IGNORECASE)[:500]


def _estimated_cost(model: str, usage: Mapping[str, object] | None) -> float:
    prices = MODEL_PRICES_USD_PER_MILLION.get(model)
    if prices is None or usage is None:
        return 0.0
    input_price, output_price = prices
    return (
        int(usage.get("input_tokens") or 0) * input_price / 1_000_000
        + int(usage.get("output_tokens") or 0) * output_price / 1_000_000
    )


def _requested_fields(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        field = str(value or "").strip().lower()
        if field not in ASSESSMENT_BOOSTER_FIELDS:
            raise ValueError(f"unsupported assessment booster field: {field or '<empty>'}")
        if field not in seen:
            seen.add(field)
            result.append(field)
    if not result:
        raise ValueError("at least one assessment booster field is required")
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
                    "required": ["field", "evidence"],
                    "properties": {
                        "field": {"type": "string", "enum": list(requested)},
                        "evidence": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": MAX_EVIDENCE_CHARS,
                        },
                    },
                },
            },
            "rationale": {"type": "string", "maxLength": 600},
        },
    }


def _field_value(
    field: str, evidence: ProductV1AssessmentEvidence
) -> object | None:
    if field == "employment_type":
        return evidence.employment_type if evidence.employment_type != "unknown" else None
    if field == "required_languages":
        return evidence.required_languages or None
    if field == "weekly_hours":
        if evidence.weekly_hours_min is None and evidence.weekly_hours_max is None:
            return None
        return (evidence.weekly_hours_min, evidence.weekly_hours_max)
    if field == "work_model":
        return evidence.work_model if evidence.work_model != "unknown" else None
    if field == "requirements_seniority":
        return (
            evidence.requirements_seniority
            if evidence.requirements_seniority != "unknown"
            else None
        )
    raise ValueError(f"unsupported assessment booster field: {field}")


def _translate_references(
    *,
    field: str,
    local: ProductV1AssessmentEvidence,
    global_start: int,
) -> tuple[AssessmentEvidenceReference, ...]:
    references: list[AssessmentEvidenceReference] = []
    for reference in local.references:
        if reference.field != field:
            continue
        references.append(
            replace(
                reference,
                span_start=global_start + reference.span_start,
                span_end=global_start + reference.span_end,
            )
        )
    return tuple(references)


def _verified_payload(
    *,
    detail_url: str,
    detail_text: str,
    title: str,
    decoded: Mapping[str, object],
    requested: tuple[str, ...],
) -> tuple[dict[str, object], tuple[AssessmentEvidenceReference, ...]]:
    raw = decoded.get("hypotheses")
    if not isinstance(raw, list):
        raise ValueError("assessment response requires hypotheses array")
    if len(raw) > MAX_HYPOTHESES:
        raise ValueError("assessment response exceeds hypothesis bound")

    requested_set = set(requested)
    values: dict[str, object] = {}
    references: list[AssessmentEvidenceReference] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("assessment hypothesis must be an object")
        field = str(item.get("field") or "").strip().lower()
        if field not in requested_set:
            raise ValueError(f"unrequested assessment field returned: {field or '<empty>'}")
        if field in values:
            raise ValueError(f"duplicate assessment field returned: {field}")
        evidence_quote = str(item.get("evidence") or "")
        if not evidence_quote or len(evidence_quote) > MAX_EVIDENCE_CHARS:
            raise ValueError("assessment evidence is empty or oversized")
        global_start, _global_end = locate_unique_evidence_span(
            detail_text=detail_text,
            evidence=evidence_quote,
        )
        local = extract_product_v1_assessment_evidence(
            description=evidence_quote,
            title=title,
            source_url=detail_url,
        )
        if field in local.conflicted_fields:
            raise ValueError(f"assessment evidence is contradictory for field: {field}")
        value = _field_value(field, local)
        if value is None:
            raise ValueError(
                f"model quote does not deterministically support assessment field: {field}"
            )
        translated = _translate_references(
            field=field,
            local=local,
            global_start=global_start,
        )
        if not translated:
            raise ValueError(f"deterministic evidence reference missing for field: {field}")
        values[field] = value
        references.extend(translated)
    return values, tuple(references)


def request_product_v1_assessment_hypotheses(
    *,
    company_name: str,
    detail_url: str,
    title: str,
    detail_text: str,
    requested_fields: Sequence[str],
    api_key: str,
    model: str,
    reasoning_effort: str = "medium",
    max_output_tokens: int = 600,
    timeout_seconds: float = 60.0,
    transport: Transport = _transport,
) -> AssessmentHypothesisObservation:
    """Request exact evidence quotes and deterministically validate them."""

    requested = _requested_fields(requested_fields)
    bounded_text = str(detail_text or "")[:MAX_DETAIL_TEXT_CHARS]
    if not bounded_text.strip():
        raise ValueError("bounded detail text must be non-empty")
    packet = {
        "company_name": str(company_name or "").strip(),
        "detail_url": str(detail_url or "").strip(),
        "title": str(title or "").strip(),
        "requested_fields": list(requested),
        "detail_text": bounded_text,
        "authority_constraints": {
            "exact_quote_only": True,
            "canonical_value_from_model": False,
            "deterministic_reparse_required": True,
            "same_detail_url_only": True,
            "candidate_facts_allowed": False,
            "capability_fit_authority": False,
            "hard_filter_authority": False,
            "ranking_authority": False,
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
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_INSTRUCTIONS}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": packet_json}],
            },
        ],
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "product_v1_assessment_evidence_hypotheses",
                "strict": True,
                "schema": _schema(requested),
            },
        },
    }

    try:
        response = transport(
            OPENAI_RESPONSES_URL,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload,
            timeout_seconds,
        )
        decoded = json.loads(_extract_output_text(response))
        if not isinstance(decoded, Mapping):
            raise ValueError("assessment hypothesis response must be an object")
        values, references = _verified_payload(
            detail_url=detail_url,
            detail_text=bounded_text,
            title=title,
            decoded=decoded,
            requested=requested,
        )
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        rationale = str(decoded.get("rationale") or "").strip()[:600]
        return AssessmentHypothesisObservation(
            status="completed",
            request_attempted=True,
            field_values=values,
            evidence_references=references,
            model=str(response.get("model") or model),
            response_id=str(response.get("id") or "") or None,
            estimated_cost_usd=_estimated_cost(model, usage_map),
            rationale=f"packet_sha256={packet_sha}; {rationale}"[:700],
        )
    except (
        json.JSONDecodeError,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        return AssessmentHypothesisObservation(
            status="failed_closed",
            request_attempted=True,
            field_values={},
            evidence_references=(),
            model=model,
            response_id=None,
            estimated_cost_usd=0.0,
            rationale=(
                f"packet_sha256={packet_sha}; failure={type(exc).__name__}: "
                f"{_safe_message(exc)}"
            )[:700],
        )


def _unresolved_booster_fields(patch: Mapping[str, object]) -> tuple[str, ...]:
    unresolved: list[str] = []
    if patch.get("employment_evidence_status") != "observed":
        unresolved.append("employment_type")
    if patch.get("language_evidence_status") != "observed":
        unresolved.append("required_languages")
    if patch.get("weekly_hours_evidence_status") != "observed":
        unresolved.append("weekly_hours")
    if patch.get("work_model") == "unknown":
        unresolved.append("work_model")
    if patch.get("seniority_evidence_status") != "observed":
        unresolved.append("requirements_seniority")
    return tuple(unresolved)


def _apply_values(patch: dict[str, object], values: Mapping[str, object]) -> None:
    for field, value in values.items():
        if field == "employment_type":
            patch["employment_type"] = value
            patch["employment_evidence_status"] = "observed"
        elif field == "required_languages":
            patch["required_languages"] = list(value) if isinstance(value, tuple) else value
            patch["language_evidence_status"] = "observed"
        elif field == "weekly_hours":
            minimum, maximum = value
            patch["weekly_hours_min"] = minimum
            patch["weekly_hours_max"] = maximum
            patch["weekly_hours_evidence_status"] = "observed"
        elif field == "work_model":
            patch["work_model"] = value
        elif field == "requirements_seniority":
            patch["requirements_seniority"] = value
            patch["seniority_evidence_status"] = "observed"
        else:
            raise ValueError(f"unsupported assessment field update: {field}")


def _hypothesis_fingerprint(observation: AssessmentHypothesisObservation) -> str:
    payload = {
        "field_values": {
            key: observation.field_values[key] for key in sorted(observation.field_values)
        },
        "references": [
            reference.canonical_payload()
            for reference in sorted(
                observation.evidence_references,
                key=lambda item: (item.field, item.span_start, item.span_end),
            )
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=list)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


ModelCallback = Callable[
    [BoosterStage, tuple[str, ...]], AssessmentHypothesisObservation
]


def execute_product_v1_assessment_booster(
    *,
    deterministic_evidence: ProductV1AssessmentEvidence,
    model: ModelCallback,
) -> ProductV1AssessmentBoosterExecution:
    """Run the bounded same-detail model cascade after deterministic extraction."""

    patch = dict(deterministic_evidence.assessment_patch())
    references = list(deterministic_evidence.references)
    requested = _unresolved_booster_fields(patch)
    stages: list[AssessmentBoosterStageEvidence] = []
    provider_requests = 0
    seen_fingerprints: set[str] = set()

    stages.append(
        AssessmentBoosterStageEvidence(
            stage=BoosterStage.DETERMINISTIC,
            attempted=True,
            status="resolved" if not requested else "residual",
            reason_code="deterministic_assessment_evidence_first",
            provider_requests=0,
            accepted_fields=tuple(
                field for field in ASSESSMENT_BOOSTER_FIELDS if field not in requested
            ),
            evidence_reference_count=len(references),
            progressed=bool(set(ASSESSMENT_BOOSTER_FIELDS).difference(requested)),
        )
    )
    stages.append(
        AssessmentBoosterStageEvidence(
            stage=BoosterStage.TAVILY,
            attempted=False,
            status="skipped",
            reason_code="external_search_not_indicated_same_detail_assessment",
            provider_requests=0,
        )
    )

    for stage in MODEL_STAGES:
        unresolved = _unresolved_booster_fields(patch)
        if not unresolved:
            stages.append(
                AssessmentBoosterStageEvidence(
                    stage=stage,
                    attempted=False,
                    status="skipped",
                    reason_code="assessment_evidence_resolved",
                    provider_requests=0,
                )
            )
            continue

        observation = model(stage, unresolved)
        request_count = int(observation.request_attempted)
        provider_requests += request_count
        estimated_cost = float(observation.estimated_cost_usd or 0.0)
        ceiling = HARD_COST_CEILING_USD[stage]
        if observation.product_authority:
            stages.append(
                AssessmentBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_product_authority_claim_rejected",
                    provider_requests=request_count,
                    estimated_cost_usd=estimated_cost,
                )
            )
            break
        if observation.status == "failed_closed":
            stages.append(
                AssessmentBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="provider_hypothesis_failed_closed",
                    provider_requests=request_count,
                    estimated_cost_usd=estimated_cost,
                )
            )
            break
        if estimated_cost < 0 or estimated_cost > ceiling:
            stages.append(
                AssessmentBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_cost_ceiling_exceeded",
                    provider_requests=request_count,
                    estimated_cost_usd=estimated_cost,
                )
            )
            break

        returned = set(observation.field_values)
        if returned.difference(unresolved):
            stages.append(
                AssessmentBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="failed_closed",
                    reason_code="model_broadened_requested_fields",
                    provider_requests=request_count,
                    estimated_cost_usd=estimated_cost,
                )
            )
            break
        if not observation.field_values:
            stages.append(
                AssessmentBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="unresolved",
                    reason_code="no_grounded_assessment_evidence",
                    provider_requests=request_count,
                    estimated_cost_usd=estimated_cost,
                )
            )
            continue

        fingerprint = _hypothesis_fingerprint(observation)
        if fingerprint in seen_fingerprints:
            stages.append(
                AssessmentBoosterStageEvidence(
                    stage=stage,
                    attempted=observation.request_attempted,
                    status="unresolved",
                    reason_code="repeated_assessment_hypothesis",
                    provider_requests=request_count,
                    hypothesis_fingerprint=fingerprint,
                    estimated_cost_usd=estimated_cost,
                )
            )
            continue
        seen_fingerprints.add(fingerprint)

        _apply_values(patch, observation.field_values)
        references.extend(observation.evidence_references)
        stages.append(
            AssessmentBoosterStageEvidence(
                stage=stage,
                attempted=observation.request_attempted,
                status="progressed",
                reason_code="deterministically_grounded_assessment_evidence",
                provider_requests=request_count,
                accepted_fields=tuple(sorted(observation.field_values)),
                evidence_reference_count=len(observation.evidence_references),
                hypothesis_fingerprint=fingerprint,
                progressed=True,
                estimated_cost_usd=estimated_cost,
            )
        )

    stages.append(
        AssessmentBoosterStageEvidence(
            stage=BoosterStage.DEEP_EVIDENCE,
            attempted=False,
            status="skipped",
            reason_code="deep_external_evidence_not_activated_for_same_page_assessment",
            provider_requests=0,
        )
    )
    unresolved = _unresolved_booster_fields(patch)
    return ProductV1AssessmentBoosterExecution(
        source_url=deterministic_evidence.source_url,
        deterministic_evidence=deterministic_evidence,
        assessment_patch=patch,
        evidence_references=tuple(references),
        requested_fields=requested,
        unresolved_fields=unresolved,
        stages=tuple(stages),
        provider_requests=provider_requests,
        llm_requests=provider_requests,
    )


def openai_assessment_model_callback(
    *,
    company_name: str,
    detail_url: str,
    title: str,
    detail_text: str,
    api_key: str,
    transport: Transport = _transport,
) -> ModelCallback:
    """Bind the canonical model campaign to the assessment evidence provider."""

    def callback(
        stage: BoosterStage, requested: tuple[str, ...]
    ) -> AssessmentHypothesisObservation:
        model, reasoning_effort = MODEL_CONFIG[stage]
        return request_product_v1_assessment_hypotheses(
            company_name=company_name,
            detail_url=detail_url,
            title=title,
            detail_text=detail_text,
            requested_fields=requested,
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort,
            transport=transport,
        )

    return callback


__all__ = [
    "ASSESSMENT_BOOSTER_FIELDS",
    "AssessmentHypothesisObservation",
    "ProductV1AssessmentBoosterExecution",
    "execute_product_v1_assessment_booster",
    "openai_assessment_model_callback",
    "request_product_v1_assessment_hypotheses",
]
