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
CONTEXT_CHARS = 700
MAX_CANDIDATES = 40

USER_AGENT = (
    "job-application-pipeline-stepstone-result-boundary-probe/0.1 "
    "(local limited source evaluation; no crawling)"
)


@dataclass(frozen=True)
class LinkOccurrence:
    href: str
    normalized_url: str
    text: str


@dataclass(frozen=True)
class CandidateContext:
    index: int
    url: str
    text: str
    raw_href: str
    position: int | None
    nearby_markers: list[str]
    context: str


class LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[LinkOccurrence] = []

        self._current_href: str | None = None
        self._current_text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return

        attrs_dict = {key.lower(): value for key, value in attrs}
        href = attrs_dict.get("href")

        if href:
            self._current_href = href
            self._current_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a":
            return

        if self._current_href is None:
            return

        text = " ".join(" ".join(self._current_text_parts).split())

        self.links.append(
            LinkOccurrence(
                href=self._current_href,
                normalized_url=urljoin(self.base_url, self._current_href),
                text=text,
            )
        )

        self._current_href = None
        self._current_text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text_parts.append(data)


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


def unique_links_preserve_order(links: list[LinkOccurrence]) -> list[LinkOccurrence]:
    seen: set[str] = set()
    result: list[LinkOccurrence] = []

    for link in links:
        if link.normalized_url not in seen:
            seen.add(link.normalized_url)
            result.append(link)

    return result


def compact_html(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def find_href_position(raw_html: str, raw_href: str, normalized_url: str) -> int | None:
    candidates = [
        raw_href,
        html.escape(raw_href, quote=True),
        normalized_url,
        html.escape(normalized_url, quote=True),
        normalized_url.replace("https://www.stepstone.de", ""),
        html.escape(normalized_url.replace("https://www.stepstone.de", ""), quote=True),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        position = raw_html.find(candidate)

        if position >= 0:
            return position

    return None


def extract_nearby_start_tags(raw_html: str, position: int, max_tags: int = 12) -> list[str]:
    before = raw_html[max(0, position - 3000):position]
    tags = re.findall(r"<[a-zA-Z][^>]{0,700}>", before)

    relevant_tags = []

    for tag in tags[-max_tags:]:
        lower = tag.lower()

        if any(
            marker in lower
            for marker in [
                "data-",
                "aria-",
                "role=",
                "job",
                "card",
                "result",
                "listing",
                "search",
                "item",
            ]
        ):
            relevant_tags.append(compact_html(tag))

    return relevant_tags[-max_tags:]


def extract_context(raw_html: str, position: int | None) -> str:
    if position is None:
        return "<href not found in raw HTML>"

    start = max(0, position - CONTEXT_CHARS)
    end = min(len(raw_html), position + CONTEXT_CHARS)

    return compact_html(raw_html[start:end])


def extract_candidates(raw_html: str, final_url: str) -> list[CandidateContext]:
    parser = LinkParser(base_url=final_url)
    parser.feed(raw_html)

    candidate_links = [
        link
        for link in parser.links
        if is_stepstone_url(link.normalized_url)
        and looks_like_job_detail_url(link.normalized_url)
    ]

    unique_candidates = unique_links_preserve_order(candidate_links)

    contexts: list[CandidateContext] = []

    for index, link in enumerate(unique_candidates[:MAX_CANDIDATES], start=1):
        position = find_href_position(
            raw_html=raw_html,
            raw_href=link.href,
            normalized_url=link.normalized_url,
        )

        nearby_markers = (
            extract_nearby_start_tags(raw_html, position)
            if position is not None
            else []
        )

        contexts.append(
            CandidateContext(
                index=index,
                url=link.normalized_url,
                text=link.text,
                raw_href=link.href,
                position=position,
                nearby_markers=nearby_markers,
                context=extract_context(raw_html, position),
            )
        )

    return contexts


def count_global_markers(raw_html: str) -> dict[str, int]:
    markers = [
        "data-testid",
        "data-at",
        "data-genesis-element",
        "job",
        "card",
        "result",
        "listing",
        "search-result",
        "__NEXT_DATA__",
        "application/ld+json",
    ]

    lower_html = raw_html.lower()

    return {
        marker: lower_html.count(marker.lower())
        for marker in markers
    }


def print_section(title: str) -> None:
    print()
    print(f"## {title}")


def print_candidate(candidate: CandidateContext) -> None:
    print()
    print(f"### Candidate {candidate.index:02d}")
    print(f"URL: {candidate.url}")
    print(f"Link text: {candidate.text or '<empty>'}")
    print(f"Raw href: {candidate.raw_href}")
    print(f"Raw HTML position: {candidate.position if candidate.position is not None else '<not found>'}")

    print()
    print("Nearby relevant start tags:")

    if candidate.nearby_markers:
        for marker in candidate.nearby_markers:
            print(f"- {marker}")
    else:
        print("- <none detected>")

    print()
    print("Compact context:")
    print(candidate.context)


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description=(
            "Limited StepStone result boundary probe. "
            "Fetches exactly one search page and inspects HTML context around "
            "globally extracted detail links. No crawling, no pagination, no database writes."
        )
    )
    argument_parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help=f"Single StepStone search URL to inspect. Default: {DEFAULT_URL}",
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

    print_section("Global Marker Counts")
    for marker, count in count_global_markers(raw_html).items():
        print(f"{marker}: {count}")

    candidates = extract_candidates(raw_html, response.url)

    print_section("Candidate Summary")
    print(f"Candidate detail links found: {len(candidates)}")
    print(f"Maximum candidates printed: {MAX_CANDIDATES}")

    for candidate in candidates:
        print_candidate(candidate)

    print_section("Assessment Reminder")
    print("This script inspects only one search page.")
    print("It does not open detail pages.")
    print("It does not paginate.")
    print("It does not write to the database.")
    print("Use the output to identify stable primary-result boundaries before connector work.")


if __name__ == "__main__":
    main()
