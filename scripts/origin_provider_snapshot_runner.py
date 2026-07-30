"""Run origin discovery from an immutable fingerprint-bound projection row.

This module intentionally performs no database access. The private runtime loads
its complete bounded projection once, verifies the dispatch fingerprint, and then
uses these helpers for all provider calls and HTTP probes.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Iterable, Mapping

from scripts.run_origin_source_discovery_agent import (
    http_probe,
    load_search_results_json,
    web_search,
)
from src.search_intelligence.origin_source_discovery_agent import (
    OriginSearchResult,
    discover_origin_source,
    generate_search_query_hints,
    result_to_json,
)

RequestAttemptObserver = Callable[[str, str], None]


def _market_evidence_urls(row: Mapping[str, object]) -> list[str]:
    raw = row.get("market_evidence_urls")
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def collect_snapshot_search_results(
    args: argparse.Namespace,
    *,
    company_key: str,
    company_name: str,
    request_attempt_observer: RequestAttemptObserver | None = None,
) -> list[OriginSearchResult]:
    """Collect provider results without consulting PostgreSQL."""

    results: list[OriginSearchResult] = []
    if args.search_results_json:
        results.extend(
            load_search_results_json(Path(args.search_results_json), company_key=company_key)
        )

    providers = [provider for provider in args.search_provider if provider != "none"]
    if not providers:
        return results

    queries = list(
        generate_search_query_hints(
            company_name=company_name,
            company_key=company_key,
            target_location=args.target_location,
        )
    )[: args.search_query_limit]

    for provider in providers:
        for query in queries:
            if request_attempt_observer is not None:
                request_attempt_observer(provider, query)
            results.extend(
                web_search(
                    query,
                    provider=provider,
                    max_results=args.search_max_results,
                    timeout_seconds=args.search_timeout_seconds,
                    search_depth=args.search_depth,
                )
            )
    return results


def run_for_projection_row(
    args: argparse.Namespace,
    row: Mapping[str, object],
    *,
    request_attempt_observer: RequestAttemptObserver | None = None,
) -> dict[str, object]:
    """Run one company entirely from a pre-verified projection row."""

    company_key = str(row["company_key"])
    company_name = str(row.get("company_name") or "")
    market_urls = _market_evidence_urls(row)
    search_results = collect_snapshot_search_results(
        args,
        company_key=company_key,
        company_name=company_name,
        request_attempt_observer=request_attempt_observer,
    )

    result = discover_origin_source(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=str(row.get("source_family_candidate") or ""),
        market_evidence_urls=market_urls,
        search_results=search_results,
        target_location=args.target_location,
        probe=None
        if args.no_probe
        else (lambda url: http_probe(url, timeout_seconds=args.timeout_seconds)),
        max_generated_candidates=args.max_candidates,
    )

    payload = result_to_json(result)
    payload["candidate_id"] = row["candidate_id"]
    payload["candidate_status"] = row.get("status")
    payload["candidate_risk_level"] = row.get("risk_level")
    payload["candidate_url_before"] = row.get("candidate_url")
    payload["market_evidence_url_count"] = len(market_urls)
    payload["search_result_count"] = len(search_results)
    payload["search_provider"] = (
        ",".join(provider for provider in args.search_provider if provider != "none")
        or "none"
    )
    payload["search_results"] = [
        {
            "provider": item.provider,
            "query": item.query,
            "title": item.title,
            "url": item.url,
        }
        for item in search_results
    ]
    payload["probe_enabled"] = not args.no_probe
    payload["projection_snapshot_used"] = True
    return payload
