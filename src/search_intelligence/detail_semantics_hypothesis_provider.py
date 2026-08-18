"""Bounded OpenAI provider for Detail Semantics evidence hypotheses.

The provider receives only already-bounded public detail-page text and may return
hypotheses for an explicit requested semantic-field subset. Every returned field
must carry an exact evidence substring and an observed source value from that same
bounded text. Python character offsets are computed and validated deterministically
after the model response; ambiguous repeated evidence fails closed. Canonical
semantic values are derived only by deterministic field normalization after the
source value has been grounded.

Provider output has no semantic, gate, product, lifecycle, ranking or write
authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Callable, Mapping, Sequence

import requests

from src.search_intelligence.detail_semantics_booster_execution import (
    DetailSemanticsHypothesisObservation,
)
from src.search_intelligence.detail_semantics_gap import (
    SEMANTIC_FIELD_NAMES,
    SemanticEvidenceReference,
)
from src.search_intelligence.detail_semantics_grounding import locate_unique_evidence_span
from src.search_intelligence.detail_semantics_normalization import (
    normalize_detail_semantic_value,
)
from src.search_intelligence.origin_llm_adjudication import OPENAI_RESPONSES_URL
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]
]

MAX_DETAIL_TEXT_CHARS = 16_000
MAX_HYPOTHESES = 12
MAX_VALUE_CHARS = 300
MAX_EVIDENCE_CHARS = 1_200

SYSTEM_INSTRUCTIONS = """You extract bounded semantic evidence from one already-supported public job-detail page.
Return hypotheses only for the explicitly requested fields: role, seniority, skills, location, remote.
Every hypothesis must quote an exact contiguous substring from the supplied detail_text and copy the
observed_value exactly from that quoted evidence. Do not canonicalize, translate, generalize or infer the
observed_value. Do not calculate or return character offsets; deterministic code locates the exact quote
and then derives the canonical field value from the grounded observed source phrase. Use one hypothesis
for role, seniority, location or remote. Skills may have multiple hypotheses, one per skill. Omit any field
that cannot be supported by an exact quote. Years of experience are not a seniority label. Never infer from
outside knowledge, never use another URL, never claim relevance, gate pass or product authority, and never
invent evidence.
"""


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
    text = re.sub(r"Bearer\s+\S+", "Bearer ***", text, flags=re.IGNORECASE)
    return text[:500]


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
        if field not in SEMANTIC_FIELD_NAMES:
            raise ValueError(f"unsupported requested semantic field: {field or '<empty>'}")
        if field not in seen:
            seen.add(field)
            result.append(field)
    if not result:
        raise ValueError("at least one requested semantic field is required")
    return tuple(result)


def _schema(requested_fields: tuple[str, ...]) -> dict[str, object]:
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
                    "required": ["field", "observed_value", "evidence"],
                    "properties": {
                        "field": {"type": "string", "enum": list(requested_fields)},
                        "observed_value": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": MAX_VALUE_CHARS,
                        },
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


def _verified_observation_payload(
    *,
    detail_url: str,
    detail_text: str,
    decoded: Mapping[str, object],
    requested_fields: tuple[str, ...],
) -> tuple[dict[str, object], tuple[SemanticEvidenceReference, ...]]:
    raw_hypotheses = decoded.get("hypotheses")
    if not isinstance(raw_hypotheses, list):
        raise ValueError("Detail Semantics response requires hypotheses array")
    if len(raw_hypotheses) > MAX_HYPOTHESES:
        raise ValueError("Detail Semantics response exceeds hypothesis bound")

    scalar_fields: dict[str, str] = {}
    skill_values: list[str] = []
    references: list[SemanticEvidenceReference] = []
    requested = set(requested_fields)

    for item in raw_hypotheses:
        if not isinstance(item, Mapping):
            raise ValueError("Detail Semantics hypothesis must be an object")
        field = str(item.get("field") or "").strip().lower()
        if field not in requested:
            raise ValueError(f"unrequested semantic field returned: {field or '<empty>'}")
        observed_value = str(item.get("observed_value") or "").strip()
        evidence = str(item.get("evidence") or "")
        if not observed_value or len(observed_value) > MAX_VALUE_CHARS:
            raise ValueError("semantic observed source value is empty or oversized")
        if not evidence or len(evidence) > MAX_EVIDENCE_CHARS:
            raise ValueError("semantic evidence is empty or oversized")
        if observed_value.casefold() not in evidence.casefold():
            raise ValueError("semantic observed source value must occur verbatim inside its evidence")

        span_start, span_end = locate_unique_evidence_span(
            detail_text=detail_text,
            evidence=evidence,
        )
        canonical_value = normalize_detail_semantic_value(
            field=field,
            observed_value=observed_value,
        )

        if field == "skills":
            if canonical_value not in skill_values:
                skill_values.append(canonical_value)
        elif field in scalar_fields:
            raise ValueError(f"duplicate scalar semantic field returned: {field}")
        else:
            scalar_fields[field] = canonical_value

        references.append(
            SemanticEvidenceReference(
                field=field,
                source_url=detail_url,
                evidence=evidence,
                value=observed_value,
                span_start=span_start,
                span_end=span_end,
            )
        )

    semantic_fields: dict[str, object] = dict(scalar_fields)
    if skill_values:
        semantic_fields["skills"] = tuple(skill_values)
    return semantic_fields, tuple(references)


def request_detail_semantics_hypotheses(
    *,
    company_name: str,
    detail_url: str,
    detail_text: str,
    requested_semantic_fields: Sequence[str],
    current_semantic_fields: Mapping[str, object],
    api_key: str,
    model: str,
    reasoning_effort: str = "medium",
    max_output_tokens: int = 700,
    timeout_seconds: float = 60.0,
    transport: Transport = _transport,
) -> DetailSemanticsHypothesisObservation:
    """Request quote-grounded semantic hypotheses with zero authority."""

    requested = _requested_fields(requested_semantic_fields)
    bounded_text = str(detail_text or "")[:MAX_DETAIL_TEXT_CHARS]
    if not bounded_text.strip():
        raise ValueError("bounded detail text must be non-empty")

    packet = {
        "company_name": str(company_name or "").strip(),
        "detail_url": str(detail_url or "").strip(),
        "requested_semantic_fields": list(requested),
        "current_semantic_fields": dict(current_semantic_fields),
        "detail_text": bounded_text,
        "detail_text_char_count": len(bounded_text),
        "authority_constraints": {
            "exact_evidence_quote_required": True,
            "observed_source_value_required": True,
            "deterministic_field_normalization_required": True,
            "deterministic_unique_span_required": True,
            "same_detail_url_only": True,
            "hypothesis_only": True,
            "gate_pass": False,
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
                "name": "detail_semantics_evidence_hypotheses",
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
            raise ValueError("Detail Semantics hypothesis response must be an object")
        semantic_fields, references = _verified_observation_payload(
            detail_url=detail_url,
            detail_text=bounded_text,
            decoded=decoded,
            requested_fields=requested,
        )
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        rationale = str(decoded.get("rationale") or "").strip()[:600]
        return DetailSemanticsHypothesisObservation(
            status="completed",
            request_attempted=True,
            semantic_fields=semantic_fields,
            evidence_references=references,
            model=str(response.get("model") or model),
            response_id=str(response.get("id") or "") or None,
            estimated_cost_usd=_estimated_cost(model, usage_map),
            rationale=f"packet_sha256={packet_sha}; {rationale}"[:700],
            product_authority=False,
        )
    except (
        json.JSONDecodeError,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        return DetailSemanticsHypothesisObservation(
            status="failed_closed",
            request_attempted=True,
            semantic_fields={},
            evidence_references=(),
            model=model,
            response_id=None,
            estimated_cost_usd=0.0,
            rationale=(
                f"packet_sha256={packet_sha}; failure={type(exc).__name__}: {_safe_message(exc)}"
            )[:700],
            product_authority=False,
        )


__all__ = [
    "MAX_DETAIL_TEXT_CHARS",
    "request_detail_semantics_hypotheses",
]
