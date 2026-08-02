"""Diagnose StepStone five-filter order sensitivity without adopting an order.

The probe selects the top five companies from the current A0 page and tests the
same five filter expressions in several deterministic orders. Different results
for the same filter set are treated as evidence that URL/query transport
semantics are unvalidated, not as a reason to create a production order policy.

Boundaries: page one only, local artifacts only, no PostgreSQL writes, no
pagination, no detail pages, no candidates, no providers, no scheduler changes.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from scripts.run_stepstone_filter_matrix_probe import (
    RequestBudget,
    fetch_with_budget,
    select_current_a0_candidates,
    summarize_probe,
)
from src.connectors.stepstone import USER_AGENT
from src.search_intelligence.stepstone_company_discovery_cycle import build_not_query

PAGE_CARD_LIMIT = 25
DEFAULT_MAX_REQUESTS = 8
DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_COMPANY_COUNT = 5
USABLE_OUTCOMES = {
    "filter_effective_full_refill",
    "filter_effective_partial_refill",
}


def _special_character_count(value: str) -> int:
    return sum(1 for char in value if not char.isalnum() and not char.isspace())


def build_order_strategies(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return distinct diagnostic orders for the same candidate set."""
    raw_strategies = [
        ("dominance_order", list(candidates)),
        ("reverse_dominance", list(reversed(candidates))),
        (
            "alias_length_ascending",
            sorted(
                candidates,
                key=lambda item: (
                    int(item["filter_alias_length"]),
                    int(item["rank"]),
                ),
            ),
        ),
        (
            "syntax_risk_ascending",
            sorted(
                candidates,
                key=lambda item: (
                    bool(item["contains_parentheses"]),
                    _special_character_count(str(item["filter_alias"])),
                    int(item["word_count"]),
                    int(item["filter_alias_length"]),
                    int(item["rank"]),
                ),
            ),
        ),
        (
            "dominant_company_last",
            list(candidates[1:]) + list(candidates[:1]),
        ),
    ]

    seen: set[tuple[str, ...]] = set()
    strategies: list[dict[str, Any]] = []
    for name, ordered in raw_strategies:
        aliases = tuple(str(item["filter_alias"]) for item in ordered)
        if aliases in seen:
            continue
        seen.add(aliases)
        strategies.append(
            {
                "name": name,
                "candidates": ordered,
                "aliases": list(aliases),
            }
        )
    return strategies


def diagnose_order_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify order evidence without recommending a production order."""
    counts = [int(item.get("parsed_card_count", 0)) for item in results]
    has_zero = any(count == 0 for count in counts)
    has_nonzero = any(count > 0 for count in counts)
    indeterminate = any(
        item["outcome"] == "indeterminate_page_type"
        for item in results
    )
    all_usable = bool(results) and all(
        item["outcome"] in USABLE_OUTCOMES
        for item in results
    )

    if has_zero and has_nonzero:
        primary = "same_filter_set_not_permutation_invariant"
        evidence = (
            "The same logical filter set produced both zero-card and non-zero-card "
            "responses when only expression order changed. URL/query transport "
            "semantics are therefore unvalidated."
        )
    elif indeterminate:
        primary = "five_filter_order_test_indeterminate"
        evidence = (
            "At least one response was technically indeterminate; no filter-count "
            "or ordering conclusion is permitted."
        )
    elif all_usable:
        primary = "orders_usable_but_transport_semantics_unvalidated"
        evidence = (
            "All tested orders produced usable pages, but this diagnostic does not "
            "prove that the logical query survived URL transport unchanged."
        )
    else:
        primary = "multi_not_transport_or_filter_semantics_unresolved"
        evidence = (
            "The order experiment did not establish stable logical filter semantics."
        )

    return {
        "primary_diagnosis": primary,
        "recommended_strategy": None,
        "recommended_alias_order": [],
        "production_order_policy_allowed": False,
        "working_strategy_count": sum(
            1 for item in results if item["outcome"] in USABLE_OUTCOMES
        ),
        "zero_card_strategy_count": sum(1 for count in counts if count == 0),
        "evidence": evidence,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-term", default="Machine Learning Engineer")
    parser.add_argument("--location", default="Hannover")
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.delay_seconds < 0:
        raise SystemExit("--delay-seconds must be non-negative")
    if args.max_requests < 4:
        raise SystemExit("--max-requests must be at least 4")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = args.artifact_dir / f"stepstone_full_filter_order_{stamp}"
    artifact_dir.mkdir(parents=True, exist_ok=False)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT.replace(
                "connector",
                "full-filter-order-diagnostic",
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        }
    )
    budget = RequestBudget(args.max_requests)

    a0 = fetch_with_budget(
        budget=budget,
        session=session,
        label="a0_baseline",
        query=args.search_term,
        location=args.location,
        artifact_dir=artifact_dir,
        delay_seconds=args.delay_seconds,
    )
    candidates = select_current_a0_candidates(
        a0["cards"],
        max_companies=DEFAULT_COMPANY_COUNT,
    )
    if len(candidates) < DEFAULT_COMPANY_COUNT:
        raise SystemExit(
            f"A0 produced only {len(candidates)} company-bearing candidates; "
            "five-filter validation is not possible."
        )

    strategies = build_order_strategies(candidates)
    required_requests = 2 + len(strategies)
    if args.max_requests < required_requests:
        raise SystemExit(
            f"--max-requests must be at least {required_requests} for this A0/order/A1 probe"
        )

    results: list[dict[str, Any]] = []
    pages: dict[str, dict[str, Any]] = {"a0": a0}
    for strategy in strategies:
        aliases = list(strategy["aliases"])
        query = build_not_query(args.search_term, aliases)
        label = f"order_{strategy['name']}"
        page = fetch_with_budget(
            budget=budget,
            session=session,
            label=label,
            query=query,
            location=args.location,
            artifact_dir=artifact_dir,
            delay_seconds=args.delay_seconds,
        )
        pages[strategy["name"]] = page
        summary = summarize_probe(
            page=page,
            candidates=list(strategy["candidates"]),
            baseline=a0,
        )
        results.append({**summary, "strategy_name": strategy["name"]})

    a1 = fetch_with_budget(
        budget=budget,
        session=session,
        label="a1_baseline_control",
        query=args.search_term,
        location=args.location,
        artifact_dir=artifact_dir,
        delay_seconds=args.delay_seconds,
    )
    pages["a1"] = a1

    a0_jobs = {str(card["job_key"]) for card in a0["cards"]}
    a1_jobs = {str(card["job_key"]) for card in a1["cards"]}
    diagnosis = diagnose_order_results(results)
    payload = {
        "schema_version": "pipeline.stepstone.full_filter_order_probe.v2",
        "created_at": datetime.now(UTC).isoformat(),
        "search_term": args.search_term,
        "location": args.location,
        "request_count": budget.used,
        "request_budget": budget.maximum,
        "company_count": DEFAULT_COMPANY_COUNT,
        "page_card_limit": PAGE_CARD_LIMIT,
        "candidates": candidates,
        "order_results": results,
        "baseline_control": {
            "a0_cards": a0["parsed_card_count"],
            "a1_cards": a1["parsed_card_count"],
            "a0_a1_job_overlap_count": len(a0_jobs & a1_jobs),
        },
        "diagnosis": diagnosis,
        "boundaries": {
            "page_one_only": True,
            "diagnostic_only": True,
            "production_order_policy_allowed": False,
            "no_pagination": True,
            "no_detail_pages": True,
            "no_database_write": True,
            "no_candidate_creation": True,
            "no_provider_call": True,
            "no_source_activation": True,
            "no_scheduler_change": True,
            "no_application_action": True,
        },
        "pages": pages,
    }
    result_path = artifact_dir / "result.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("StepStone full five-filter order diagnostic")
    print(f"artifact: {result_path}")
    print(f"requests: {budget.used}/{budget.maximum}")
    print("order outcomes:")
    for item in results:
        aliases = " -> ".join(item["filter_aliases"])
        print(
            f"- {item['strategy_name']}: {item['outcome']} | "
            f"cards={item['parsed_card_count']}/25 | leakage={item['leakage_count']}"
        )
        print(f"  order: {aliases}")
    print(f"diagnosis: {diagnosis['primary_diagnosis']}")
    print("recommended_strategy: None")
    print("production_order_policy_allowed: false")
    print(f"evidence: {diagnosis['evidence']}")
    print("RESULT: STEPSTONE_FULL_FILTER_ORDER_DIAGNOSTIC_COMPLETED")


if __name__ == "__main__":
    main()
