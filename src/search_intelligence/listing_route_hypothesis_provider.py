"""Bounded LLM provider for unresolved Listing Discovery route hypotheses.

The provider can only propose HTTPS listing/career/ATS route hypotheses. It has
no authority to select, persist, register, or activate a source. Every returned
URL must be re-fetched and reclassified by ``listing_surface_evidence`` before
it can resolve the Listing station.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from time import perf_counter
from typing import Callable, Mapping

import requests

from src.search_intelligence.listing_booster_progress import ListingProgressLedger
from src.search_intelligence.origin_llm_adjudication import OPENAI_RESPONSES_URL
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]
]

SYSTEM_INSTRUCTIONS = """You expand a bounded search space for an employer's current job-listing route.
Return only plausible official employer career/listing or ATS-board HTTPS route hypotheses that could
contain the employer's current vacancies. Do not claim that any URL is valid. Do not propose social
media, generic job aggregators, individual candidate profiles, login/authentication routes, or unrelated
companies. Prefer listing/search/board routes over individual job-detail URLs. Return at most three URL
hypotheses. Every URL will be independently fetched and deterministically validated; your output has no
product authority.
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
        "required": ["urls", "rationale"],
        "properties": {
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
class ListingRouteHypothesisObservation:
    status: str
    request_attempted: bool
    model: str
    response_id: str | None
    latency_ms: int
    estimated_cost_usd: float
    packet_sha256: str
    urls: tuple[str, ...]
    rationale: str
    product_authority: bool = False
    failure_class: str | None = None
    failure_message: str | None = None

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["urls"] = list(self.urls)
        return payload


def _novel_urls_without_consuming(
    ledger: ListingProgressLedger,
    raw_urls: list[object],
) -> tuple[str, ...]:
    return ledger.clone().novel_urls(str(item) for item in raw_urls[:3])


def request_listing_route_hypotheses(
    *,
    company_key: str,
    company_name: str,
    origin_url: str,
    deterministic_evidence: Mapping[str, object],
    attempted_candidate_summaries: tuple[Mapping[str, object], ...],
    ledger: ListingProgressLedger,
    api_key: str,
    model: str,
    reasoning_effort: str = "medium",
    max_output_tokens: int = 500,
    timeout_seconds: float = 60.0,
    transport: Transport = _transport,
) -> ListingRouteHypothesisObservation:
    packet = {
        "company_key": company_key,
        "company_name": company_name,
        "origin_url": origin_url,
        "deterministic_listing_evidence": {
            "final_url": deterministic_evidence.get("final_url"),
            "classification": deterministic_evidence.get("classification"),
            "reason_codes": deterministic_evidence.get("reason_codes", []),
            "jsonld_types": deterministic_evidence.get("jsonld_types", []),
            "route_candidates": deterministic_evidence.get("route_candidates", []),
            "delegated_route_candidates": deterministic_evidence.get(
                "delegated_route_candidates", []
            ),
        },
        "attempted_urls": sorted(ledger.attempted_urls),
        "observed_domains": sorted(ledger.observed_domains),
        "attempted_candidate_summaries": [
            dict(item) for item in attempted_candidate_summaries[-8:]
        ],
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
                "name": "listing_route_hypotheses",
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
            raise ValueError("listing route hypothesis response must be an object")
        raw_urls = decoded.get("urls")
        if not isinstance(raw_urls, list):
            raise ValueError("listing route hypothesis response requires urls array")
        urls = _novel_urls_without_consuming(ledger, raw_urls)
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        return ListingRouteHypothesisObservation(
            status="completed",
            request_attempted=True,
            model=str(response.get("model") or model),
            response_id=str(response.get("id") or "") or None,
            latency_ms=int(round((perf_counter() - started) * 1000)),
            estimated_cost_usd=_estimated_cost(model, usage_map),
            packet_sha256=packet_sha,
            urls=urls,
            rationale=str(decoded.get("rationale") or "").strip()[:600],
            product_authority=False,
        )
    except (
        json.JSONDecodeError,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        return ListingRouteHypothesisObservation(
            status="failed_closed",
            request_attempted=True,
            model=model,
            response_id=None,
            latency_ms=int(round((perf_counter() - started) * 1000)),
            estimated_cost_usd=0.0,
            packet_sha256=packet_sha,
            urls=(),
            rationale="",
            product_authority=False,
            failure_class=type(exc).__name__,
            failure_message=_safe_message(exc),
        )


__all__ = [
    "ListingRouteHypothesisObservation",
    "request_listing_route_hypotheses",
]
