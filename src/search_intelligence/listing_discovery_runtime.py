"""Listing Discovery projection over the active connector-feasibility runtime.

The existing connector-feasibility decision remains authoritative. This wrapper
fetches at most once, delegates all existing feasibility/query-detail behavior,
and appends deterministic LLM-BOOST-001 listing-surface evidence for later
booster eligibility decisions. It does not call Tavily/LLMs or widen product
authority.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from src.search_intelligence.connector_feasibility import (
    ConnectorFeasibilityItem,
    ConnectorFeasibilityReview,
    OriginCandidate,
    ProbeFetchResult,
    bounded_fetch,
)
from src.search_intelligence.connector_feasibility_query_runtime import (
    evaluate_connector_feasibility_runtime as evaluate_base_runtime,
)
from src.search_intelligence.listing_surface_evidence import analyze_listing_surface


def evaluate_listing_discovery_runtime(
    candidate: OriginCandidate,
    *,
    fetch_enabled: bool = True,
    fetch_result: ProbeFetchResult | None = None,
) -> ConnectorFeasibilityItem:
    if not fetch_enabled or not candidate.origin_url:
        item = evaluate_base_runtime(
            candidate,
            fetch_enabled=fetch_enabled,
            fetch_result=fetch_result,
        )
        listing = analyze_listing_surface(
            origin_url=candidate.origin_url,
            fetch_result=fetch_result if fetch_enabled else None,
        )
    else:
        result = fetch_result if fetch_result is not None else bounded_fetch(candidate.origin_url)
        item = evaluate_base_runtime(
            candidate,
            fetch_enabled=True,
            fetch_result=result,
        )
        listing = analyze_listing_surface(
            origin_url=candidate.origin_url,
            fetch_result=result,
        )

    evidence = dict(item.evidence)
    evidence["listing_surface_evidence"] = listing.to_json()
    return replace(item, evidence=evidence)


def build_listing_discovery_review(
    candidates: Iterable[OriginCandidate],
    *,
    reviewed_by: str,
    fetch_enabled: bool = True,
) -> ConnectorFeasibilityReview:
    items = tuple(
        evaluate_listing_discovery_runtime(
            candidate,
            fetch_enabled=fetch_enabled,
        )
        for candidate in candidates
    )
    return ConnectorFeasibilityReview(
        items=items,
        fetch_enabled=fetch_enabled,
        reviewed_by=reviewed_by,
    )


# Compatibility name for the probe agent while keeping the new layer explicit.
build_connector_feasibility_review = build_listing_discovery_review


__all__ = [
    "build_connector_feasibility_review",
    "build_listing_discovery_review",
    "evaluate_listing_discovery_runtime",
]
