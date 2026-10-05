"""Generic public directory discovery primitives for the Connector Factory corpus."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError
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


class _PageHeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] | None = None
        self.headings: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.suppressed += 1
        elif tag == "h1" and not self.suppressed:
            self.parts = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.suppressed:
            self.suppressed -= 1
        elif tag == "h1" and self.parts is not None and not self.suppressed:
            self.headings.append(" ".join(" ".join(self.parts).split()))
            self.parts = None

    def handle_data(self, data):
        if self.parts is not None and not self.suppressed:
            self.parts.append(data)


def unique_page_heading(html: str) -> str:
    """Extract the actual profile heading; never guess a name from a URL/card."""
    parser = _PageHeadingParser()
    parser.feed(html)
    parser.close()
    headings = set(parser.headings)
    if len(headings) != 1:
        raise ValueError("directory_profile_heading_required")
    name = headings.pop()
    if not 2 <= len(name) <= 180 or re.match(r"(?i)(?:https?://|www\.)", name):
        raise ValueError("directory_profile_heading_invalid")
    if name.casefold() in {"not found", "page not found", "404", "homepage", "access denied"}:
        raise ValueError("directory_profile_heading_invalid")
    return name


def discovery_failure(exc: Exception) -> dict[str, object]:
    """Bounded diagnostic classification; no raw stderr, URLs, tokens or paths."""
    reason = "SOURCE_FAILURE"
    result: dict[str, object] = {}
    if isinstance(exc, HTTPError) and type(exc.code) is int:
        reason = "HTTP_ERROR"
        result["http_status"] = exc.code
    elif isinstance(exc, subprocess.TimeoutExpired):
        reason = "SOURCE_TIMEOUT"
    elif isinstance(exc, subprocess.CalledProcessError):
        reason = "SUBPROCESS_FAILED"
        if type(exc.returncode) is int:
            result["exit_code"] = exc.returncode
        raw = exc.stderr or ""
        if isinstance(raw, bytes):
            raw = raw[-8192:].decode("utf-8", errors="replace")
        lines = str(raw)[-8192:].strip().splitlines()
        tail = lines[-1] if lines else ""
        # Only the terminal exception line, never a quoted source-code line.
        match = re.search(r"(?:HTTP Error |directory_http_status:)([1-5][0-9]{2})(?:\b|$)", tail)
        if match:
            reason = "HTTP_ERROR"
            result["http_status"] = int(match.group(1))
        elif any(token in tail for token in ("Name or service not known", "Temporary failure in name resolution")):
            reason = "DNS_FAILURE"
        elif "CERTIFICATE_VERIFY_FAILED" in tail:
            reason = "TLS_CERTIFICATE_FAILURE"
        elif "timed out" in tail or "TimeoutError" in tail:
            reason = "TRANSPORT_TIMEOUT"
        elif "ModuleNotFoundError:" in tail:
            reason = "RUNTIME_IMPORT_FAILURE"
        elif "directory_record_" in tail or "directory_profile_heading_" in tail:
            reason = "SOURCE_IDENTITY_PARSE_FAILURE"
    elif isinstance(exc, json.JSONDecodeError):
        reason = "INVALID_SOURCE_JSON"
    elif isinstance(exc, OSError):
        reason = "SOURCE_IO_FAILURE"
    elif isinstance(exc, ValueError):
        reason = "SOURCE_SHAPE_FAILURE"
    result["failure_reason"] = reason
    return result
