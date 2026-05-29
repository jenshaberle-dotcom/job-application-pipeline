from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities

LISTING_URL = "https://www.f-i.de/de/karriere/offene-stellen"
REQUEST_TIMEOUT_SECONDS = 20
MAX_DETAIL_PAGES = 3
USER_AGENT = (
    "job-application-pipeline-finanz-informatik-connector-candidate/0.1 "
    "(bounded; max 3 detail pages; relevance gated)"
)

PROFILE_TERMS = (
    "data",
    "daten",
    "analytics",
    "analyst",
    "business analyst",
    "business-analyst",
    "bi",
    "sql",
    "python",
    "ki",
    "ai",
    "software",
    "entwickler",
    "javascript",
    "ui",
    "product owner",
    "produktverantwort",
)

TARGET_LOCATION_TERMS = ("hannover", "remote", "deutschland", "bundesweit", "hybrid")
SECONDARY_LOCATION_TERMS = ("frankfurt", "muenster", "münster")
EXCLUSION_TERMS = (
    "duales-studium",
    "duales studium",
    "ausbildung",
    "werkstudent",
    "werkstudierende",
    "praktikum",
    "trainee",
)


@dataclass(frozen=True)
class CandidateLink:
    url: str
    path: str
    text: str
    location_terms: tuple[str, ...]
    profile_terms: tuple[str, ...]
    recommendation: str
    reason: str


@dataclass(frozen=True)
class DetailPage:
    url: str
    final_url: str
    status_code: int
    title: str
    text: str
    html_bytes: int


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if not href:
            return
        self._current_href = urljoin(self.base_url, href)
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href:
            self.links.append((self._current_href, normalize_whitespace(" ".join(self._text_parts))))
            self._current_href = None
            self._text_parts = []


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        self.text_parts.append(data)

    @property
    def title(self) -> str:
        return normalize_whitespace(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return normalize_whitespace(" ".join(self.text_parts))


class FinanzInformatikConnector(JobSourceConnector):
    """Bounded Finanz Informatik connector candidate.

    This connector is intentionally conservative:
    - one configured listing page
    - max three detail pages
    - no OnApply crawling
    - relevance gates before RawJobRecord creation
    - not activated by migrations in this patch
    """

    source_name = "finanz_informatik:hannover"

    capabilities = SourceCapabilities(
        supports_keyword=False,
        supports_location=False,
        supports_radius=False,
        supports_employment_type=False,
        supports_remote_filter=False,
        supports_pagination=False,
        supports_full_fetch=True,
    )

    def __init__(
        self,
        listing_url: str = LISTING_URL,
        max_detail_pages: int = MAX_DETAIL_PAGES,
        fetcher=None,
    ) -> None:
        self.listing_url = listing_url
        self.max_detail_pages = max_detail_pages
        self.fetcher = fetcher or fetch_url

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        listing_html, final_url, status_code = self.fetcher(self.listing_url)
        if status_code >= 400:
            raise RuntimeError(f"Finanz Informatik listing request failed with status {status_code}")

        candidates = select_detail_candidates(
            extract_candidate_links(listing_html, final_url),
            limit=self.max_detail_pages,
        )

        observed_at_utc = datetime.now(UTC).isoformat()
        records: list[RawJobRecord] = []

        for candidate in candidates:
            detail_html, detail_final_url, detail_status = self.fetcher(candidate.url)
            detail = parse_detail_page(
                url=candidate.url,
                final_url=detail_final_url,
                status_code=detail_status,
                html=detail_html,
            )
            if not detail_supports_record(candidate, detail):
                continue

            records.append(
                build_raw_job_record(
                    candidate=candidate,
                    detail=detail,
                    requested_listing_url=final_url,
                    observed_at_utc=observed_at_utc,
                )
            )

        return records, final_url


def fetch_url(url: str) -> tuple[str, str, int]:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text, response.url, response.status_code


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str | None) -> str:
    value = normalize_whitespace(value).lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return value


def find_terms(value: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    lowered = normalize_text(value)
    matches = []
    for term in terms:
        if normalize_text(term) in lowered and term not in matches:
            matches.append(term)
    return tuple(matches)


def is_allowed_finanz_informatik_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in {"www.f-i.de", "f-i.de"}


def extract_candidate_links(html: str, base_url: str) -> list[CandidateLink]:
    parser = LinkExtractor(base_url)
    parser.feed(html)

    candidates: list[CandidateLink] = []
    seen: set[str] = set()

    for url, text in parser.links:
        if url in seen:
            continue
        seen.add(url)

        parsed = urlparse(url)
        path = parsed.path
        blob = " ".join([url, path, text])

        if not is_allowed_finanz_informatik_host(url) or "/de/karriere/offene-stellen/" not in path:
            continue

        if "/duales-studium-ausbildung/" in path:
            continue

        profile_terms = find_terms(blob, PROFILE_TERMS)
        location_terms = find_terms(blob, TARGET_LOCATION_TERMS + SECONDARY_LOCATION_TERMS)
        recommendation, reason = classify_listing_candidate(
            path=path,
            text=text,
            profile_terms=profile_terms,
            location_terms=location_terms,
        )

        candidates.append(
            CandidateLink(
                url=url,
                path=path,
                text=text,
                location_terms=location_terms,
                profile_terms=profile_terms,
                recommendation=recommendation,
                reason=reason,
            )
        )

    return candidates


def has_target_location(location_terms: tuple[str, ...]) -> bool:
    normalized = {normalize_text(value) for value in location_terms}
    return bool(normalized & {normalize_text(value) for value in TARGET_LOCATION_TERMS})


def has_secondary_location(location_terms: tuple[str, ...]) -> bool:
    normalized = {normalize_text(value) for value in location_terms}
    return bool(normalized & {normalize_text(value) for value in SECONDARY_LOCATION_TERMS})


def classify_listing_candidate(
    path: str,
    text: str,
    profile_terms: tuple[str, ...],
    location_terms: tuple[str, ...],
) -> tuple[str, str]:
    listing_scope_text = " ".join([path, text])
    if find_terms(listing_scope_text, EXCLUSION_TERMS):
        return (
            "exclude_training_student_or_entry_level",
            "Listing is training, student, internship or entry-level scoped and must not consume bounded detail-fetch capacity.",
        )

    if has_secondary_location(location_terms) and not has_target_location(location_terms):
        return (
            "defer_non_target_location_without_remote_signal",
            "Listing is outside target scope and has no visible remote/Germany-wide signal.",
        )

    if profile_terms and has_target_location(location_terms):
        return "strong_listing_candidate_for_review", "Listing has profile and target-location signals."

    if has_target_location(location_terms):
        return "job_candidate_low_profile_signal", "Listing has target location but weak profile signal."

    return "profile_match_location_unknown_review", "Listing needs manual location review."


def select_detail_candidates(candidates: list[CandidateLink], limit: int) -> list[CandidateLink]:
    priority = {
        "strong_listing_candidate_for_review": 0,
        "job_candidate_low_profile_signal": 1,
    }
    ranked: list[tuple[int, int, CandidateLink]] = []

    for index, candidate in enumerate(candidates):
        if candidate.recommendation not in priority:
            continue
        if not has_target_location(candidate.location_terms):
            continue
        ranked.append((priority[candidate.recommendation], index, candidate))

    return [candidate for _, _, candidate in sorted(ranked)[:limit]]


def parse_detail_page(url: str, final_url: str, status_code: int, html: str) -> DetailPage:
    parser = TextExtractor()
    parser.feed(html)
    return DetailPage(
        url=url,
        final_url=final_url,
        status_code=status_code,
        title=parser.title,
        text=parser.text,
        html_bytes=len(html.encode("utf-8")),
    )


def detail_supports_record(candidate: CandidateLink, detail: DetailPage) -> bool:
    if detail.status_code >= 400:
        return False

    relevance_text = " ".join([candidate.url, candidate.path, candidate.text, detail.title, detail.text])
    exclusion_scope_text = " ".join([candidate.url, candidate.path, detail.title])

    if find_terms(exclusion_scope_text, EXCLUSION_TERMS):
        return False

    return bool(find_terms(relevance_text, PROFILE_TERMS) and find_terms(relevance_text, TARGET_LOCATION_TERMS))


def stable_external_job_id(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.rstrip("/").split("/")[-1]
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{slug}:{digest}"


def build_raw_job_record(
    candidate: CandidateLink,
    detail: DetailPage,
    requested_listing_url: str,
    observed_at_utc: str,
) -> RawJobRecord:
    title = detail.title.removesuffix(" - Finanz Informatik").strip() or candidate.text or candidate.path.rsplit("/", 1)[-1]
    location = "; ".join(candidate.location_terms) or "hannover"
    profile_terms = find_terms(" ".join([candidate.url, detail.title, detail.text]), PROFILE_TERMS)

    return RawJobRecord(
        source_name="finanz_informatik:hannover",
        source_url=detail.final_url or candidate.url,
        external_job_id=stable_external_job_id(candidate.url),
        raw_data={
            "source_family": "finanz_informatik",
            "source_target": "hannover",
            "acquisition_boundary": {
                "listing_url": requested_listing_url,
                "max_detail_pages": MAX_DETAIL_PAGES,
                "detail_pages_fetched": True,
                "onapply_used": False,
                "relevance_gated": True,
            },
            "result_card": {
                "title": title,
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "location": location,
                "detail_url": detail.final_url or candidate.url,
            },
            "job": {
                "title": title,
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "location": location,
                "source_url": detail.final_url or candidate.url,
                "profile_terms": list(profile_terms),
            },
            "listing_evidence": {
                "candidate_path": candidate.path,
                "listing_text": candidate.text,
                "listing_recommendation": candidate.recommendation,
                "listing_reason": candidate.reason,
            },
            "detail_evidence": {
                "page_title": detail.title,
                "html_bytes": detail.html_bytes,
                "status_code": detail.status_code,
                "raw_html_persisted": False,
            },
            "observed_at_utc": observed_at_utc,
        },
    )
