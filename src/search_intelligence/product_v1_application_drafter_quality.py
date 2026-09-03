"""Quality-hardened Product V1 application drafting for DEMO-001.

This module keeps the bounded OpenAI campaign and Candidate-Fact / employer-origin
authority rules. At the operator's explicit Generate action, the text of the two
approved local base documents is shared with the provider as style/structure context.
The base documents still do not grant authority for newly invented or strengthened
candidate claims; those remain bound to approved Candidate Facts.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence

import requests

from src.search_intelligence.llm_booster_policy import BoosterStage, MODEL_CONFIG
from src.search_intelligence.origin_llm_adjudication import OPENAI_RESPONSES_URL
from src.search_intelligence.product_v1_application_context import ProductV1ApplicationContext
from src.search_intelligence.product_v1_application_drafter import (
    ApplicationDraftObservation,
    DRAFT_FRAGMENT_KINDS,
    MAX_DETAIL_TEXT_CHARS,
    MAX_FACT_KEYS_PER_FRAGMENT,
    MAX_FRAGMENT_CHARS,
    MAX_FRAGMENTS,
    MAX_JOB_QUOTES_PER_FRAGMENT,
    ModelCallback,
    Transport,
    _estimated_cost,
    _extract_output_text,
    _fact_map,
    _safe_message,
    _source_manifest_sha256,
    _transport,
    _validate_package,
)


MAX_ALLOWED_JOB_QUOTES = 16
MAX_ALLOWED_QUOTE_CHARS = 600
MAX_BASE_DOCUMENT_CHARS = 12_000
_QUOTE_RADII = (48, 80, 120, 180, 260)

QUALITY_SYSTEM_INSTRUCTIONS = """Create polished German job-application material for operator review only.

The operator explicitly approved sharing the extracted text of the two approved base documents for this
Generate action. Use the base CV to understand existing structure, terminology and emphasis. Use the base
application letter as a style/tone reference. Never carry forward an old employer, old role, old addressee or
old vacancy-specific statement from the base letter into the new application.

Write like an experienced German application writer, not like an audit system or generic AI assistant. Avoid
phrases such as 'hiermit bewerbe ich', 'the vacancy states', 'evidence', 'Candidate Fact', 'claim plan',
'directly relevant', exaggerated enthusiasm and empty superlatives. Prefer concise, concrete connections
between the candidate's approved experience and the actual role.

Return status 'draft_for_review' and structured fragments only. Aim for exactly one strong cv_summary, three
or four cv_bullet fragments, one letter_opening, two or three substantial letter_fit paragraphs and one short
letter_closing. The letter fragments together must read as one coherent German letter of roughly 250-350
words with natural transitions. The opening should quickly explain why this specific role is a credible next
step. The fit paragraphs should cover the two or three strongest supported connections rather than repeat the
same Python/SQL point. The closing should be confident and brief.

Candidate Facts are the authority for new or rephrased candidate-specific claims. Every cv_summary/cv_bullet
must cite at least one allowed candidate_fact_key. Every letter_fit must cite at least one allowed
candidate_fact_key and at least one supplied allowed_job_evidence quote. letter_opening must cite at least one
supplied allowed_job_evidence quote. letter_closing must stay generic and cite no facts or vacancy quotes.

For job_evidence, copy values exactly from allowed_job_evidence; never create, shorten or paraphrase a quote.
Do not invent years, counts, percentages, certifications, employers, skills, salary, location, availability or
experience. Do not approve, persist, submit or send anything. Do not claim application, submission or product
authority. Do not use outside knowledge.
"""


def _unique_quote_around(*, detail_text: str, start: int, end: int) -> str | None:
    """Return a readable exact substring that occurs exactly once in detail_text."""

    if not (0 <= start < end <= len(detail_text)):
        return None
    for radius in _QUOTE_RADII:
        left = max(0, start - radius)
        right = min(len(detail_text), end + radius)

        if left > 0:
            boundary = detail_text.rfind(" ", left, start)
            if boundary >= 0:
                left = boundary + 1
        if right < len(detail_text):
            boundary = detail_text.find(" ", end, right)
            if boundary >= 0:
                right = boundary

        quote = detail_text[left:right].strip()
        if not quote or len(quote) > MAX_ALLOWED_QUOTE_CHARS:
            continue
        if detail_text.count(quote) == 1:
            return quote

    raw = detail_text[start:end]
    return raw if raw and detail_text.count(raw) == 1 else None


def allowed_job_evidence(context: ProductV1ApplicationContext) -> tuple[str, ...]:
    """Build bounded unique exact vacancy snippets from deterministic claim matches."""

    detail_text = context.target.detail_text
    quotes: list[str] = []
    seen: set[str] = set()
    for entry in context.claim_plan:
        for reference in entry.job_references:
            quote = _unique_quote_around(
                detail_text=detail_text,
                start=reference.span_start,
                end=reference.span_end,
            )
            if quote is None or quote in seen:
                continue
            seen.add(quote)
            quotes.append(quote)
            if len(quotes) >= MAX_ALLOWED_JOB_QUOTES:
                return tuple(quotes)
    return tuple(quotes)


def _quality_schema(
    allowed_fact_keys: Sequence[str],
    allowed_quotes: Sequence[str],
) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "fragments", "rationale"],
        "properties": {
            "status": {"type": "string", "enum": ["draft_for_review"]},
            "fragments": {
                "type": "array",
                "minItems": 2,
                "maxItems": MAX_FRAGMENTS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "text", "candidate_fact_keys", "job_evidence"],
                    "properties": {
                        "kind": {"type": "string", "enum": list(DRAFT_FRAGMENT_KINDS)},
                        "text": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": MAX_FRAGMENT_CHARS,
                        },
                        "candidate_fact_keys": {
                            "type": "array",
                            "maxItems": MAX_FACT_KEYS_PER_FRAGMENT,
                            "items": {"type": "string", "enum": list(allowed_fact_keys)},
                        },
                        "job_evidence": {
                            "type": "array",
                            "maxItems": MAX_JOB_QUOTES_PER_FRAGMENT,
                            "items": {"type": "string", "enum": list(allowed_quotes)},
                        },
                    },
                },
            },
            "rationale": {"type": "string", "maxLength": 600},
        },
    }


def _quality_packet(
    context: ProductV1ApplicationContext,
    allowed_quotes: Sequence[str],
) -> dict[str, object]:
    claim_plan = [
        {
            "fact_key": entry.fact_key,
            "approved_statement": entry.statement,
            "limitations": list(entry.limitations),
            "matched_capability_tags": list(entry.matched_capability_tags),
        }
        for entry in context.claim_plan
    ]
    return {
        "draft_language": "de",
        "target": {
            "title": context.target.title,
            "company_name": context.target.company_name,
            "source_url": context.target.source_url,
            "detail_text": context.target.detail_text[:MAX_DETAIL_TEXT_CHARS],
        },
        "approved_claim_plan": claim_plan,
        "allowed_job_evidence": list(allowed_quotes),
        "source_manifest_sha256": _source_manifest_sha256(context),
        "base_documents": [
            {
                "document_type": document.document_type,
                "source_label": document.source_label,
                "content_sha256": document.content_sha256,
                "content": document.content[:MAX_BASE_DOCUMENT_CHARS],
                "text_shared_with_provider": True,
                "usage": "style_structure_and_approved_carry_forward_context",
                "fact_authority_for_new_claims": False,
            }
            for document in context.source_documents
        ],
        "authority_constraints": {
            "draft_for_review_only": True,
            "candidate_claims_require_fact_keys": True,
            "vacancy_assertions_require_allowed_exact_quotes": True,
            "base_document_text_shared_with_provider": True,
            "base_document_fact_authority_for_new_claims": False,
            "draft_approval_authority": False,
            "application_authority": False,
            "submission_authority": False,
            "send_authority": False,
            "product_authority": False,
        },
    }


def request_quality_application_draft(
    *,
    context: ProductV1ApplicationContext,
    api_key: str,
    model: str,
    reasoning_effort: str = "medium",
    max_output_tokens: int = 3_200,
    timeout_seconds: float = 90.0,
    transport: Transport = _transport,
) -> ApplicationDraftObservation:
    if not context.generation_ready:
        return ApplicationDraftObservation(
            status="blocked",
            request_attempted=False,
            package=None,
            model=model,
            rationale="generation_context_not_ready",
        )

    allowed_fact_keys = tuple(sorted(_fact_map(context)))
    allowed_quotes = allowed_job_evidence(context)
    if not allowed_fact_keys:
        return ApplicationDraftObservation(
            status="blocked",
            request_attempted=False,
            package=None,
            model=model,
            rationale="candidate_job_claim_plan_required",
        )
    if not allowed_quotes:
        return ApplicationDraftObservation(
            status="blocked",
            request_attempted=False,
            package=None,
            model=model,
            rationale="unique_vacancy_evidence_required",
        )

    packet = _quality_packet(context, allowed_quotes)
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
                "content": [{"type": "input_text", "text": QUALITY_SYSTEM_INSTRUCTIONS}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": packet_json}],
            },
        ],
        "text": {
            "verbosity": "medium",
            "format": {
                "type": "json_schema",
                "name": "product_v1_application_draft_for_review_v3",
                "strict": True,
                "schema": _quality_schema(allowed_fact_keys, allowed_quotes),
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
            raise ValueError("application draft response must be an object")
        package = _validate_package(decoded=decoded, context=context)
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        return ApplicationDraftObservation(
            status="completed",
            request_attempted=True,
            package=package,
            model=str(response.get("model") or model),
            response_id=str(response.get("id") or "") or None,
            estimated_cost_usd=_estimated_cost(model, usage_map),
            rationale=(
                f"packet_sha256={packet_sha}; unique_evidence_quotes={len(allowed_quotes)}; "
                "base_document_style_context_shared=true; validated_quality_draft_for_review"
            ),
        )
    except (
        json.JSONDecodeError,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        return ApplicationDraftObservation(
            status="failed_closed",
            request_attempted=True,
            package=None,
            model=model,
            estimated_cost_usd=0.0,
            rationale=(
                f"packet_sha256={packet_sha}; unique_evidence_quotes={len(allowed_quotes)}; "
                f"failure={type(exc).__name__}: {_safe_message(exc)}"
            )[:900],
        )


def openai_quality_application_draft_model_callback(
    *,
    context: ProductV1ApplicationContext,
    api_key: str,
    transport: Transport = _transport,
) -> ModelCallback:
    def callback(stage: BoosterStage) -> ApplicationDraftObservation:
        model, reasoning_effort = MODEL_CONFIG[stage]
        return request_quality_application_draft(
            context=context,
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort,
            transport=transport,
        )

    return callback


__all__ = [
    "MAX_ALLOWED_JOB_QUOTES",
    "MAX_BASE_DOCUMENT_CHARS",
    "QUALITY_SYSTEM_INSTRUCTIONS",
    "allowed_job_evidence",
    "openai_quality_application_draft_model_callback",
    "request_quality_application_draft",
]
