from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests


DEFAULT_URL = "https://www.stepstone.de/jobs/data-engineer/in-hannover"
REQUEST_TIMEOUT_SECONDS = 20
MAX_SAMPLE_LINKS = 15

USER_AGENT = (
    "job-application-pipeline-stepstone-source-probe/0.1 "
    "(local limited source evaluation; no crawling)"
)


@dataclass(frozen=True)
class LinkCandidate:
    href: str
    text: str


class BasicHTMLProbeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.links: list[LinkCandidate] = []
        self.meta_robots: list[str] = []

        self._inside_title = False
        self._current_href: str | None = None
        self._current_link_text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attrs_dict = {key.lower(): value for key, value in attrs}

        if tag.lower() == "title":
            self._inside_title = True

        if tag.lower() == "meta":
            name = (attrs_dict.get("name") or "").lower()
            content = attrs_dict.get("content") or ""

            if name == "robots":
                self.meta_robots.append(content.strip())

        if tag.lower() == "a":
            href = attrs_dict.get("href")

            if href:
                self._current_href = href
                self._current_link_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

        if tag.lower() == "a" and self._current_href is not None:
            text = " ".join(" ".join(self._current_link_text_parts).split())
            self.links.append(
                LinkCandidate(
                    href=self._current_href,
                    text=text,
                )
            )
            self._current_href = None
            self._current_link_text_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self.title_parts.append(data)

        if self._current_href is not None:
            self._current_link_text_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(" ".join(self.title_parts).split())


def normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def is_stepstone_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("stepstone.de")


def looks_like_job_detail_url(url: str) -> bool:
    return "stellenangebote" in url and re.search(r"--\d+.*\.html", url) is not None


def extract_numeric_ids(urls: Iterable[str]) -> list[str]:
    ids: set[str] = set()

    for url in urls:
        for match in re.finditer(r"--(\d+)(?:-|\.|_)?", url):
            ids.add(match.group(1))

    return sorted(ids)


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)

    return result


def fetch_url(url: str) -> requests.Response:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    return response


def print_section(title: str) -> None:
    print()
    print(f"## {title}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Limited StepStone source probe. "
            "Fetches exactly one URL and prints non-persistent analysis hints."
        )
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help=f"Single StepStone URL to inspect. Default: {DEFAULT_URL}",
    )

    args = parser.parse_args()
    url = args.url

    print_section("Request")
    print(f"Requested URL: {url}")
    print("Scope: single request, no crawling, no pagination, no persistence")

    response = fetch_url(url)

    print_section("Response")
    print(f"Status code: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Content-Type: {response.headers.get('content-type', '<missing>')}")
    print(f"Response bytes: {len(response.content)}")
    print(f"Elapsed seconds: {response.elapsed.total_seconds():.3f}")

    html = response.text

    parser = BasicHTMLProbeParser()
    parser.feed(html)

    print_section("HTML Signals")
    print(f"Title: {parser.title or '<missing>'}")

    if parser.meta_robots:
        print("Meta robots:")
        for value in parser.meta_robots:
            print(f"- {value}")
    else:
        print("Meta robots: <missing>")

    normalized_links = [
        normalize_url(response.url, link.href)
        for link in parser.links
    ]

    stepstone_links = [
        link
        for link in normalized_links
        if is_stepstone_url(link)
    ]

    job_detail_links = [
        link
        for link in stepstone_links
        if looks_like_job_detail_url(link)
    ]

    unique_job_detail_links = unique_preserve_order(job_detail_links)
    numeric_ids = extract_numeric_ids(unique_job_detail_links)

    print_section("Link Signals")
    print(f"All links found: {len(parser.links)}")
    print(f"StepStone links found: {len(stepstone_links)}")
    print(f"Candidate job detail links found: {len(unique_job_detail_links)}")
    print(f"Candidate numeric IDs found: {len(numeric_ids)}")

    print_section("Sample Candidate Job Detail Links")
    if unique_job_detail_links:
        for link in unique_job_detail_links[:MAX_SAMPLE_LINKS]:
            print(f"- {link}")
    else:
        print("<none>")

    print_section("Sample Candidate Numeric IDs")
    if numeric_ids:
        for numeric_id in numeric_ids[:MAX_SAMPLE_LINKS]:
            print(f"- {numeric_id}")
    else:
        print("<none>")

    print_section("Assessment Reminder")
    print("This script is a limited source probe.")
    print("It must not be extended into broad crawling without a separate decision.")
    print("No database writes are performed.")


if __name__ == "__main__":
    main()
