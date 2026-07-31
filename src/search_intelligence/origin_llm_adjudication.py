"""Governed LLM adjudication for ambiguous employer-origin evidence.

The provider receives a compact evidence packet only. It cannot invent candidate
URLs, overwrite deterministic evidence or mutate Pipeline state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Callable, Mapping, Sequence

import requests

from src.search_intelligence.origin_source_evidence import OriginEvidenceDecision

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

ADJUDICATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {
            "type": "string",
            "enum": [
                "confirm_deterministic",
                "prefer_alternative",
                "manual_review_required",
                "abstain",
            ],
        },
        "recommended_candidate_id": {"type": ["string", "null"]},
        "entity_relationship": {
            "type": "string",
            "enum": [
                "exact_legal_entity",
                "brand_match",
                "parent_group_match",
                "related_entity",
                "ambiguous",
                "unknown",
            ],
        },
        "origin_assessment": {
            "type": "string",
            "enum": [
                "verified_job_listing",
                "verified_empty_job_board",
                "career_landing_only",
                "not_job_bearing",
                "insufficient_evidence",
            ],
        },
        "manual_review_required": {"type": "boolean"},
        "evidence_references": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "remaining_uncertainty": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "rationale": {"type": "string", "maxLength": 1200},
    },
    "required": [
        "decision",
        "recommended_candidate_id",
        "entity_relationship",
        "origin_assessment",
        "manual_review_required",
        "evidence_references",
        "remaining_uncertainty",
        "rationale",
    ],
}

SYSTEM_INSTRUCTIONS = """You adjudicate employer job-origin evidence.
Use only the supplied candidates and observations. Never invent a URL, employer
relationship, job count or page content. Deterministic observations are primary.
A missing job today does not prove an origin is wrong. Prefer a concrete ATS/job
listing over a generic career landing page when entity fidelity is at least as
strong. Use exact candidate_id values only in recommended_candidate_id and
evidence_references. evidence_references must never contain prose, URLs or
observation labels. When evidence conflicts or a legal entity relationship is not
proven, require manual review or abstain. Return only the requested JSON schema."""


class AdjudicationValidationError(ValueError):
    """Validation failure with a stable diagnostic stage."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class LLMAdjudication:
    decision: str
    recommended_candidate_id: str | None
    entity_relationship: str
    origin_assessment: str
    manual_review_required: bool
    evidence_references: tuple[str, ...]
    remaining_uncertainty: tuple[str, ...]
    rationale: str

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence_references"] = list(self.evidence_references)
        payload["remaining_uncertainty"] = list(self.remaining_uncertainty)
        return payload


@dataclass(frozen=True)
class LLMAdjudicationResult:
    status: str
    provider: str
    model: str | None
    request_attempted: bool
    response_id: str | None
    usage: Mapping[str, object] | None
    adjudication: LLMAdjudication | None
    failure_class: str | None = None
    failure_stage: str | None = None
    failure_message: str | None = None
    provider_status: str | None = None
    http_status: int | None = None
    incomplete_details: Mapping[str, object] | None = None
    output_item_types: tuple[str, ...] = ()
    output_text_length: int | None = None
    raw_output_sha256: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "request_attempted": self.request_attempted,
            "response_id": self.response_id,
            "usage": dict(self.usage or {}),
            "adjudication": None
            if self.adjudication is None
            else self.adjudication.to_json(),
            "failure_class": self.failure_class,
            "failure_stage": self.failure_stage,
            "failure_message": self.failure_message,
            "provider_status": self.provider_status,
            "http_status": self.http_status,
            "incomplete_details": dict(self.incomplete_details or {}),
            "output_item_types": list(self.output_item_types),
            "output_text_length": self.output_text_length,
            "raw_output_sha256": self.raw_output_sha256,
        }


def build_adjudication_schema(candidate_ids: Sequence[str]) -> dict[str, object]:
    """Bind structured-output candidate references to the exact evidence packet."""

    allowed_ids = tuple(
        dict.fromkeys(str(item).strip() for item in candidate_ids if str(item).strip())
    )
    if not allowed_ids:
        raise ValueError("adjudication schema requires at least one candidate ID")

    schema = json.loads(json.dumps(ADJUDICATION_SCHEMA))
    properties = schema["properties"]
    properties["recommended_candidate_id"]["enum"] = [*allowed_ids, None]
    properties["evidence_references"]["items"]["enum"] = list(allowed_ids)
    return schema


def build_adjudication_packet(decision: OriginEvidenceDecision) -> dict[str, object]:
    candidates = []
    for item in decision.assessments[:4]:
        candidates.append(
            {
                "candidate_id": item.candidate_id,
                "url": item.final_url,
                "provider": item.provider,
                "source_grade": item.source_grade,
                "entity_fidelity": item.entity_fidelity,
                "job_inventory_state": item.job_inventory_state,
                "observed_job_count": item.observed_job_count,
                "target_signal_job_count": item.target_signal_job_count,
                "sample_job_urls": list(item.sample_job_urls[:3]),
                "locale": item.locale,
                "identity_score": item.identity_score,
                "ranking_score": item.ranking_score,
                "evidence_completeness": item.evidence_completeness,
                "reasons": list(item.reasons[:8]),
                "failure_class": item.failure_class,
            }
        )
    return {
        "schema_version": "origin_llm_adjudication_packet.v1",
        "company_key": decision.company_key,
        "company_name": decision.company_name,
        "deterministic_decision": decision.deterministic_decision,
        "deterministic_selected_candidate_id": decision.selected_candidate_id,
        "selection_margin": decision.selection_margin,
        "confidence_band": decision.confidence_band,
        "adjudication_reasons": list(decision.adjudication_reasons),
        "candidates": candidates,
        "boundary": {
            "candidate_ids_only": True,
            "no_new_url": True,
            "no_mutation": True,
            "provider_output_is_review_signal_only": True,
        },
    }


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
            if not isinstance(block, Mapping):
                continue
            if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(str(block["text"]))
    if not parts:
        raise ValueError("response contains no output_text")
    return "".join(parts)


def validate_adjudication(
    payload: Mapping[str, object],
    *,
    allowed_candidate_ids: set[str],
) -> LLMAdjudication:
    expected = set(ADJUDICATION_SCHEMA["required"])
    if set(payload) != expected:
        raise AdjudicationValidationError(
            "schema_validation",
            "adjudication field set does not match strict schema",
        )
    decision = str(payload["decision"])
    allowed_decisions = {
        "confirm_deterministic",
        "prefer_alternative",
        "manual_review_required",
        "abstain",
    }
    if decision not in allowed_decisions:
        raise AdjudicationValidationError(
            "schema_validation",
            "unsupported adjudication decision",
        )
    recommended_raw = payload["recommended_candidate_id"]
    recommended = None if recommended_raw is None else str(recommended_raw)
    if recommended is not None and recommended not in allowed_candidate_ids:
        raise AdjudicationValidationError(
            "candidate_validation",
            "provider recommended a candidate outside the evidence packet",
        )
    if decision == "prefer_alternative" and recommended is None:
        raise AdjudicationValidationError(
            "business_validation",
            "prefer_alternative requires a candidate ID",
        )
    references = tuple(str(item) for item in payload["evidence_references"])
    if not set(references).issubset(allowed_candidate_ids):
        raise AdjudicationValidationError(
            "candidate_validation",
            "provider cited an unknown candidate ID",
        )
    uncertainties = tuple(str(item) for item in payload["remaining_uncertainty"])
    return LLMAdjudication(
        decision=decision,
        recommended_candidate_id=recommended,
        entity_relationship=str(payload["entity_relationship"]),
        origin_assessment=str(payload["origin_assessment"]),
        manual_review_required=bool(payload["manual_review_required"]),
        evidence_references=references,
        remaining_uncertainty=uncertainties,
        rationale=str(payload["rationale"]),
    )


Transport = Callable[[str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]]


def _requests_transport(
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


def adjudicate_with_openai(
    decision: OriginEvidenceDecision,
    *,
    api_key: str,
    model: str,
    timeout_seconds: float = 45.0,
    transport: Transport = _requests_transport,
) -> LLMAdjudicationResult:
    key = str(api_key or "").strip()
    selected_model = str(model or "").strip()
    if not key:
        return LLMAdjudicationResult(
            status="configuration_error",
            provider="openai_responses",
            model=selected_model or None,
            request_attempted=False,
            response_id=None,
            usage=None,
            adjudication=None,
            failure_class="missing_openai_api_key",
            failure_stage="configuration",
            failure_message="OPENAI_API_KEY is missing",
        )
    if not selected_model:
        return LLMAdjudicationResult(
            status="configuration_error",
            provider="openai_responses",
            model=None,
            request_attempted=False,
            response_id=None,
            usage=None,
            adjudication=None,
            failure_class="missing_origin_adjudication_model",
            failure_stage="configuration",
            failure_message="origin adjudication model is missing",
        )

    packet = build_adjudication_packet(decision)
    allowed_ids = tuple(item.candidate_id for item in decision.assessments[:4])
    adjudication_schema = build_adjudication_schema(allowed_ids)
    request_payload: dict[str, object] = {
        "model": selected_model,
        "store": False,
        "max_output_tokens": 900,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_INSTRUCTIONS}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(packet, ensure_ascii=False, sort_keys=True),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "origin_adjudication",
                "strict": True,
                "schema": adjudication_schema,
            }
        },
    }
    response: Mapping[str, object] | None = None
    try:
        response = transport(
            OPENAI_RESPONSES_URL,
            {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            request_payload,
            timeout_seconds,
        )
        output_text = _extract_output_text(response)
        decoded = json.loads(output_text)
        if not isinstance(decoded, Mapping):
            raise AdjudicationValidationError(
                "schema_validation",
                "adjudication JSON root must be an object",
            )
        adjudication = validate_adjudication(
            decoded,
            allowed_candidate_ids=set(allowed_ids),
        )
    except (json.JSONDecodeError, requests.RequestException, TypeError, ValueError) as exc:
        usage = None if response is None else response.get("usage")
        if isinstance(exc, AdjudicationValidationError):
            failure_stage = exc.stage
        elif isinstance(exc, json.JSONDecodeError):
            failure_stage = "json_decode"
        elif isinstance(exc, requests.RequestException):
            failure_stage = "transport"
        else:
            failure_stage = "output_extraction"
        return LLMAdjudicationResult(
            status="failed_closed",
            provider="openai_responses",
            model=(
                selected_model
                if response is None
                else str(response.get("model") or selected_model)
            ),
            request_attempted=True,
            response_id=(
                None
                if response is None
                else (str(response.get("id") or "") or None)
            ),
            usage=usage if isinstance(usage, Mapping) else None,
            adjudication=None,
            failure_class=type(exc).__name__,
            failure_stage=failure_stage,
            failure_message=str(exc)[:800],
            provider_status=(
                None
                if response is None
                else (str(response.get("status") or "") or None)
            ),
        )

    usage = response.get("usage")
    return LLMAdjudicationResult(
        status="completed",
        provider="openai_responses",
        model=str(response.get("model") or selected_model),
        request_attempted=True,
        response_id=str(response.get("id") or "") or None,
        usage=usage if isinstance(usage, Mapping) else None,
        adjudication=adjudication,
        provider_status=str(response.get("status") or "") or None,
    )


def final_review_state(
    decision: OriginEvidenceDecision,
    result: LLMAdjudicationResult | None,
) -> str:
    """Keep provider output separate from deterministic truth and all mutations."""

    if decision.deterministic_decision == "origin_url_candidate_selected":
        return "deterministic_candidate_ready_for_operator_review"
    if result is None or result.adjudication is None:
        return "manual_review_required"
    adjudication = result.adjudication
    if adjudication.decision == "abstain" or adjudication.manual_review_required:
        return "manual_review_required"
    if adjudication.recommended_candidate_id:
        return "provider_recommends_candidate_for_operator_review"
    return "manual_review_required"
