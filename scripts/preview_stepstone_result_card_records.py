from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.connectors.stepstone_result_cards import (  # noqa: E402
    RESULT_CARD_SELECTOR_DESCRIPTION,
    ResultCardFields,
    extract_stepstone_id_from_url,
    extract_result_card_fields,
)


SOURCE_NAME = "stepstone"
DEFAULT_URL = "https://www.stepstone.de/jobs/data-engineer/in-hannover"
REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_MAX_RECORDS = 3

USER_AGENT = (
    "job-application-pipeline-stepstone-record-preview/0.1 "
    "(local limited source evaluation; no crawling)"
)


def fetch_url(url: str) -> requests.Response:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }

    return requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )


def build_preview_record(
    card: ResultCardFields,
    final_search_url: str,
    requested_url: str,
    observed_at_utc: str,
) -> dict[str, Any]:
    detail_url_external_job_id = extract_stepstone_id_from_url(card.detail_url)

    external_job_id = (
        card.external_job_id
        if card.title_id_matches_article_id
        else None
    )

    return {
        "source_name": SOURCE_NAME,
        "source_url": card.detail_url or final_search_url,
        "external_job_id": external_job_id,
        "raw_data": {
            "search_context": {
                "requested_url": requested_url,
                "final_search_url": final_search_url,
            },
            "result_card": {
                "title": card.title,
                "company_name": card.company,
                "location": card.location,
                "detail_url": card.detail_url,
                "external_job_id_candidate": card.external_job_id,
                "publication_hint_text": card.publication_hint_text,
                "salary_hint_text": card.salary_hint_text,
                "remote_hint_text": card.remote_hint_text,
                "employment_type_hint_text": card.employment_type_hint_text,
            },
            "source_specific": {
                "article_external_job_id": card.external_job_id,
                "detail_url_external_job_id": detail_url_external_job_id,
                "raw_href": card.raw_href,
                "salary_ui_prompt_text": card.salary_ui_prompt_text,
                "card_html_bytes": card.card_html_bytes,
                "title_id_matches_article_id": card.title_id_matches_article_id,
                "data_at_fields": card.data_at_fields,
                "raw_card_text": card.raw_card_text,
            },
            "extraction": {
                "extracted_from": "search_result_page",
                "detail_page_fetched": False,
                "pagination_used": False,
                "database_write": False,
                "connector_mode": "limited_result_card_preview",
                "selector": RESULT_CARD_SELECTOR_DESCRIPTION,
                "selector_version": "stepstone_result_card_v1",
                "observed_at_utc": observed_at_utc,
            },
            "quality_signals": {
                "has_title": card.title is not None,
                "has_company": card.company is not None,
                "has_location": card.location is not None,
                "has_detail_url": card.detail_url is not None,
                "has_external_job_id_candidate": card.external_job_id is not None,
                "id_match": card.title_id_matches_article_id,
                "has_publication_hint": card.publication_hint_text is not None,
                "has_salary_hint": card.salary_hint_text is not None,
                "has_salary_ui_prompt": card.salary_ui_prompt_text is not None,
                "has_remote_hint": card.remote_hint_text is not None,
                "has_employment_type_hint": card.employment_type_hint_text is not None,
            },
        },
    }


def build_summary(
    cards: list[ResultCardFields],
    max_records: int,
) -> dict[str, Any]:
    total = len(cards)

    with_title = sum(1 for card in cards if card.title)
    with_company = sum(1 for card in cards if card.company)
    with_location = sum(1 for card in cards if card.location)
    with_detail_url = sum(1 for card in cards if card.detail_url)
    matching_ids = sum(1 for card in cards if card.title_id_matches_article_id)

    with_publication_hint = sum(1 for card in cards if card.publication_hint_text)
    with_salary_hint = sum(1 for card in cards if card.salary_hint_text)
    with_salary_ui_prompt = sum(1 for card in cards if card.salary_ui_prompt_text)
    with_remote_hint = sum(1 for card in cards if card.remote_hint_text)
    with_employment_type_hint = sum(
        1 for card in cards if card.employment_type_hint_text
    )

    return {
        "result_cards": total,
        "preview_records_printed": min(total, max_records),
        "max_preview_records": max_records,
        "with_title": with_title,
        "with_company": with_company,
        "with_location": with_location,
        "with_detail_url": with_detail_url,
        "matching_external_job_ids": matching_ids,
        "with_publication_hint": with_publication_hint,
        "with_salary_hint": with_salary_hint,
        "with_salary_ui_prompt": with_salary_ui_prompt,
        "with_remote_hint": with_remote_hint,
        "with_employment_type_hint": with_employment_type_hint,
        "title_coverage": with_title / total if total else 0,
        "company_coverage": with_company / total if total else 0,
        "location_coverage": with_location / total if total else 0,
        "detail_url_coverage": with_detail_url / total if total else 0,
        "id_match_rate": matching_ids / total if total else 0,
        "publication_hint_coverage": with_publication_hint / total if total else 0,
        "salary_hint_coverage": with_salary_hint / total if total else 0,
        "salary_ui_prompt_coverage": with_salary_ui_prompt / total if total else 0,
        "remote_hint_coverage": with_remote_hint / total if total else 0,
        "employment_type_hint_coverage": (
            with_employment_type_hint / total if total else 0
        ),
    }


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description=(
            "Preview RawJobRecord-shaped records from StepStone result cards. "
            "Fetches exactly one search page. "
            "No detail pages, no pagination, no database writes."
        )
    )
    argument_parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help=f"Single StepStone search URL to inspect. Default: {DEFAULT_URL}",
    )
    argument_parser.add_argument(
        "--max-records",
        type=int,
        default=DEFAULT_MAX_RECORDS,
        help=(
            "Maximum number of preview records to print. "
            f"Default: {DEFAULT_MAX_RECORDS}"
        ),
    )

    args = argument_parser.parse_args()
    observed_at_utc = datetime.now(UTC).isoformat()

    response = fetch_url(args.url)

    cards = extract_result_card_fields(
        raw_html=response.text,
        final_url=response.url,
    )

    records = [
        build_preview_record(
            card=card,
            final_search_url=response.url,
            requested_url=args.url,
            observed_at_utc=observed_at_utc,
        )
        for card in cards
    ]

    output = {
        "request": {
            "requested_url": args.url,
            "final_url": response.url,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "response_bytes": len(response.content),
            "elapsed_seconds": response.elapsed.total_seconds(),
            "scope": {
                "single_search_page": True,
                "detail_pages": False,
                "pagination": False,
                "database_writes": False,
                "production_connector": False,
            },
        },
        "summary": build_summary(
            cards=cards,
            max_records=args.max_records,
        ),
        "records": records[: args.max_records],
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
