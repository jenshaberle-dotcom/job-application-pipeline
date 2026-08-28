from __future__ import annotations

import argparse

from scripts.run_origin_source_discovery_agent import (
    collect_search_results,
    connect,
    http_probe,
    load_candidate,
    load_market_evidence_urls,
)
from src.search_intelligence.origin_candidate_plan_v2 import generate_company_url_candidates_v2
from src.search_intelligence.origin_source_discovery_agent import (
    discover_origin_source,
    result_to_json,
)


def run_for_company(args: argparse.Namespace, company_key: str) -> dict[str, object]:
    """Run the existing authority/scoring model with the breadth-first V2 plan."""

    with connect() as conn:
        candidate = load_candidate(conn, company_key)
        market_urls = load_market_evidence_urls(
            conn,
            company_key,
            limit=args.market_evidence_limit,
        )

    search_results = collect_search_results(
        args,
        company_key=str(candidate["company_key"]),
        company_name=str(candidate["company_name"]),
    )

    generated = generate_company_url_candidates_v2(
        company_key=str(candidate["company_key"]),
        company_name=str(candidate["company_name"]),
        source_family_candidate=str(candidate.get("source_family_candidate") or ""),
        max_candidates=args.max_candidates,
    )

    result = discover_origin_source(
        company_key=str(candidate["company_key"]),
        company_name=str(candidate["company_name"]),
        source_family_candidate=str(candidate.get("source_family_candidate") or ""),
        market_evidence_urls=market_urls,
        search_result_candidates=generated,
        search_results=search_results,
        target_location=args.target_location,
        probe=None
        if args.no_probe
        else (lambda url: http_probe(url, timeout_seconds=args.timeout_seconds)),
        # Prevent the legacy depth-first generator from contaminating the A/B run.
        max_generated_candidates=0,
    )

    payload = result_to_json(result)
    payload["candidate_id"] = candidate["id"]
    payload["candidate_status"] = candidate.get("status")
    payload["candidate_risk_level"] = candidate.get("risk_level")
    payload["candidate_url_before"] = candidate.get("candidate_url")
    payload["market_evidence_url_count"] = len(market_urls)
    payload["search_result_count"] = len(search_results)
    payload["search_provider"] = (
        ",".join(provider for provider in args.search_provider if provider != "none")
        or "none"
    )
    payload["probe_enabled"] = not args.no_probe
    payload["origin_candidate_planner"] = "breadth_first_v2"
    payload["generated_candidate_count"] = len(generated)
    payload["generated_candidates"] = [
        {
            "url": item.url,
            "reason": item.reason,
            "source_priority": item.source_priority,
        }
        for item in generated
    ]
    return payload
