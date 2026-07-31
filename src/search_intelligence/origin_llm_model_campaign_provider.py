"""Provider transport for the bounded origin LLM model campaign."""

from __future__ import annotations

import hashlib
import json
import re
from time import perf_counter
from typing import Callable, Mapping

import requests

from src.search_intelligence.origin_llm_adjudication import (
    ADJUDICATION_SCHEMA,
    OPENAI_RESPONSES_URL,
    SYSTEM_INSTRUCTIONS,
    AdjudicationValidationError,
    LLMAdjudicationResult,
    build_adjudication_packet,
    validate_adjudication,
)
from src.search_intelligence.origin_source_evidence import OriginEvidenceDecision
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
    ModelCallObservation,
    canonical_sha256,
)

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float],
    Mapping[str, object],
]


class ProviderTransportError(RuntimeError):
    """Sanitized provider failure with stable stage and HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.http_status = http_status


def _safe_failure_message(exc: BaseException) -> str:
    text = " ".join(str(exc).split()) or type(exc).__name__
    text = re.sub(r"Bearer\s+\S+", "Bearer ***", text, flags=re.IGNORECASE)
    return text[:800]


def _output_item_types(response: Mapping[str, object]) -> tuple[str, ...]:
    output = response.get("output")
    if not isinstance(output, list):
        return ()
    result: list[str] = []
    for item in output:
        if not isinstance(item, Mapping):
            continue
        item_type = item.get("type")
        if isinstance(item_type, str) and item_type:
            result.append(item_type)
    return tuple(result)


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
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = response.status_code
        stage = "authentication" if status in {401, 403} else "provider_response"
        raise ProviderTransportError(
            f"OpenAI request failed with HTTP {status}",
            stage=stage,
            http_status=status,
        ) from exc
    try:
        decoded = response.json()
    except ValueError as exc:
        raise ProviderTransportError(
            "OpenAI response body is not valid JSON",
            stage="provider_response",
            http_status=response.status_code,
        ) from exc
    if not isinstance(decoded, Mapping):
        raise ProviderTransportError(
            "OpenAI response root must be an object",
            stage="provider_response",
            http_status=response.status_code,
        )
    return decoded


def build_request_payload(
    decision: OriginEvidenceDecision,
    *,
    model: str,
    reasoning_effort: str = "low",
    max_output_tokens: int = 900,
) -> tuple[dict[str, object], str, str]:
    packet = build_adjudication_packet(decision)
    packet_sha = canonical_sha256(packet)
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
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(packet, ensure_ascii=False, sort_keys=True),
                    }
                ],
            },
        ],
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "origin_adjudication",
                "strict": True,
                "schema": ADJUDICATION_SCHEMA,
            },
        },
    }
    contract_payload = {
        "packet_sha256": packet_sha,
        "system_instructions": SYSTEM_INSTRUCTIONS,
        "reasoning_effort": reasoning_effort,
        "max_output_tokens": max_output_tokens,
        "schema": ADJUDICATION_SCHEMA,
        "store": False,
        "text_verbosity": "low",
    }
    return payload, packet_sha, canonical_sha256(contract_payload)


def _estimated_cost_usd(model: str, usage: Mapping[str, object] | None) -> float:
    if usage is None:
        return 0.0
    prices = MODEL_PRICES_USD_PER_MILLION.get(model)
    if prices is None:
        return 0.0
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    input_price, output_price = prices
    return (
        input_tokens * input_price / 1_000_000
        + output_tokens * output_price / 1_000_000
    )


def adjudicate_model(
    decision: OriginEvidenceDecision,
    *,
    api_key: str,
    model: str,
    reasoning_effort: str = "low",
    max_output_tokens: int = 900,
    timeout_seconds: float = 60.0,
    transport: Transport = _requests_transport,
) -> ModelCallObservation:
    key = str(api_key or "").strip()
    selected_model = str(model or "").strip()
    request_payload, packet_sha, request_contract_sha = build_request_payload(
        decision,
        model=selected_model,
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
    )
    if not key or not selected_model:
        failure = "missing_openai_api_key" if not key else "missing_model"
        result = LLMAdjudicationResult(
            status="configuration_error",
            provider="openai_responses",
            model=selected_model or None,
            request_attempted=False,
            response_id=None,
            usage=None,
            adjudication=None,
            failure_class=failure,
            failure_stage="configuration",
            failure_message=(
                "OPENAI_API_KEY is missing" if not key else "model is missing"
            ),
        )
        return ModelCallObservation(
            company_key=decision.company_key,
            company_name=decision.company_name,
            model_requested=selected_model,
            model_returned=None,
            packet_sha256=packet_sha,
            request_contract_sha256=request_contract_sha,
            latency_ms=0,
            estimated_cost_usd=0.0,
            result=result,
        )

    started = perf_counter()
    response: Mapping[str, object] | None = None
    usage_map: Mapping[str, object] | None = None
    returned_model = selected_model
    response_id: str | None = None
    provider_status: str | None = None
    http_status: int | None = None
    incomplete_details: Mapping[str, object] | None = None
    output_item_types: tuple[str, ...] = ()
    output_text_length: int | None = None
    raw_output_sha256: str | None = None
    failure_stage = "transport"
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
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        returned_model = str(response.get("model") or selected_model)
        response_id = str(response.get("id") or "") or None
        provider_status = str(response.get("status") or "") or None
        incomplete = response.get("incomplete_details")
        incomplete_details = incomplete if isinstance(incomplete, Mapping) else None
        output_item_types = _output_item_types(response)

        failure_stage = "output_extraction"
        output_text = _extract_output_text(response)
        output_text_length = len(output_text)
        raw_output_sha256 = hashlib.sha256(output_text.encode("utf-8")).hexdigest()

        failure_stage = "json_decode"
        decoded = json.loads(output_text)
        if not isinstance(decoded, Mapping):
            raise AdjudicationValidationError(
                "schema_validation",
                "adjudication JSON root must be an object",
            )

        failure_stage = "schema_validation"
        allowed_ids = {item.candidate_id for item in decision.assessments[:4]}
        adjudication = validate_adjudication(
            decoded,
            allowed_candidate_ids=allowed_ids,
        )
        result = LLMAdjudicationResult(
            status="completed",
            provider="openai_responses",
            model=returned_model,
            request_attempted=True,
            response_id=response_id,
            usage=usage_map,
            adjudication=adjudication,
            provider_status=provider_status,
            http_status=http_status,
            incomplete_details=incomplete_details,
            output_item_types=output_item_types,
            output_text_length=output_text_length,
            raw_output_sha256=raw_output_sha256,
        )
    except (
        AdjudicationValidationError,
        ProviderTransportError,
        json.JSONDecodeError,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        if isinstance(exc, AdjudicationValidationError):
            failure_stage = exc.stage
        elif isinstance(exc, ProviderTransportError):
            failure_stage = exc.stage
            http_status = exc.http_status
        elif isinstance(exc, json.JSONDecodeError):
            failure_stage = "json_decode"
        elif isinstance(exc, requests.RequestException):
            failure_stage = "transport"
        result = LLMAdjudicationResult(
            status="failed_closed",
            provider="openai_responses",
            model=returned_model,
            request_attempted=True,
            response_id=response_id,
            usage=usage_map,
            adjudication=None,
            failure_class=type(exc).__name__,
            failure_stage=failure_stage,
            failure_message=_safe_failure_message(exc),
            provider_status=provider_status,
            http_status=http_status,
            incomplete_details=incomplete_details,
            output_item_types=output_item_types,
            output_text_length=output_text_length,
            raw_output_sha256=raw_output_sha256,
        )
    elapsed_ms = int(round((perf_counter() - started) * 1000))
    return ModelCallObservation(
        company_key=decision.company_key,
        company_name=decision.company_name,
        model_requested=selected_model,
        model_returned=returned_model,
        packet_sha256=packet_sha,
        request_contract_sha256=request_contract_sha,
        latency_ms=elapsed_ms,
        estimated_cost_usd=_estimated_cost_usd(selected_model, usage_map),
        result=result,
    )
