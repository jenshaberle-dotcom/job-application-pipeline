"""Probe StepStone logical-query transport semantics after an explicit cooldown.

The probe compares the same five-company filter set in dominance and reverse
orders across candidate URL transports. A transport passes only when both
permutations preserve the intended query, remain leak-free, and return a full
page. One successful ordering is never treated as a production policy.

Boundaries: maximum eight page-one requests, no pagination, no detail pages,
no database writes, no candidates, no providers, no source activation, no
scheduler mutation, and no application action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from scripts.run_stepstone_aba_filter_refill_probe import (
    PAGE_CARD_LIMIT,
    classify_page,
    company_distribution,
    extract_page_title,
    raw_job_item_marker_count,
    serialize_card,
)
from scripts.run_stepstone_filter_matrix_probe import (
    RequestBudget,
    fetch_with_budget,
    select_current_a0_candidates,
)
from src.connectors.stepstone import REQUEST_TIMEOUT_SECONDS, USER_AGENT
from src.connectors.stepstone_result_cards import extract_result_card_fields
from src.search_intelligence.stepstone_company_discovery_cycle import build_not_query
from src.search_intelligence.stepstone_query_transport import (
    SUPPORTED_TRANSPORTS,
    StepStoneQueryTransport,
    assess_permutation_pair,
    assess_transport_integrity,
    build_query_transport,
)

DEFAULT_MAX_REQUESTS = 8
DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_COMPANY_COUNT = 5
DEFAULT_NOT_BEFORE_UTC = "2026-08-03T04:26:00+00:00"
APPROVAL_TOKEN = "run_stepstone_query_transport_probe_after_cooldown"


def parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone offset")
    return parsed.astimezone(UTC)


def enforce_execution_gate(
    *,
    approval_token: str,
    not_before_utc: str,
    now: datetime | None = None,
) -> datetime:
    if approval_token != APPROVAL_TOKEN:
        raise SystemExit(
            "Live probe blocked: exact --approval-token is required."
        )
    try:
        not_before = parse_aware_datetime(not_before_utc)
    except ValueError as exc:
        raise SystemExit(f"Invalid --not-before-utc: {exc}") from exc
    reference = (now or datetime.now(UTC)).astimezone(UTC)
    if reference < not_before:
        raise SystemExit(
            "Live probe blocked by cooldown until "
            f"{not_before.isoformat()} (now={reference.isoformat()})."
        )
    return not_before


def fetch_explicit_transport_page(
    *,
    budget: RequestBudget,
    session: requests.Session,
    label: str,
    transport: StepStoneQueryTransport,
    filter_aliases: list[str],
    candidate_keys: list[str],
    artifact_dir: Path,
    delay_seconds: float,
) -> dict[str, Any]:
    if budget.used > 0:
        time.sleep(delay_seconds)
    budget.consume(label)

    response = session.get(
        transport.requested_url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    response.raise_for_status()
    raw_html = response.text
    cards = extract_result_card_fields(
        raw_html=raw_html,
        final_url=response.url,
    )[:PAGE_CARD_LIMIT]
    serialized_cards = [serialize_card(card) for card in cards]
    html_path = artifact_dir / f"{label}.html"
    html_path.write_text(raw_html, encoding="utf-8")

    leakage_by_company = {
        key: sum(
            1
            for card in serialized_cards
            if card.get("company_key") == key
        )
        for key in candidate_keys
    }
    integrity = assess_transport_integrity(
        transport=transport,
        final_url=response.url,
    )
    return {
        "label": label,
        "transport_mode": transport.mode,
        "intended_query": transport.intended_query,
        "filter_aliases": filter_aliases,
        "requested_url": transport.requested_url,
        "final_url": response.url,
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "elapsed_seconds": response.elapsed.total_seconds(),
        "html_bytes": len(response.content),
        "html_sha256": hashlib.sha256(response.content).hexdigest(),
        "page_title": extract_page_title(raw_html),
        "raw_job_item_marker_count": raw_job_item_marker_count(raw_html),
        "parsed_card_count": len(serialized_cards),
        "page_type": classify_page(
            raw_html=raw_html,
            parsed_card_count=len(serialized_cards),
        ),
        "company_distribution": company_distribution(serialized_cards),
        "leakage_by_company": leakage_by_company,
        "leakage_count": sum(leakage_by_company.values()),
        "cards": serialized_cards,
        "html_artifact": str(html_path),
        **integrity,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-term", default="Machine Learning Engineer")
    parser.add_argument("--location", default="Hannover")
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    parser.add_argument("--not-before-utc", default=DEFAULT_NOT_BEFORE_UTC)
    parser.add_argument("--approval-token", required=True)
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
    if args.max_requests < DEFAULT_MAX_REQUESTS:
        raise SystemExit(
            f"--max-requests must be at least {DEFAULT_MAX_REQUESTS} for A0, "
            "six transport requests, and A1"
        )
    not_before = enforce_execution_gate(
        approval_token=args.approval_token,
        not_before_utc=args.not_before_utc,
    )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = args.artifact_dir / f"stepstone_query_transport_{stamp}"
    artifact_dir.mkdir(parents=True, exist_ok=False)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT.replace(
                "connector",
                "query-transport-contract-proof",
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
            "five-filter transport validation is not possible."
        )

    dominance_aliases = [str(item["filter_alias"]) for item in candidates]
    reverse_aliases = list(reversed(dominance_aliases))
    candidate_keys = [str(item["company_key"]) for item in candidates]
    orders = (
        ("dominance", dominance_aliases),
        ("reverse", reverse_aliases),
    )

    pages: dict[str, Any] = {"a0": a0}
    transport_results: list[dict[str, Any]] = []
    for mode in SUPPORTED_TRANSPORTS:
        permutation_pages: list[dict[str, Any]] = []
        for order_name, aliases in orders:
            intended_query = build_not_query(args.search_term, aliases)
            transport = build_query_transport(
                mode=mode,
                base_search_term=args.search_term,
                location=args.location,
                intended_query=intended_query,
            )
            label = f"{mode}_{order_name}"
            page = fetch_explicit_transport_page(
                budget=budget,
                session=session,
                label=label,
                transport=transport,
                filter_aliases=aliases,
                candidate_keys=candidate_keys,
                artifact_dir=artifact_dir,
                delay_seconds=args.delay_seconds,
            )
            pages[label] = page
            permutation_pages.append(page)

        contract = assess_permutation_pair(
            permutation_pages[0],
            permutation_pages[1],
            page_card_limit=PAGE_CARD_LIMIT,
        )
        transport_results.append(
            {
                "transport_mode": mode,
                "dominance": permutation_pages[0],
                "reverse": permutation_pages[1],
                "contract": contract,
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
    pages["a1"] = a1

    passing = [
        item["transport_mode"]
        for item in transport_results
        if item["contract"]["contract_pass"]
    ]
    diagnosis = (
        "query_transport_contract_candidate_found"
        if passing
        else "multi_not_transport_semantics_unvalidated"
    )
    payload = {
        "schema_version": "pipeline.stepstone.query_transport_probe.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "not_before_utc": not_before.isoformat(),
        "search_term": args.search_term,
        "location": args.location,
        "request_count": budget.used,
        "request_budget": budget.maximum,
        "page_card_limit": PAGE_CARD_LIMIT,
        "candidates": candidates,
        "transport_results": transport_results,
        "diagnosis": {
            "primary_diagnosis": diagnosis,
            "passing_transport_candidates": passing,
            "production_adoption_allowed": False,
            "reason": (
                "A passing result identifies a candidate transport for review and "
                "repeat validation only. No URL transport or ordering policy is "
                "automatically adopted by this diagnostic."
            ),
        },
        "baseline_control": {
            "a0_cards": a0["parsed_card_count"],
            "a1_cards": a1["parsed_card_count"],
        },
        "boundaries": {
            "page_one_only": True,
            "maximum_requests": DEFAULT_MAX_REQUESTS,
            "not_before_gate_enforced": True,
            "approval_token_required": True,
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

    print("StepStone query transport contract probe")
    print(f"artifact: {result_path}")
    print(f"requests: {budget.used}/{budget.maximum}")
    for item in transport_results:
        contract = item["contract"]
        print(
            f"- {item['transport_mode']}: {contract['diagnosis']} | "
            f"dominance={contract['first_card_count']}/25 | "
            f"reverse={contract['second_card_count']}/25 | "
            f"contract_pass={contract['contract_pass']}"
        )
    print(f"diagnosis: {diagnosis}")
    print("production_adoption_allowed: false")
    print("RESULT: STEPSTONE_QUERY_TRANSPORT_PROBE_COMPLETED")


if __name__ == "__main__":
    main()
