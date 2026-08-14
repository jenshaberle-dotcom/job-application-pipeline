"""Run the deterministic Listing Discovery station for LLM-BOOST-001.

This entry point reuses the existing S7N candidate loader/persistence contract and
adds the Listing Surface Evidence projection. It performs bounded HTTP reads
only; Tavily/model execution belongs to a later separately admitted booster
slice after the deterministic station has classified a real external gap.
"""

from __future__ import annotations

import argparse
from typing import Sequence

from scripts import run_connector_feasibility_probe_agent as legacy
from src.search_intelligence.listing_discovery_runtime import (
    build_listing_discovery_review,
)

BOUNDARY = (
    "bounded HTTP read only; no Tavily, no LLM, no connector build, no connector "
    "registration, no source activation, no Bronze/Silver/Gold write, no ranking, "
    "no application write, no scheduler change"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic LLM-BOOST-001 Listing Discovery evidence fusion."
    )
    parser.add_argument("--company-key", help="Run probe for one company key.")
    parser.add_argument(
        "--include-missing-url",
        action="store_true",
        help="Include candidates without candidate_url.",
    )
    parser.add_argument("--reviewed-by", default="listing_discovery_deterministic")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Disable HTTP fetch; provider escalation remains ineligible.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist the review through the existing connector-feasibility evidence tables.",
    )
    return parser.parse_args(argv)


def _print_listing_projection(review) -> None:  # type: ignore[no-untyped-def]
    print("LLM-BOOST-001 Listing Discovery · deterministic station")
    print(f"boundary: {BOUNDARY}")
    print("---")
    for item in review.items:
        raw = item.evidence.get("listing_surface_evidence") or {}
        print(
            f"- {item.candidate.company_name} [{item.candidate.company_key}] | "
            f"listing={raw.get('classification', 'missing')} | "
            f"current_jobs={raw.get('current_job_url_count', 0)} | "
            f"external_search_gap={raw.get('external_search_gap', False)} | "
            f"next={raw.get('next_action', '-')}"
        )
        print(f"  fingerprint: {raw.get('evidence_fingerprint', '-')}")
        for url in (raw.get("current_job_urls") or [])[:3]:
            print(f"  current_job: {url}")
        for url in (raw.get("route_candidates") or [])[:3]:
            print(f"  route_candidate: {url}")
        for url in (raw.get("delegated_route_candidates") or [])[:3]:
            print(f"  delegated_candidate: {url}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    with legacy.connect() as conn:
        candidates = legacy.load_candidates(
            conn,
            company_key=args.company_key,
            include_missing_url=args.include_missing_url,
        )
        review = build_listing_discovery_review(
            candidates,
            reviewed_by=args.reviewed_by,
            fetch_enabled=not args.no_fetch,
        )
        persisted_review_id = None
        if args.write:
            scope = args.company_key or (
                "all_candidates"
                if args.include_missing_url
                else "selected_origin_candidates"
            )
            persisted_review_id = legacy.persist_review(conn, review, scope=scope)

    legacy.print_review(review, persisted_review_id=persisted_review_id)
    print("---")
    _print_listing_projection(review)
    if not args.write:
        print(
            "NEXT: use deterministic next_action; only explicit external_search_gap "
            "may enter a later Tavily/model booster slice."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
