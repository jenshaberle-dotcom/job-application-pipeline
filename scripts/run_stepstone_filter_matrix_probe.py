"""Diagnose StepStone NOT-filter term, interaction, and cardinality behavior.

The probe uses only page-one requests and local artifacts. It separates:

1. individual filter-term validity;
2. cumulative filter cardinality;
3. order sensitivity;
4. leave-one-out interaction effects.

It does not paginate, fetch detail pages, write PostgreSQL, create candidates,
call providers, activate sources, change schedulers, or generate applications.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from scripts.run_stepstone_aba_filter_refill_probe import (
    PAGE_CARD_LIMIT,
    company_distribution,
    fetch_page,
)
from src.connectors.stepstone import USER_AGENT
from src.search_intelligence.stepstone_company_discovery_cycle import (
    build_not_query,
    company_not_alias,
)

DEFAULT_MAX_COMPANIES = 5
DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_MAX_REQUESTS = 16
INTERPRETABLE_PAGE_TYPES = {
    "result_page_with_cards",
    "explicit_zero_results",
}


def select_current_a0_candidates(
    cards: list[dict[str, Any]],
    *,
    max_companies: int,
) -> list[dict[str, Any]]:
    """Select only the strongest companies observed in the current A0 page."""
    distribution = company_distribution(cards)
    candidates: list[dict[str, Any]] = []
    for rank, item in enumerate(distribution[:max_companies], start=1):
        alias = company_not_alias(
            str(item["company_key"]),
            str(item["company_name"]),
        )
        candidates.append(
            {
                **item,
                "rank": rank,
                "filter_alias": alias,
                "filter_alias_length": len(alias),
                "contains_parentheses": "(" in alias or ")" in alias,
                "word_count": len(alias.split()),
            }
        )
    return candidates


def page_company_count(page: dict[str, Any], company_key: str) -> int:
    return sum(
        1
        for card in page["cards"]
        if card.get("company_key") == company_key
    )


def summarize_probe(
    *,
    page: dict[str, Any],
    candidates: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    candidate_keys = [str(item["company_key"]) for item in candidates]
    leakage = {
        key: page_company_count(page, key)
        for key in candidate_keys
    }
    baseline_jobs = {str(card["job_key"]) for card in baseline["cards"]}
    page_jobs = {str(card["job_key"]) for card in page["cards"]}
    baseline_companies = {
        str(card["company_key"])
        for card in baseline["cards"]
        if card.get("company_key")
    }
    page_companies = {
        str(card["company_key"])
        for card in page["cards"]
        if card.get("company_key")
    }
    page_interpretable = page["page_type"] in INTERPRETABLE_PAGE_TYPES
    leakage_count = sum(leakage.values())

    if not page_interpretable:
        outcome = "indeterminate_page_type"
    elif leakage_count > 0:
        outcome = "filter_leakage"
    elif page["parsed_card_count"] == PAGE_CARD_LIMIT:
        outcome = "filter_effective_full_refill"
    elif page["parsed_card_count"] > 0:
        outcome = "filter_effective_partial_refill"
    else:
        outcome = "filter_effective_no_refill"

    return {
        "outcome": outcome,
        "filter_count": len(candidates),
        "filter_companies": candidates,
        "filter_aliases": [str(item["filter_alias"]) for item in candidates],
        "query_length": len(str(page["query"])),
        "requested_url_length": len(str(page["requested_url"])),
        "final_url_length": len(str(page["final_url"])),
        "page_type": page["page_type"],
        "parsed_card_count": page["parsed_card_count"],
        "raw_job_item_marker_count": page["raw_job_item_marker_count"],
        "leakage_by_company": leakage,
        "leakage_count": leakage_count,
        "new_job_count_vs_a0": len(page_jobs - baseline_jobs),
        "new_company_count_vs_a0": len(page_companies - baseline_companies),
        "retained_job_count_vs_a0": len(page_jobs & baseline_jobs),
        "html_sha256": page["html_sha256"],
        "html_bytes": page["html_bytes"],
        "page_title": page["page_title"],
        "html_artifact": page["html_artifact"],
    }


def first_cumulative_break(
    cumulative: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for result in cumulative:
        if result["outcome"] not in {
            "filter_effective_full_refill",
            "filter_effective_partial_refill",
        }:
            return result
    return None


def diagnose_matrix(
    *,
    individual: list[dict[str, Any]],
    cumulative: list[dict[str, Any]],
    reverse: dict[str, Any] | None,
    leave_one_out: list[dict[str, Any]],
) -> dict[str, Any]:
    individual_failures = [
        item
        for item in individual
        if item["outcome"] not in {
            "filter_effective_full_refill",
            "filter_effective_partial_refill",
        }
    ]
    broken = first_cumulative_break(cumulative)

    if individual_failures:
        return {
            "primary_diagnosis": "individual_filter_term_failure",
            "failed_individual_aliases": [
                item["filter_aliases"][0]
                for item in individual_failures
            ],
            "first_cumulative_break": broken,
            "evidence": (
                "At least one filter expression fails when used alone; "
                "cardinality is not the only cause."
            ),
        }

    if broken is None:
        return {
            "primary_diagnosis": "validated_through_requested_cardinality",
            "failed_individual_aliases": [],
            "first_cumulative_break": None,
            "evidence": (
                "Every individual and cumulative filter set remained interpretable, "
                "leak-free, and produced at least one card."
            ),
        }

    if reverse and reverse["outcome"] in {
        "filter_effective_full_refill",
        "filter_effective_partial_refill",
    }:
        return {
            "primary_diagnosis": "filter_order_sensitive",
            "failed_individual_aliases": [],
            "first_cumulative_break": broken,
            "evidence": (
                "The same filter set failed in dominance order but succeeded "
                "when the expression order was reversed."
            ),
        }

    successful_omissions = [
        item
        for item in leave_one_out
        if item["outcome"] in {
            "filter_effective_full_refill",
            "filter_effective_partial_refill",
        }
    ]
    omitted_aliases = [
        str(item["omitted_company"]["filter_alias"])
        for item in successful_omissions
    ]

    if len(successful_omissions) == len(leave_one_out) and leave_one_out:
        return {
            "primary_diagnosis": "cardinality_or_total_query_complexity_boundary",
            "failed_individual_aliases": [],
            "first_cumulative_break": broken,
            "successful_omission_aliases": omitted_aliases,
            "evidence": (
                "All individual terms work, the full set fails, and every set "
                "with one term removed recovers. The evidence points to the total "
                "filter count or aggregate query length/complexity."
            ),
        }

    if successful_omissions:
        return {
            "primary_diagnosis": "specific_filter_interaction",
            "failed_individual_aliases": [],
            "first_cumulative_break": broken,
            "successful_omission_aliases": omitted_aliases,
            "evidence": (
                "All terms work alone, but only specific omissions recover the "
                "failed cumulative set, indicating an interaction involving those terms."
            ),
        }

    return {
        "primary_diagnosis": "unresolved_higher_order_or_page_behavior",
        "failed_individual_aliases": [],
        "first_cumulative_break": broken,
        "successful_omission_aliases": [],
        "evidence": (
            "Terms work alone, but reverse order and leave-one-out controls did not "
            "restore a usable page. More targeted alias or syntax experiments are required."
        ),
    }


class RequestBudget:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self.used = 0

    def consume(self, label: str) -> None:
        if self.used >= self.maximum:
            raise RuntimeError(
                f"Request budget exhausted before {label}: {self.used}/{self.maximum}"
            )
        self.used += 1


def fetch_with_budget(
    *,
    budget: RequestBudget,
    session: requests.Session,
    label: str,
    query: str,
    location: str,
    artifact_dir: Path,
    delay_seconds: float,
) -> dict[str, Any]:
    if budget.used > 0:
        time.sleep(delay_seconds)
    budget.consume(label)
    return fetch_page(
        session=session,
        label=label,
        query=query,
        location=location,
        artifact_dir=artifact_dir,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-term", default="Machine Learning Engineer")
    parser.add_argument("--location", default="Hannover")
    parser.add_argument("--max-companies", type=int, default=DEFAULT_MAX_COMPANIES)
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
    if args.max_companies < 2:
        raise SystemExit("--max-companies must be at least 2")
    if args.max_companies > 5:
        raise SystemExit("--max-companies is capped at 5 for this diagnostic")
    if args.delay_seconds < 0:
        raise SystemExit("--delay-seconds must be non-negative")
    minimum_budget = 2 * args.max_companies + 1
    if args.max_requests < minimum_budget:
        raise SystemExit(
            f"--max-requests must be at least {minimum_budget} for baseline, "
            "individual, cumulative, and control requests"
        )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = args.artifact_dir / f"stepstone_filter_matrix_{stamp}"
    artifact_dir.mkdir(parents=True, exist_ok=False)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT.replace(
                "connector",
                "filter-term-cardinality-matrix-proof",
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
        max_companies=args.max_companies,
    )
    if len(candidates) < args.max_companies:
        raise SystemExit(
            f"A0 produced only {len(candidates)} company-bearing candidates; "
            f"cannot test requested cardinality {args.max_companies}"
        )

    individual: list[dict[str, Any]] = []
    individual_pages: dict[int, dict[str, Any]] = {}
    for candidate in candidates:
        rank = int(candidate["rank"])
        query = build_not_query(
            args.search_term,
            [str(candidate["filter_alias"])],
        )
        page = fetch_with_budget(
            budget=budget,
            session=session,
            label=f"individual_{rank}",
            query=query,
            location=args.location,
            artifact_dir=artifact_dir,
            delay_seconds=args.delay_seconds,
        )
        individual_pages[rank] = page
        individual.append(
            summarize_probe(
                page=page,
                candidates=[candidate],
                baseline=a0,
            )
        )

    cumulative: list[dict[str, Any]] = [individual[0]]
    for cardinality in range(2, len(candidates) + 1):
        selected = candidates[:cardinality]
        query = build_not_query(
            args.search_term,
            [str(item["filter_alias"]) for item in selected],
        )
        page = fetch_with_budget(
            budget=budget,
            session=session,
            label=f"cumulative_{cardinality}",
            query=query,
            location=args.location,
            artifact_dir=artifact_dir,
            delay_seconds=args.delay_seconds,
        )
        cumulative.append(
            summarize_probe(
                page=page,
                candidates=selected,
                baseline=a0,
            )
        )

    broken = first_cumulative_break(cumulative)
    reverse_result: dict[str, Any] | None = None
    leave_one_out: list[dict[str, Any]] = []

    if broken is not None:
        break_count = int(broken["filter_count"])
        break_candidates = candidates[:break_count]
        reverse_candidates = list(reversed(break_candidates))
        reverse_query = build_not_query(
            args.search_term,
            [str(item["filter_alias"]) for item in reverse_candidates],
        )
        reverse_page = fetch_with_budget(
            budget=budget,
            session=session,
            label=f"reverse_{break_count}",
            query=reverse_query,
            location=args.location,
            artifact_dir=artifact_dir,
            delay_seconds=args.delay_seconds,
        )
        reverse_result = summarize_probe(
            page=reverse_page,
            candidates=reverse_candidates,
            baseline=a0,
        )

        # The cumulative k-1 probe already represents omission of the newest term.
        if break_count > 1:
            prior = cumulative[break_count - 2]
            leave_one_out.append(
                {
                    **prior,
                    "omitted_company": break_candidates[-1],
                    "reused_existing_probe": True,
                }
            )

        for omitted_index in range(0, max(0, break_count - 1)):
            selected = [
                item
                for index, item in enumerate(break_candidates)
                if index != omitted_index
            ]
            query = build_not_query(
                args.search_term,
                [str(item["filter_alias"]) for item in selected],
            )
            page = fetch_with_budget(
                budget=budget,
                session=session,
                label=f"leave_one_out_{break_count}_omit_{omitted_index + 1}",
                query=query,
                location=args.location,
                artifact_dir=artifact_dir,
                delay_seconds=args.delay_seconds,
            )
            result = summarize_probe(
                page=page,
                candidates=selected,
                baseline=a0,
            )
            leave_one_out.append(
                {
                    **result,
                    "omitted_company": break_candidates[omitted_index],
                    "reused_existing_probe": False,
                }
            )

    a1 = fetch_with_budget(
        budget=budget,
        session=session,
        label="a1_baseline_control",
        query=args.search_term,
        location=args.location,
        artifact_dir=artifact_dir,
        delay_seconds=args.delay_seconds,
    )

    diagnosis = diagnose_matrix(
        individual=individual,
        cumulative=cumulative,
        reverse=reverse_result,
        leave_one_out=leave_one_out,
    )
    payload = {
        "schema_version": "pipeline.stepstone.filter_matrix_probe.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "search_term": args.search_term,
        "location": args.location,
        "page_card_limit": PAGE_CARD_LIMIT,
        "request_budget": {
            "maximum": budget.maximum,
            "used": budget.used,
        },
        "boundaries": {
            "page_one_only": True,
            "max_companies": args.max_companies,
            "no_pagination": True,
            "no_detail_pages": True,
            "no_database_write": True,
            "no_candidate_creation": True,
            "no_provider_call": True,
            "no_source_activation": True,
            "no_scheduler_change": True,
            "no_application_action": True,
        },
        "a0": a0,
        "a0_candidates": candidates,
        "individual": individual,
        "cumulative": cumulative,
        "reverse_at_first_break": reverse_result,
        "leave_one_out_at_first_break": leave_one_out,
        "a1": a1,
        "a0_a1": {
            "a0_card_count": a0["parsed_card_count"],
            "a1_card_count": a1["parsed_card_count"],
            "a0_page_type": a0["page_type"],
            "a1_page_type": a1["page_type"],
            "a0_a1_job_overlap_count": len(
                {str(card["job_key"]) for card in a0["cards"]}
                & {str(card["job_key"]) for card in a1["cards"]}
            ),
        },
        "diagnosis": diagnosis,
    }
    result_path = artifact_dir / "result.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("StepStone filter term/cardinality matrix probe")
    print(f"artifact: {result_path}")
    print(f"requests: {budget.used}/{budget.maximum}")
    print("A0 candidates:")
    for item in candidates:
        print(
            f"- #{item['rank']} {item['company_name']} | "
            f"cards={item['card_count']} | alias={item['filter_alias']!r}"
        )

    print("individual outcomes:")
    for result in individual:
        print(
            f"- {result['filter_aliases'][0]!r}: "
            f"{result['outcome']} | cards={result['parsed_card_count']}/25 | "
            f"leakage={result['leakage_count']}"
        )

    print("cumulative outcomes:")
    for result in cumulative:
        print(
            f"- n={result['filter_count']}: {result['outcome']} | "
            f"cards={result['parsed_card_count']}/25 | "
            f"leakage={result['leakage_count']} | "
            f"query_length={result['query_length']} | "
            f"url_length={result['final_url_length']}"
        )

    if reverse_result is not None:
        print(
            "reverse_at_break: "
            f"{reverse_result['outcome']} | "
            f"cards={reverse_result['parsed_card_count']}/25"
        )
    for item in leave_one_out:
        omitted = item["omitted_company"]
        print(
            "leave_one_out: omit="
            f"{omitted['filter_alias']!r} | {item['outcome']} | "
            f"cards={item['parsed_card_count']}/25"
        )

    print("diagnosis:", diagnosis["primary_diagnosis"])
    print("evidence:", diagnosis["evidence"])
    print("RESULT: STEPSTONE_FILTER_MATRIX_PROBE_COMPLETED")


if __name__ == "__main__":
    main()
