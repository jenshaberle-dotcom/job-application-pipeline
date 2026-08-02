"""Run a bounded StepStone A0-B-A1 page-one filter/refill proof.

The probe performs exactly three defensive page-one requests:

A0: baseline query without company exclusion.
B:  the same query excluding exactly one dominant A0 company.
A1: baseline query repeated as a temporal control.

It writes local JSON and HTML artifacts only. It does not write to PostgreSQL,
create candidates, paginate, open detail pages, call a provider, activate a
source, change a scheduler, or generate an application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from src.connectors.stepstone import (
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    build_stepstone_search_url,
)
from src.connectors.stepstone_result_cards import (
    ResultCardFields,
    extract_result_card_fields,
)
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.stepstone_company_discovery_cycle import (
    build_not_query,
    company_not_alias,
)

PAGE_CARD_LIMIT = 25
DEFAULT_DELAY_SECONDS = 2.0

ZERO_RESULT_MARKERS = (
    "keine jobs gefunden",
    "keine passenden jobs",
    "keine passenden stellenangebote",
    "0 jobs",
    "0 stellenangebote",
    "no jobs found",
)
CHALLENGE_MARKERS = (
    "verify you are human",
    "access denied",
    "unusual traffic",
    "cf-chl-",
    "captcha",
    "robot or human",
)


def extract_page_title(raw_html: str) -> str | None:
    match = re.search(
        r"<title\b[^>]*>(.*?)</title>",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip()
    return value or None


def raw_job_item_marker_count(raw_html: str) -> int:
    return len(
        re.findall(
            r"<article\b[^>]*data-testid\s*=\s*(['\"])job-item\1",
            raw_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )


def classify_page(*, raw_html: str, parsed_card_count: int) -> str:
    if parsed_card_count > 0:
        return "result_page_with_cards"

    lowered = raw_html.lower()
    if any(marker in lowered for marker in CHALLENGE_MARKERS):
        return "challenge_or_block_page"
    if any(marker in lowered for marker in ZERO_RESULT_MARKERS):
        return "explicit_zero_results"
    if raw_job_item_marker_count(raw_html) > 0:
        return "parser_mismatch"
    return "unexpected_markup_or_empty_page"


def card_identity(card: ResultCardFields) -> str:
    if card.external_job_id:
        return f"stepstone:{card.external_job_id}"
    if card.detail_url:
        return card.detail_url
    raw = "|".join(
        [
            card.company or "",
            card.title or "",
            card.location or "",
        ]
    )
    return "fallback:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def serialize_card(card: ResultCardFields) -> dict[str, Any]:
    return {
        "position": card.index,
        "job_key": card_identity(card),
        "external_job_id": card.external_job_id,
        "title": card.title,
        "company": card.company,
        "company_key": normalize_company_key(card.company or ""),
        "location": card.location,
        "detail_url": card.detail_url,
    }


def company_distribution(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    names: dict[str, str] = {}
    for card in cards:
        key = str(card.get("company_key") or "")
        if not key:
            continue
        counts[key] += 1
        names.setdefault(key, str(card.get("company") or key))

    return [
        {
            "company_key": key,
            "company_name": names[key],
            "card_count": count,
        }
        for key, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def select_exclusion_company(
    *,
    cards: list[dict[str, Any]],
    explicit_company: str | None,
) -> dict[str, Any]:
    distribution = company_distribution(cards)
    if not distribution:
        raise RuntimeError("A0 contains no company-bearing result cards")

    if explicit_company:
        explicit_key = normalize_company_key(explicit_company)
        for item in distribution:
            if item["company_key"] == explicit_key:
                return {
                    **item,
                    "selection_mode": "explicit_a0_company",
                    "dominant_threshold_met": item["card_count"] >= 2,
                }
        raise RuntimeError(
            "The explicitly requested company is not present in A0: "
            + explicit_company
        )

    selected = distribution[0]
    return {
        **selected,
        "selection_mode": "strongest_a0_company",
        "dominant_threshold_met": selected["card_count"] >= 2,
    }


def page_company_count(page: dict[str, Any], company_key: str) -> int:
    return sum(
        1
        for card in page["cards"]
        if card.get("company_key") == company_key
    )


def fetch_page(
    *,
    session: requests.Session,
    label: str,
    query: str,
    location: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    requested_url = build_stepstone_search_url(
        search_term=query,
        search_location=location,
    )
    response = session.get(
        requested_url,
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

    return {
        "label": label,
        "query": query,
        "requested_url": requested_url,
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
        "cards": serialized_cards,
        "html_artifact": str(html_path),
    }


def compare_probe(
    *,
    a0: dict[str, Any],
    b: dict[str, Any],
    a1: dict[str, Any],
    excluded: dict[str, Any],
) -> dict[str, Any]:
    company_key = str(excluded["company_key"])
    a0_target_count = page_company_count(a0, company_key)
    b_target_count = page_company_count(b, company_key)
    a1_target_count = page_company_count(a1, company_key)

    a0_jobs = {str(card["job_key"]) for card in a0["cards"]}
    b_jobs = {str(card["job_key"]) for card in b["cards"]}
    a1_jobs = {str(card["job_key"]) for card in a1["cards"]}

    a0_companies = {
        str(card["company_key"])
        for card in a0["cards"]
        if card.get("company_key")
    }
    b_companies = {
        str(card["company_key"])
        for card in b["cards"]
        if card.get("company_key")
    }

    b_page_is_interpretable = b["page_type"] in {
        "result_page_with_cards",
        "explicit_zero_results",
    }
    if not b_page_is_interpretable:
        filter_answer = "indeterminate_page_type"
    elif b_target_count > 0:
        filter_answer = "no_excluded_company_leaked"
    elif a1_target_count > 0:
        filter_answer = "yes_confirmed_by_a0_b_a1"
    else:
        filter_answer = "likely_but_a1_did_not_reconfirm_company"

    if not b_page_is_interpretable:
        refill_answer = "indeterminate_page_type"
    elif b["parsed_card_count"] == PAGE_CARD_LIMIT:
        refill_answer = "yes_full_page_refill"
    elif b["parsed_card_count"] > 0:
        refill_answer = "partial_page_refill"
    else:
        refill_answer = "no_refill_observed"

    return {
        "filter_answer": filter_answer,
        "refill_answer": refill_answer,
        "excluded_company": excluded,
        "excluded_company_card_count": {
            "a0": a0_target_count,
            "b": b_target_count,
            "a1": a1_target_count,
        },
        "page_fill": {
            "a0": a0["parsed_card_count"],
            "b": b["parsed_card_count"],
            "a1": a1["parsed_card_count"],
            "page_limit": PAGE_CARD_LIMIT,
        },
        "new_job_count_b_vs_a0": len(b_jobs - a0_jobs),
        "new_company_count_b_vs_a0": len(b_companies - a0_companies),
        "retained_job_count_b_vs_a0": len(b_jobs & a0_jobs),
        "lost_job_count_b_vs_a0": len(a0_jobs - b_jobs),
        "a0_a1_job_overlap_count": len(a0_jobs & a1_jobs),
        "a0_a1_target_reconfirmed": a1_target_count > 0,
        "excluded_company_leakage_count": b_target_count,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-term", default="Data Engineer")
    parser.add_argument("--location", default="Hannover")
    parser.add_argument("--exclude-company")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
    )
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

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = args.artifact_dir / f"stepstone_aba_{stamp}"
    artifact_dir.mkdir(parents=True, exist_ok=False)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT.replace(
                "connector",
                "aba-filter-refill-proof",
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        }
    )

    a0 = fetch_page(
        session=session,
        label="a0_baseline",
        query=args.search_term,
        location=args.location,
        artifact_dir=artifact_dir,
    )
    excluded = select_exclusion_company(
        cards=a0["cards"],
        explicit_company=args.exclude_company,
    )
    excluded_alias = company_not_alias(
        str(excluded["company_key"]),
        str(excluded["company_name"]),
    )
    b_query = build_not_query(args.search_term, [excluded_alias])

    time.sleep(args.delay_seconds)
    b = fetch_page(
        session=session,
        label="b_single_company_not",
        query=b_query,
        location=args.location,
        artifact_dir=artifact_dir,
    )

    time.sleep(args.delay_seconds)
    a1 = fetch_page(
        session=session,
        label="a1_baseline_control",
        query=args.search_term,
        location=args.location,
        artifact_dir=artifact_dir,
    )

    verdict = compare_probe(a0=a0, b=b, a1=a1, excluded=excluded)
    payload = {
        "schema_version": "pipeline.stepstone.aba_filter_refill_probe.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "request_count": 3,
        "page_card_limit": PAGE_CARD_LIMIT,
        "search_term": args.search_term,
        "location": args.location,
        "delay_seconds": args.delay_seconds,
        "boundaries": {
            "page_one_only": True,
            "no_pagination": True,
            "no_detail_pages": True,
            "no_database_write": True,
            "no_candidate_creation": True,
            "no_provider_call": True,
            "no_source_activation": True,
            "no_scheduler_change": True,
            "no_application_action": True,
        },
        "pages": {"a0": a0, "b": b, "a1": a1},
        "verdict": verdict,
    }
    result_path = artifact_dir / "result.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("StepStone A0-B-A1 filter/refill proof")
    print(f"artifact: {result_path}")
    print(
        "excluded_company: "
        f"{excluded['company_name']} "
        f"(A0 cards={excluded['card_count']})"
    )
    print(
        "page_fill: "
        f"A0={a0['parsed_card_count']}/25, "
        f"B={b['parsed_card_count']}/25, "
        f"A1={a1['parsed_card_count']}/25"
    )
    print(
        "excluded_company_counts: "
        f"A0={verdict['excluded_company_card_count']['a0']}, "
        f"B={verdict['excluded_company_card_count']['b']}, "
        f"A1={verdict['excluded_company_card_count']['a1']}"
    )
    print(
        "variation: "
        f"new_jobs={verdict['new_job_count_b_vs_a0']}, "
        f"new_companies={verdict['new_company_count_b_vs_a0']}"
    )
    print(f"filter_answer: {verdict['filter_answer']}")
    print(f"refill_answer: {verdict['refill_answer']}")
    print("RESULT: STEPSTONE_ABA_FILTER_REFILL_PROBE_COMPLETED")


if __name__ == "__main__":
    main()
