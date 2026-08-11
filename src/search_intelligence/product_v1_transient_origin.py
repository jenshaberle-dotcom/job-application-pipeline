from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from src.search_intelligence.origin_source_discovery_agent import OriginDiscoveryResult


@dataclass(frozen=True)
class TransientOriginResolution:
    status: str
    decision: str
    selected_url: str | None
    selected_domain: str | None
    confidence_score: float
    risk_level: str
    candidate_count: int
    assessed_count: int
    reason: str


def should_attempt_transient_origin(origin_candidate_status: str) -> bool:
    """Only a genuinely missing persisted candidate may enter transient fallback."""

    return origin_candidate_status == "origin_candidate_required"


def _absolute_https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def classify_transient_origin_result(
    result: OriginDiscoveryResult,
) -> TransientOriginResolution:
    common = {
        "decision": result.decision,
        "selected_url": result.selected_url,
        "selected_domain": result.selected_domain,
        "confidence_score": result.confidence_score,
        "risk_level": result.risk_level,
        "candidate_count": result.candidate_count,
        "assessed_count": result.assessed_count,
        "reason": result.reason,
    }
    if (
        result.decision == "origin_url_candidate_selected"
        and _absolute_https_url(result.selected_url)
    ):
        return TransientOriginResolution(
            status="ready_for_bounded_detail_discovery",
            **common,
        )
    if result.decision == "origin_url_candidate_selected":
        return TransientOriginResolution(
            status="transient_origin_invalid_selected_url",
            **common,
        )
    if result.decision == "manual_review_required":
        return TransientOriginResolution(
            status="transient_origin_manual_review_required",
            **common,
        )
    if result.decision == "not_found":
        return TransientOriginResolution(
            status="transient_origin_not_found",
            **common,
        )
    return TransientOriginResolution(
        status="transient_origin_unclassified",
        **common,
    )


def transient_origin_resolution_payload(
    resolution: TransientOriginResolution,
) -> dict[str, object]:
    return asdict(resolution)
