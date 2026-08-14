"""Listing-specific progress identity for LLM-BOOST-001.

Origin discovery intentionally strips URL queries because the product target is
a stable career origin. Listing discovery cannot reuse that identity rule:
query parameters can be the actual job/listing identity on current jobboards.
This ledger removes only obvious tracking parameters while preserving functional
query keys and prevents repeated provider/fetch work on unchanged hypotheses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse
import re

from src.search_intelligence.connector_feasibility import (
    KNOWN_AGGREGATOR_DOMAINS,
    SOCIAL_OR_EXTERNAL_NOISE_DOMAINS,
    is_public_https_origin_url,
    is_technical_or_asset_url,
)
from src.search_intelligence.origin_url_policy import has_disallowed_source_url_shape

_TRACKING_QUERY_KEYS = {
    "gclid",
    "fbclid",
    "msclkid",
    "ref",
    "referrer",
    "source",
}


def normalize_listing_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "").strip().lower())


def normalize_listing_candidate_url(url: str) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().strip(".")
    if parsed.scheme.lower() != "https" or not host:
        return None
    if not is_public_https_origin_url(raw):
        return None
    if host in KNOWN_AGGREGATOR_DOMAINS or host in SOCIAL_OR_EXTERNAL_NOISE_DOMAINS:
        return None
    if is_technical_or_asset_url(raw):
        return None
    if has_disallowed_source_url_shape(raw) is not None:
        return None

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query_pairs = []
    for key, value in parse_qsl(parsed.query or "", keep_blank_values=True):
        normalized_key = key.strip().lower()
        if normalized_key.startswith("utm_") or normalized_key in _TRACKING_QUERY_KEYS:
            continue
        query_pairs.append((key, value))
    query = urlencode(sorted(query_pairs))
    return parsed._replace(
        scheme="https",
        netloc=host,
        path=path,
        params="",
        query=query,
        fragment="",
    ).geturl()


@dataclass
class ListingProgressLedger:
    attempted_queries: set[str] = field(default_factory=set)
    attempted_urls: set[str] = field(default_factory=set)
    observed_domains: set[str] = field(default_factory=set)

    def novel_queries(self, queries: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        for raw in queries:
            normalized = normalize_listing_query(raw)
            if not normalized or normalized in self.attempted_queries:
                continue
            self.attempted_queries.add(normalized)
            result.append(str(raw).strip())
        return tuple(result)

    def novel_urls(self, urls: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        for raw in urls:
            normalized = normalize_listing_candidate_url(raw)
            if normalized is None or normalized in self.attempted_urls:
                continue
            self.attempted_urls.add(normalized)
            host = (urlparse(normalized).hostname or "").lower()
            if host:
                self.observed_domains.add(host)
            result.append(normalized)
        return tuple(result)

    def clone(self) -> "ListingProgressLedger":
        return ListingProgressLedger(
            attempted_queries=set(self.attempted_queries),
            attempted_urls=set(self.attempted_urls),
            observed_domains=set(self.observed_domains),
        )

    def to_json(self) -> dict[str, object]:
        return {
            "attempted_queries": sorted(self.attempted_queries),
            "attempted_urls": sorted(self.attempted_urls),
            "observed_domains": sorted(self.observed_domains),
        }


__all__ = [
    "ListingProgressLedger",
    "normalize_listing_candidate_url",
    "normalize_listing_query",
]
