"""Bounded early-LLM provider for origin search-space expansion.

This provider is deliberately separate from late evidence adjudication. It may
propose at most three novel search queries and three novel URL hypotheses. It
cannot select, persist, register, or activate an origin source. All proposed URLs
must subsequently pass the deterministic origin discovery and evidence gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from time import perf_counter
from typing import Callable, Mapping

import requests

from src.search_intelligence.adaptive_origin_search import (
    SearchHypothesisSet,
    SearchProgressLedger,
    validate_search_hypotheses,
)
from src.search_intelligence.origin_llm_adjudication import OPENAI_RESPONSES_URL
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float],
    Mapping[str, object],
]

SYSTEM_INSTRUCTIONS = """You expand a bounded search space for an official employer career source.
Return only novel hypotheses that a human searcher would try after the supplied attempts failed.
You may transform symbol and numeric brands into plausible domain surfaces, propose site searches,
and propose likely official career hosts. Do not claim that any URL is valid. Do not repeat an
attempted query or URL. Do not propose aggregators, social media, or job-board URLs. Return at most
three queries and three HTTPS URL hypotheses. Every hypothesis will be independently validated.
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


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["queries", "urls", "rationale"],
        "properties": {
            "queries": {
                "type": "array",
                "maxItems": 3,
                "items": {"type": "string", "minLength": 1, "maxLength": 240},
            },
            "urls": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "string",
                    "pattern": "^https://",
                    "maxLength": 500,
                },
            },
            "rationale": {"type": "string", "maxLength": 600},
        },
    }


@dataclass(frozen=True)
class SearchHypothesisObservation:
    status: str
    request_attempted: bool
    model: str
    response_id: str | None
    latency_ms: int
    estimated_cost_usd: float
    packet_sha256: str
    hypotheses: SearchHypothesisSet | None
    failure_class: str | None = None
    failure_message: str | None = None

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["hypotheses"] = (
            None if self.hypotheses is None else self.hypotheses.to_json()
        )
        return payload


def request_search_hypotheses(
    *,
    company_key: str,
    company_name: str,
    baseline_payload: Mapping[str, object],
    latest_payload: Mapping[str, object],
    ledger: SearchProgressLedger,
    api_key: str,
    model: str,
    reasoning_effort: str = "low",
    max_output_tokens: int = 500,
    timeout_seconds: float = 60.0,
    transport: Transport = _transport,
) -> SearchHypothesisObservation:
    packet = {
        "company_key": company_key,
        "company_name": company_name,
        "attempted_queries": sorted(ledger.attempted_queries),
        "attempted_urls": sorted(ledger.attempted_urls),
        "observed_domains": sorted(ledger.observed_domains),
        "baseline": {
            "decision": baseline_payload.get("decision"),
            "confidence_score": baseline_payload.get("confidence_score"),
            "rejected": baseline_payload.get("rejected", [])[:6]
            if isinstance(baseline_payload.get("rejected"), list)
            else [],
        },
        "latest": {
            "decision": latest_payload.get("decision"),
            "confidence_score": latest_payload.get("confidence_score"),
            "search_results": latest_payload.get("search_results", [])[:12]
            if isinstance(latest_payload.get("search_results"), list)
            else [],
            "alternatives": latest_payload.get("alternatives", [])[:6]
            if isinstance(latest_payload.get("alternatives"), list)
            else [],
            "rejected": latest_payload.get("rejected", [])[:6]
            if isinstance(latest_payload.get("rejected"), list)
            else [],
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
                "name": "origin_search_hypotheses",
                "strict": True,
                "schema": _schema(),
            },
        },
    }

    started = perf_counter()
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
            raise ValueError("search hypothesis response must be an object")
        hypotheses = validate_search_hypotheses(decoded, ledger=ledger)
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        return SearchHypothesisObservation(
            status="completed",
            request_attempted=True,
            model=str(response.get("model") or model),
            response_id=str(response.get("id") or "") or None,
            latency_ms=int(round((perf_counter() - started) * 1000)),
            estimated_cost_usd=_estimated_cost(model, usage_map),
            packet_sha256=packet_sha,
            hypotheses=hypotheses,
        )
    except (
        json.JSONDecodeError,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        return SearchHypothesisObservation(
            status="failed_closed",
            request_attempted=True,
            model=model,
            response_id=None,
            latency_ms=int(round((perf_counter() - started) * 1000)),
            estimated_cost_usd=0.0,
            packet_sha256=packet_sha,
            hypotheses=None,
            failure_class=type(exc).__name__,
            failure_message=_safe_message(exc),
        )
