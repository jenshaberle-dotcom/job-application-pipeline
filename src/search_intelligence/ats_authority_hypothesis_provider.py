"""Bounded LLM provider for unresolved ATS authority-evidence gaps.

The provider may only propose HTTPS ATS URLs that could contain alternate public
evidence for an employer/ATS binding. It cannot validate a tenant, permit
delegation, persist a source, or activate a connector. Every returned URL is
filtered by the execution ledger and then routed back to deterministic
provider-specific authority validation.
"""

from __future__ import annotations

import hashlib
import json
import re
from time import perf_counter
from typing import Callable, Mapping

import requests

from src.search_intelligence.ats_authority_gap_execution import (
    ATSAuthorityHypothesisObservation,
    ATSAuthorityProgressLedger,
)
from src.search_intelligence.origin_llm_adjudication import OPENAI_RESPONSES_URL
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)

Transport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float], Mapping[str, object]
]

SYSTEM_INSTRUCTIONS = """You expand a bounded evidence search for an employer's ATS authority binding.
Return only plausible public HTTPS ATS URLs that could help a deterministic validator prove which ATS
provider/tenant belongs to the named employer. Do not claim that any tenant is authoritative. Do not
claim delegation is permitted. Do not return generic job aggregators, social media, login/authentication
routes, unrelated companies, or invented URLs. Prefer official ATS tenant/board/listing/evidence routes.
Return at most three URL hypotheses. Every URL is independently classified and must pass a separate
provider-specific deterministic authority validator; your output has no product authority.
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


def _novel_urls_without_consuming(
    ledger: ATSAuthorityProgressLedger,
    raw_urls: list[object],
) -> tuple[str, ...]:
    return ledger.clone().novel_urls(tuple(str(item) for item in raw_urls[:3]))


def request_ats_authority_hypotheses(
    *,
    company_key: str,
    company_name: str,
    expected_provider: str | None,
    authority_gap_evidence: Mapping[str, object],
    attempted_candidate_summaries: tuple[Mapping[str, object], ...],
    ledger: ATSAuthorityProgressLedger,
    api_key: str,
    model: str,
    reasoning_effort: str = "medium",
    max_output_tokens: int = 500,
    timeout_seconds: float = 60.0,
    transport: Transport = _transport,
) -> ATSAuthorityHypothesisObservation:
    """Request bounded ATS evidence URL hypotheses with zero selection authority."""

    packet = {
        "company_key": company_key,
        "company_name": company_name,
        "expected_provider": expected_provider,
        "authority_gap": {
            "classification": authority_gap_evidence.get("classification"),
            "external_information_gap": authority_gap_evidence.get(
                "external_information_gap"
            ),
            "deterministic_request_replay_blocked": authority_gap_evidence.get(
                "deterministic_request_replay_blocked"
            ),
            "next_action": authority_gap_evidence.get("next_action"),
            "evidence_fingerprint": authority_gap_evidence.get("evidence_fingerprint"),
        },
        "attempted_urls": sorted(ledger.attempted_urls),
        "attempted_candidate_summaries": [
            dict(item) for item in attempted_candidate_summaries[-8:]
        ],
        "authority_constraints": {
            "candidate_only": True,
            "tenant_authority": False,
            "delegation_permitted": False,
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
                "name": "ats_authority_evidence_hypotheses",
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
            raise ValueError("ATS authority hypothesis response must be an object")
        raw_urls = decoded.get("urls")
        if not isinstance(raw_urls, list):
            raise ValueError("ATS authority hypothesis response requires urls array")
        urls = _novel_urls_without_consuming(ledger, raw_urls)
        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else None
        rationale = str(decoded.get("rationale") or "").strip()[:600]
        # Trace identity stays in rationale-free packet/evidence logs owned by the
        # caller; this observation intentionally carries no raw prompt/body.
        return ATSAuthorityHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=urls,
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
        return ATSAuthorityHypothesisObservation(
            status="failed_closed",
            request_attempted=True,
            urls=(),
            model=model,
            response_id=None,
            estimated_cost_usd=0.0,
            rationale=(
                f"packet_sha256={packet_sha}; failure={type(exc).__name__}: {_safe_message(exc)}"
            )[:700],
            product_authority=False,
        )


__all__ = ["request_ats_authority_hypotheses"]
