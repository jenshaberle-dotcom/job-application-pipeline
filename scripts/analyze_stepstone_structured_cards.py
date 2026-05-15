from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests


DEFAULT_URL = "https://www.stepstone.de/jobs/data-engineer/in-hannover"
REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_MAX_CARDS = 40

USER_AGENT = (
    "job-application-pipeline-stepstone-structured-card-probe/0.1 "
    "(local limited source evaluation; no crawling)"
)


@dataclass(frozen=True)
class ResultCardBlock:
    external_job_id: str
    raw_html: str
    start_position: int
    end_position: int


@dataclass(frozen=True)
class ResultCardFields:
    index: int
    external_job_id: str
    title: str | None
    company: str | None
    location: str | None
    detail_url: str | None
    raw_href: str | None
    card_html_bytes: int
    title_id_matches_article_id: bool
    data_at_fields: dict[str, str]


class CardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()

        self.title_href: str | None = None
        self.title_parts: list[str] = []

        self.data_at_fields: dict[str, list[str]] = {}

        self._ignored_depth = 0
        self._title_depth: int | None = None
        self._data_at_captures: list[dict[str, object]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized_tag = tag.lower()

        if normalized_tag in {"style", "script"}:
            self._ignored_depth += 1
            return

        if self._ignored_depth > 0:
            return

        if self._title_depth is not None:
            self._title_depth += 1

        for capture in self._data_at_captures:
            capture["depth"] = int(capture["depth"]) + 1

        attrs_dict = normalize_attrs(attrs)

        data_testid = attrs_dict.get("data-testid")
        data_at = attrs_dict.get("data-at")

        if normalized_tag == "a" and data_testid == "job-item-title":
            self.title_href = attrs_dict.get("href")
            self._title_depth = 1
            self.title_parts = []

        if data_at:
            self._data_at_captures.append(
                {
                    "name": data_at,
                    "depth": 1,
                }
            )
            self.data_at_fields.setdefault(data_at, [])

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()

        if normalized_tag in {"style", "script"} and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return

        if self._ignored_depth > 0:
            return

        if self._title_depth is not None:
            self._title_depth -= 1

            if self._title_depth <= 0:
                self._title_depth = None

        remaining_captures: list[dict[str, object]] = []

        for capture in self._data_at_captures:
            capture["depth"] = int(capture["depth"]) - 1

            if int(capture["depth"]) > 0:
                remaining_captures.append(capture)

        self._data_at_captures = remaining_captures

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return

        if self._title_depth is not None:
            self.title_parts.append(data)

        for capture in self._data_at_captures:
            name = str(capture["name"])
            self.data_at_fields.setdefault(name, []).append(data)

    @property
    def title(self) -> str | None:
        value = compact_text(" ".join(self.title_parts))
        return value or None

    @property
    def compact_data_at_fields(self) -> dict[str, str]:
        result: dict[str, str] = {}

        for key, parts in self.data_at_fields.items():
            value = compact_text(" ".join(parts))

            if value:
                result[key] = value

        return result


def normalize_attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in attrs
        if value is not None
    }


def compact_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_attr_from_tag(tag: str, attr_name: str) -> str | None:
    pattern = re.compile(
        rf"\b{re.escape(attr_name)}\s*=\s*(['\"])(.*?)\1",
        flags=re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(tag)

    if not match:
        return None

    return html.unescape(match.group(2))


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


def is_stepstone_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("stepstone.de")


def looks_like_job_detail_url(url: str) -> bool:
    return "stellenangebote" in url and re.search(r"--\d+.*\.html", url) is not None


def extract_stepstone_id_from_url(url: str | None) -> str | None:
    if not url:
        return None

    match = re.search(r"--(\d+)-inline\.html", url)

    if not match:
        return None

    return match.group(1)


def iter_article_blocks(raw_html: str) -> list[ResultCardBlock]:
    blocks: list[ResultCardBlock] = []

    for match in re.finditer(r"<article\b[^>]*>", raw_html, flags=re.IGNORECASE | re.DOTALL):
        opening_tag = match.group(0)

        data_testid = extract_attr_from_tag(opening_tag, "data-testid")
        article_id = extract_attr_from_tag(opening_tag, "id")

        if data_testid != "job-item":
            continue

        if not article_id:
            continue

        id_match = re.fullmatch(r"job-item-(\d+)", article_id)

        if not id_match:
            continue

        close_position = raw_html.find("</article>", match.end())

        if close_position < 0:
            continue

        end_position = close_position + len("</article>")

        blocks.append(
            ResultCardBlock(
                external_job_id=id_match.group(1),
                raw_html=raw_html[match.start():end_position],
                start_position=match.start(),
                end_position=end_position,
            )
        )

    return blocks


def find_first_job_detail_href(card_html: str) -> str | None:
    for match in re.finditer(r"<a\b[^>]*>", card_html, flags=re.IGNORECASE | re.DOTALL):
        opening_tag = match.group(0)
        href = extract_attr_from_tag(opening_tag, "href")

        if href and looks_like_job_detail_url(href):
            return href

    return None


def find_field_by_exact_keys(
    fields: dict[str, str],
    keys: list[str],
) -> str | None:
    for key in keys:
        value = fields.get(key)

        if value:
            return value

    return None


def find_field_by_name_fragment(
    fields: dict[str, str],
    fragments: list[str],
    excluded_fragments: list[str] | None = None,
) -> str | None:
    excluded_fragments = excluded_fragments or []

    for key, value in fields.items():
        lower_key = key.lower()

        if any(fragment in lower_key for fragment in excluded_fragments):
            continue

        if any(fragment in lower_key for fragment in fragments):
            return value

    return None


def extract_company(fields: dict[str, str]) -> str | None:
    return (
        find_field_by_exact_keys(
            fields,
            [
                "job-item-company-name",
                "company-name",
                "company",
            ],
        )
        or find_field_by_name_fragment(
            fields,
            fragments=["company", "arbeitgeber", "employer"],
            excluded_fragments=["logo"],
        )
    )


def extract_location(fields: dict[str, str]) -> str | None:
    return (
        find_field_by_exact_keys(
            fields,
            [
                "job-item-location",
                "job-location",
                "location",
            ],
        )
        or find_field_by_name_fragment(
            fields,
            fragments=["location", "ort", "standort"],
        )
    )


def extract_result_card_fields(
    raw_html: str,
    final_url: str,
) -> list[ResultCardFields]:
    article_blocks = iter_article_blocks(raw_html)
    cards: list[ResultCardFields] = []

    for index, article in enumerate(article_blocks, start=1):
        parser = CardParser()
        parser.feed(article.raw_html)

        fields = parser.compact_data_at_fields

        raw_href = parser.title_href or find_first_job_detail_href(article.raw_html)
        detail_url = urljoin(final_url, raw_href) if raw_href else None

        if detail_url and not is_stepstone_url(detail_url):
            detail_url = None

        title_job_id = extract_stepstone_id_from_url(detail_url)

        cards.append(
            ResultCardFields(
                index=index,
                external_job_id=article.external_job_id,
                title=parser.title,
                company=extract_company(fields),
                location=extract_location(fields),
                detail_url=detail_url,
                raw_href=raw_href,
                card_html_bytes=len(article.raw_html.encode("utf-8")),
                title_id_matches_article_id=title_job_id == article.external_job_id,
                data_at_fields=fields,
            )
        )

    return cards


def print_section(title: str) -> None:
    print()
    print(f"## {title}")


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
        print(f"external_job_id: {card.external_job_id}")
        print(f"title: {card.title or '<missing>'}")
        print(f"company: {card.company or '<missing>'}")
        print(f"location: {card.location or '<missing>'}")
        print(f"detail_url: {card.detail_url or '<missing>'}")
        print(f"raw_href: {card.raw_href or '<missing>'}")
        print(f"card_html_bytes: {card.card_html_bytes}")
        print(f"title_id_matches_article_id: {card.title_id_matches_article_id}")

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

    printed_cards = min(total, max_printed_cards)

    printed_cards = min(total, max_printed_cards)

    print(f"result_cards: {total}")
    print(f"printed_result_cards: {printed_cards}")
    print(f"max_printed_result_cards: {max_printed_cards}")
    print(f"with_title: {with_title}")
    print(f"with_company: {with_company}")
    print(f"with_location: {with_location}")
    print(f"with_detail_url: {with_detail_url}")
    print(f"title_id_matches_article_id: {matching_ids}")

    if total:
        print(f"title_coverage: {with_title / total:.4f}")
        print(f"company_coverage: {with_company / total:.4f}")
        print(f"location_coverage: {with_location / total:.4f}")
        print(f"detail_url_coverage: {with_detail_url / total:.4f}")
        print(f"id_match_rate: {matching_ids / total:.4f}")


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description=(
            "Limited StepStone result card field extraction probe. "
            "Fetches exactly one search page and extracts structured fields from "
            "article[data-testid='job-item'] result cards. "
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
    print("It extracts fields only from article[data-testid='job-item'] result cards.")
    print("It does not open detail pages.")
    print("It does not paginate.")
    print("It does not write to the database.")
    print("Use the output to decide whether StepStone result cards expose stable enough fields for a connector spike.")


if __name__ == "__main__":
    main()
