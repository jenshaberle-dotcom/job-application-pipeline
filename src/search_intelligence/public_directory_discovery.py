"""Generic public directory discovery primitives for the Connector Factory corpus."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class DirectorySource:
    source_id: str
    geography: str
    cohorts: tuple[str, ...]
    start_url: str
    max_pages: int = 250


class LinkTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            value = " ".join(data.split())
            if value:
                self._text.append(value)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join(self._text).strip()
            if text:
                self.links.append((self._href, text))
            self._href = None
            self._text = []


def fetch_text(url: str, *, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": "JAP-Connector-Factory-Corpus/1.0"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"directory_http_status:{response.status}")
        return response.read().decode("utf-8", errors="replace")


def links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = LinkTextParser()
    parser.feed(html)
    return [(urljoin(base_url, href), text) for href, text in parser.links]


def seed(
    company_name: str,
    source: DirectorySource,
    *,
    website: str | None = None,
    industry: str | None = None,
    source_record_id: str | None = None,
    directory_url: str | None = None,
) -> dict[str, object]:
    return {
        "company_name": company_name.strip(),
        "source": source.source_id,
        "website": website,
        "directory_url": directory_url,
        "industry": industry,
        "source_record_id": source_record_id,
        "cohorts": list(source.cohorts),
        "cohort": source.cohorts[0],
        "geography": source.geography,
    }
