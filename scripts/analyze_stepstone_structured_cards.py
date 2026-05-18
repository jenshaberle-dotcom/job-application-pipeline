from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.connectors.stepstone_result_cards import (  # noqa: E402
    RESULT_CARD_SELECTOR_DESCRIPTION,
    ResultCardFields,
    extract_result_card_fields,
)


DEFAULT_URL = "https://www.stepstone.de/jobs/data-engineer/in-hannover"
REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_MAX_CARDS = 40

USER_AGENT = (
    "job-application-pipeline-stepstone-structured-card-probe/0.1 "
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


def print_section(title: str) -> None:
    print()
    print(f"## {title}")


def print_optional_field(label: str, value: str | None) -> None:
    print(f"{label}: {value or '<missing>'}")


def print_text_preview(label: str, value: str, max_chars: int = 300) -> None:
    if not value:
        print(f"{label}: <missing>")
        return

    preview = value[:max_chars]

    if len(value) > max_chars:
        preview = f"{preview}..."

    print(f"{label}: {preview}")


def print_result_card_fields(
    cards: list[ResultCardFields],
    max_printed_cards: int,
) -> None:
    if not cards:
        print("<no result cards detected>")
        return

    for card in cards[:max_printed_cards]:
        print()
        print(f"### Card {card.index:02d}")
        print(f"external_job_id_candidate: {card.external_job_id}")
        print_optional_field("title", card.title)
        print_optional_field("company", card.company)
        print_optional_field("location", card.location)
        print_optional_field("detail_url", card.detail_url)
        print_optional_field("raw_href", card.raw_href)
        print(f"card_html_bytes: {card.card_html_bytes}")
        print(f"title_id_matches_article_id: {card.title_id_matches_article_id}")
        print_optional_field("publication_hint_text", card.publication_hint_text)
        print_optional_field("salary_hint_text", card.salary_hint_text)
        print_optional_field("salary_ui_prompt_text", card.salary_ui_prompt_text)
        print_optional_field("remote_hint_text", card.remote_hint_text)
        print_optional_field("employment_type_hint_text", card.employment_type_hint_text)
        print_text_preview("raw_card_text_preview", card.raw_card_text)

        print("data_at_fields:")

        if card.data_at_fields:
            for key, value in sorted(card.data_at_fields.items()):
                print(f"- {key}: {value}")
        else:
            print("- <none>")


def print_quality_summary(
    cards: list[ResultCardFields],
    max_printed_cards: int,
) -> None:
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

    printed_cards = min(total, max_printed_cards)

    print(f"result_cards: {total}")
    print(f"printed_result_cards: {printed_cards}")
    print(f"max_printed_result_cards: {max_printed_cards}")
    print(f"with_title: {with_title}")
    print(f"with_company: {with_company}")
    print(f"with_location: {with_location}")
    print(f"with_detail_url: {with_detail_url}")
    print(f"title_id_matches_article_id: {matching_ids}")
    print(f"with_publication_hint: {with_publication_hint}")
    print(f"with_salary_hint: {with_salary_hint}")
    print(f"with_salary_ui_prompt: {with_salary_ui_prompt}")
    print(f"with_remote_hint: {with_remote_hint}")
    print(f"with_employment_type_hint: {with_employment_type_hint}")

    if total:
        print(f"title_coverage: {with_title / total:.4f}")
        print(f"company_coverage: {with_company / total:.4f}")
        print(f"location_coverage: {with_location / total:.4f}")
        print(f"detail_url_coverage: {with_detail_url / total:.4f}")
        print(f"id_match_rate: {matching_ids / total:.4f}")
        print(f"publication_hint_coverage: {with_publication_hint / total:.4f}")
        print(f"salary_hint_coverage: {with_salary_hint / total:.4f}")
        print(f"salary_ui_prompt_coverage: {with_salary_ui_prompt / total:.4f}")
        print(f"remote_hint_coverage: {with_remote_hint / total:.4f}")
        print(
            "employment_type_hint_coverage: "
            f"{with_employment_type_hint / total:.4f}"
        )


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description=(
            "Limited StepStone result card field extraction probe. "
            "Fetches exactly one search page and extracts structured fields from "
            f"{RESULT_CARD_SELECTOR_DESCRIPTION} result cards. "
            "No crawling, no pagination, no detail pages, no database writes."
        )
    )
    argument_parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help=f"Single StepStone search URL to inspect. Default: {DEFAULT_URL}",
    )
    argument_parser.add_argument(
        "--max-cards",
        type=int,
        default=DEFAULT_MAX_CARDS,
        help=f"Maximum number of result cards to print. Default: {DEFAULT_MAX_CARDS}",
    )

    args = argument_parser.parse_args()

    print_section("Request")
    print(f"Requested URL: {args.url}")
    print("Scope: single search-page request, no detail pages, no crawling, no persistence")
    print(f"Result card selector: {RESULT_CARD_SELECTOR_DESCRIPTION}")

    response = fetch_url(args.url)
    raw_html = response.text

    print_section("Response")
    print(f"Status code: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Content-Type: {response.headers.get('content-type', '<missing>')}")
    print(f"Response bytes: {len(response.content)}")
    print(f"Elapsed seconds: {response.elapsed.total_seconds():.3f}")

    cards = extract_result_card_fields(
        raw_html=raw_html,
        final_url=response.url,
    )

    print_section("Result Card Field Quality Summary")
    print_quality_summary(cards, max_printed_cards=args.max_cards)

    print_section("Result Card Fields")
    print_result_card_fields(cards, max_printed_cards=args.max_cards)

    print_section("Assessment Reminder")
    print("This script inspects only one search page.")
    print(f"It extracts fields only from {RESULT_CARD_SELECTOR_DESCRIPTION} result cards.")
    print("It does not open detail pages.")
    print("It does not paginate.")
    print("It does not write to the database.")
    print(
        "Use the output to validate whether StepStone result cards expose "
        "stable enough fields for a limited connector."
    )


if __name__ == "__main__":
    main()
