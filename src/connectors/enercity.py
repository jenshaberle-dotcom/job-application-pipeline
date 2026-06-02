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


SOURCE_NAME = 'enercity:discovery'
SOURCE_FAMILY = 'enercity'
SOURCE_TARGET = None
SOURCE_TYPE = 'employer_origin_career_site'
COMPANY_NAME = 'enercity AG'
LISTING_URL = 'https://www.enercity.de/karriere/jobsuche'
ALLOWED_HOSTS = ('www.enercity.de',)
KNOWN_DETAIL_URLS = ('https://www.enercity.de/karriere/jobsuche/cloud-infrastructure-devops-engineer-f-m-d-azure-focus-J2026011', 'https://www.enercity.de/karriere/jobsuche/manager-in-trinkwasserschutz-und-entschaedigungsmanagement-J2026258')
REQUEST_TIMEOUT_SECONDS = 20
MAX_DETAIL_PAGES = 3
USER_AGENT = (
    "job-application-pipeline-enercity-connector-candidate/0.1 "
    "(bounded; max 3 detail pages; relevance gated)"
)

PROFILE_TERMS = ('data', 'daten', 'analytics', 'analyst', 'business analyst', 'business intelligence', 'bi', 'sql', 'python', 'ki', 'ai', 'software', 'entwickler', 'javascript', 'ui', 'product owner', 'produktverantwort')
TARGET_LOCATION_TERMS = ('hannover', 'remote', 'deutschland', 'bundesweit', 'hybrid')
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


class EnercityConnector(JobSourceConnector):
    # Bounded employer-origin connector candidate generated from DB-backed approval-gated connector evidence.
    # This module does not activate recurring ingestion or approve Bronze persistence.

    source_name = SOURCE_NAME

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
            raise RuntimeError(f"{SOURCE_NAME} listing request failed with status {status_code}")

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
    value = normalize_whitespace(value).casefold()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return value


def find_terms(value: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    lowered = normalize_text(value)
    matches: list[str] = []

    for term in terms:
        if normalize_text(term) in lowered and term not in matches:
            matches.append(term)

    return tuple(matches)


def allowed_host(url: str) -> bool:
    return urlparse(url).netloc.lower() in ALLOWED_HOSTS


def has_known_detail_url(url: str) -> bool:
    return url.split("#", 1)[0] in KNOWN_DETAIL_URLS


def extract_candidate_links(html: str, base_url: str) -> list[CandidateLink]:
    parser = LinkExtractor(base_url)
    parser.feed(html)

    candidates: list[CandidateLink] = []
    seen: set[str] = set()

    for url, text in parser.links:
        clean_url = url.split("#", 1)[0]
        if clean_url in seen:
            continue
        seen.add(clean_url)

        if not allowed_host(clean_url):
            continue

        parsed = urlparse(clean_url)
        path = parsed.path
        blob = " ".join([clean_url, path, text])

        if find_terms(blob, EXCLUSION_TERMS):
            continue

        profile_terms = find_terms(blob, PROFILE_TERMS)
        location_terms = find_terms(blob, TARGET_LOCATION_TERMS)

        if has_known_detail_url(clean_url):
            recommendation = "known_detail_candidate_from_gate_evidence"
            reason = "URL was approved by DB-backed detail evidence gate."
        elif profile_terms and location_terms:
            recommendation = "strong_listing_candidate_for_review"
            reason = "Listing has profile and target/remote signals."
        elif profile_terms or location_terms:
            recommendation = "weak_listing_candidate_for_review"
            reason = "Listing has partial relevance evidence."
        else:
            continue

        candidates.append(
            CandidateLink(
                url=clean_url,
                path=path,
                text=text,
                location_terms=location_terms,
                profile_terms=profile_terms,
                recommendation=recommendation,
                reason=reason,
            )
        )

    return candidates


def select_detail_candidates(candidates: list[CandidateLink], limit: int) -> list[CandidateLink]:
    known = [candidate for candidate in candidates if candidate.recommendation == "known_detail_candidate_from_gate_evidence"]
    strong = [candidate for candidate in candidates if candidate.recommendation == "strong_listing_candidate_for_review"]
    weak = [candidate for candidate in candidates if candidate.recommendation == "weak_listing_candidate_for_review"]

    selected: list[CandidateLink] = []
    seen: set[str] = set()

    for candidate in [*known, *strong, *weak]:
        if candidate.url in seen:
            continue
        seen.add(candidate.url)
        selected.append(candidate)
        if len(selected) >= limit:
            break

    return selected


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

    evidence_text = " ".join([candidate.url, candidate.path, candidate.text, detail.title, detail.text])
    exclusion_scope_text = " ".join([candidate.url, candidate.path, detail.title])

    if find_terms(exclusion_scope_text, EXCLUSION_TERMS):
        return False

    return bool(find_terms(evidence_text, PROFILE_TERMS) and find_terms(evidence_text, TARGET_LOCATION_TERMS))


def stable_external_job_id(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.rstrip("/").split("/")[-1] or SOURCE_FAMILY
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{slug}:{digest}"


def derive_title(candidate: CandidateLink, detail: DetailPage) -> str:
    title = detail.title

    for suffix in (f" - {COMPANY_NAME}", f" | {COMPANY_NAME}", f" - {SOURCE_FAMILY}"):
        if title.endswith(suffix):
            title = title[: -len(suffix)]

    return normalize_whitespace(title) or candidate.text or candidate.path.rsplit("/", 1)[-1].replace("-", " ")


def build_raw_job_record(
    candidate: CandidateLink,
    detail: DetailPage,
    requested_listing_url: str,
    observed_at_utc: str,
) -> RawJobRecord:
    title = derive_title(candidate, detail)
    evidence_text = " ".join([candidate.url, candidate.text, detail.title, detail.text])
    profile_terms = find_terms(evidence_text, PROFILE_TERMS)
    location_terms = find_terms(evidence_text, TARGET_LOCATION_TERMS)
    location = "; ".join(location_terms) or SOURCE_TARGET or ""

    detail_url = detail.final_url or candidate.url

    return RawJobRecord(
        source_name=SOURCE_NAME,
        source_url=detail_url,
        external_job_id=stable_external_job_id(candidate.url),
        raw_data={
            "source_family": SOURCE_FAMILY,
            "source_target": SOURCE_TARGET,
            "source_type": SOURCE_TYPE,
            "acquisition_boundary": {
                "listing_url": requested_listing_url,
                "max_detail_pages": MAX_DETAIL_PAGES,
                "detail_pages_fetched": True,
                "browser_automation_used": False,
                "raw_html_persisted": False,
                "relevance_gated": True,
                "generated_from_gate_evidence": True,
            },
            "result_card": {
                "title": title,
                "company_name": COMPANY_NAME,
                "location": location,
                "detail_url": detail_url,
            },
            "job": {
                "title": title,
                "company_name": COMPANY_NAME,
                "location": location,
                "source_url": detail_url,
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
