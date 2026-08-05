from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse

import requests

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.connectors.capabilities import SourceCapabilities
from src.search_intelligence.successfactors_locations import (
    extract_successfactors_locations,
)


SOURCE_FAMILY = "successfactors"
SOURCE_TYPE = "employer_origin_ats_backed_career_site"
REQUEST_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 750_000
MAX_DETAIL_PAGES_HARD_LIMIT = 5
USER_AGENT = (
    "job-application-pipeline-successfactors-connector/0.1 "
    "(bounded-read-only; one-listing-page; max-five-detail-pages)"
)


@dataclass(frozen=True)
class SuccessFactorsTarget:
    target_key: str
    source_name: str
    listing_url: str
    allowed_hosts: tuple[str, ...]
    employer_name: str
    employer_tokens: tuple[str, ...]
    profile_terms: tuple[str, ...]
    exclusion_terms: tuple[str, ...]
    job_path_prefixes: tuple[str, ...]


EON_GERMANY_TARGET = SuccessFactorsTarget(
    target_key="eon_germany",
    source_name="successfactors:eon_germany",
    listing_url=(
        "https://careers.eon.com/deutschland/go/Germany-Careers/3727101"
        "?q=&sortColumn=sort_title&sortDirection=asc"
    ),
    allowed_hosts=("careers.eon.com",),
    employer_name="E.ON Digital Technology GmbH",
    employer_tokens=("e.on", "digital", "technology", "gmbh"),
    profile_terms=(
        "data",
        "daten",
        "analytics",
        "analyst",
        "business intelligence",
        "ai",
        "ki",
        "machine learning",
        "software",
        "developer",
        "engineer",
        "platform",
        "cloud",
        "devops",
        "architect",
        "product owner",
        "sql",
        "python",
        "agentic",
        "copilot",
        "automation",
        "digital workplace",
        "cyber security",
    ),
    exclusion_terms=(
        "werkstudent",
        "working student",
        "praktikum",
        "internship",
        "ausbildung",
        "apprenticeship",
        "trainee",
        "duales studium",
        "dual study",
    ),
    job_path_prefixes=("/deutschland/job/",),
)

TARGETS: dict[str, SuccessFactorsTarget] = {
    EON_GERMANY_TARGET.target_key: EON_GERMANY_TARGET,
}


@dataclass(frozen=True)
class ListingCandidate:
    url: str
    external_job_id: str
    title_hint: str
    location_hint: str
    matched_terms: tuple[str, ...]
    requested_term_match: bool


@dataclass(frozen=True)
class DetailPage:
    requested_url: str
    final_url: str
    status_code: int
    title: str
    text: str
    html_bytes: int


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self._href = urljoin(self.base_url, href)
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        self.links.append(
            (
                self._href,
                normalize_whitespace(" ".join(self._text_parts)),
            )
        )
        self._href = None
        self._text_parts = []


class VisibleTextExtractor(HTMLParser):
    IGNORED_TAGS = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.text_parts: list[str] = []
        self._ignored_depth = 0
        self._title_depth = 0
        self._h1_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in self.IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if lowered == "title":
            self._title_depth += 1
        elif lowered == "h1":
            self._h1_depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self.IGNORED_TAGS:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if lowered == "title" and self._title_depth:
            self._title_depth -= 1
        elif lowered == "h1" and self._h1_depth:
            self._h1_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        cleaned = normalize_whitespace(data)
        if not cleaned:
            return
        self.text_parts.append(cleaned)
        if self._title_depth:
            self.title_parts.append(cleaned)
        if self._h1_depth:
            self.h1_parts.append(cleaned)

    @property
    def page_title(self) -> str:
        return normalize_whitespace(" ".join(self.title_parts))

    @property
    def h1(self) -> str:
        return normalize_whitespace(" ".join(self.h1_parts))

    @property
    def visible_text(self) -> str:
        return normalize_whitespace(" ".join(self.text_parts))


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str | None) -> str:
    text = normalize_whitespace(value).casefold()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def target_for(target_key: str) -> SuccessFactorsTarget:
    try:
        return TARGETS[target_key]
    except KeyError as exc:
        raise ValueError(f"Unknown SuccessFactors target: {target_key}") from exc


def allowed_host(url: str, target: SuccessFactorsTarget) -> bool:
    return (urlparse(url).hostname or "").casefold() in target.allowed_hosts


def job_id_from_url(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if not parts or not parts[-1].isdigit():
        return None
    return parts[-1]


def concrete_job_url(url: str, target: SuccessFactorsTarget) -> bool:
    if not allowed_host(url, target):
        return False
    path = urlparse(url).path
    if not any(path.startswith(prefix) for prefix in target.job_path_prefixes):
        return False
    return job_id_from_url(url) is not None


def find_terms(value: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    normalized = normalize_text(value)
    matches: list[str] = []
    for term in terms:
        if normalize_text(term) in normalized and term not in matches:
            matches.append(term)
    return tuple(matches)


def tokens_match(value: str, term: str) -> bool:
    normalized_term = normalize_text(term)
    if not normalized_term or normalized_term == "*":
        return False
    normalized_value = normalize_text(value)
    return all(token in normalized_value for token in normalized_term.split())


def _slug_parts(url: str) -> tuple[str, str]:
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) < 2:
        return "", ""
    slug = unquote(path_parts[-2])
    if "-" not in slug:
        return "", slug.replace("-", " ")
    location, title = slug.split("-", 1)
    return location.replace("-", " "), title.replace("-", " ")


def extract_listing_candidates(
    html: str,
    base_url: str,
    *,
    target: SuccessFactorsTarget,
    requested_term: str = "*",
) -> list[ListingCandidate]:
    parser = LinkExtractor(base_url)
    parser.feed(html)

    candidates: list[ListingCandidate] = []
    seen: set[str] = set()

    for raw_url, anchor_text in parser.links:
        clean_url = raw_url.split("#", 1)[0]
        if clean_url in seen or not concrete_job_url(clean_url, target):
            continue
        seen.add(clean_url)

        job_id = job_id_from_url(clean_url)
        if job_id is None:
            continue

        location_hint, slug_title = _slug_parts(clean_url)
        title_hint = anchor_text or slug_title
        evidence_blob = " ".join((clean_url, title_hint, location_hint))

        if find_terms(evidence_blob, target.exclusion_terms):
            continue

        matched_terms = find_terms(evidence_blob, target.profile_terms)
        requested_match = tokens_match(evidence_blob, requested_term)
        if not matched_terms and not requested_match:
            continue

        candidates.append(
            ListingCandidate(
                url=clean_url,
                external_job_id=job_id,
                title_hint=title_hint,
                location_hint=location_hint,
                matched_terms=matched_terms,
                requested_term_match=requested_match,
            )
        )

    return sorted(
        candidates,
        key=lambda item: (
            not item.requested_term_match,
            -len(item.matched_terms),
            normalize_text(item.title_hint),
            item.external_job_id,
        ),
    )


def select_listing_candidates(
    candidates: list[ListingCandidate],
    *,
    limit: int,
) -> list[ListingCandidate]:
    bounded_limit = max(0, min(limit, MAX_DETAIL_PAGES_HARD_LIMIT))
    return candidates[:bounded_limit]


def parse_detail_page(
    *,
    requested_url: str,
    final_url: str,
    status_code: int,
    html: str,
) -> DetailPage:
    parser = VisibleTextExtractor()
    parser.feed(html)
    title = parser.h1 or parser.page_title
    title = re.sub(
        r"\s+(?:Job Details|Stellendetails)\s*\|\s*E\.ON\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )
    return DetailPage(
        requested_url=requested_url,
        final_url=final_url,
        status_code=status_code,
        title=normalize_whitespace(title),
        text=parser.visible_text,
        html_bytes=len(html.encode("utf-8")),
    )


def employer_matches(detail: DetailPage, target: SuccessFactorsTarget) -> bool:
    normalized = normalize_text(detail.text)
    exact = normalize_text(target.employer_name)
    if exact and exact in normalized:
        return True
    return all(normalize_text(token) in normalized for token in target.employer_tokens)


def detail_supports_record(
    candidate: ListingCandidate,
    detail: DetailPage,
    target: SuccessFactorsTarget,
) -> bool:
    if detail.status_code >= 400:
        return False
    if not concrete_job_url(detail.final_url or candidate.url, target):
        return False
    if not employer_matches(detail, target):
        return False
    title_scope = " ".join((candidate.title_hint, detail.title))
    if find_terms(title_scope, target.exclusion_terms):
        return False
    relevance_scope = " ".join((title_scope, detail.text))
    return bool(find_terms(relevance_scope, target.profile_terms))


def _employment_metadata(detail: DetailPage, target: SuccessFactorsTarget) -> tuple[str, ...]:
    pattern = re.compile(
        re.escape(target.employer_name)
        + r"\s*\|\s*([^|]{1,80})\s*\|\s*([^|]{1,80})",
        flags=re.IGNORECASE,
    )
    match = pattern.search(detail.text)
    if not match:
        return ()
    return tuple(normalize_whitespace(value) for value in match.groups())


def build_raw_job_record(
    *,
    candidate: ListingCandidate,
    detail: DetailPage,
    target: SuccessFactorsTarget,
    listing_url: str,
    observed_at_utc: str,
    request_count: int,
    max_detail_pages: int,
) -> RawJobRecord:
    title = detail.title or candidate.title_hint
    detail_url = detail.final_url or candidate.url
    employment_metadata = _employment_metadata(detail, target)
    structured_locations = extract_successfactors_locations(detail.text)
    location_payload = [
        {
            "city": location.city,
            "country_code": location.country,
            "evidence_source": location.evidence_source,
            "evidence_text": location.evidence_text,
        }
        for location in structured_locations
    ]

    return RawJobRecord(
        source_name=target.source_name,
        source_url=detail_url,
        external_job_id=f"{target.target_key}:{candidate.external_job_id}",
        raw_data={
            "source_family": SOURCE_FAMILY,
            "source_target": target.target_key,
            "source_type": SOURCE_TYPE,
            "acquisition_boundary": {
                "listing_pages_fetched": 1,
                "pagination_enabled": False,
                "max_detail_pages": max_detail_pages,
                "request_count": request_count,
                "browser_automation_used": False,
                "access_control_bypass_used": False,
                "provider_requests": 0,
                "pipeline_mutation": False,
                "raw_html_persisted": False,
                "review_output_only_not_pipeline_input": True,
            },
            "result_card": {
                "title": title,
                "company_name": target.employer_name,
                "location": candidate.location_hint,
                "detail_url": detail_url,
            },
            "job": {
                "title": title,
                "company_name": target.employer_name,
                "location": candidate.location_hint,
                "locations": location_payload,
                "source_url": detail_url,
                "description": detail.text,
                "employment_metadata": list(employment_metadata),
            },
            "listing_evidence": {
                "listing_url": listing_url,
                "title_hint": candidate.title_hint,
                "location_hint": candidate.location_hint,
                "matched_profile_terms": list(candidate.matched_terms),
                "requested_term_match": candidate.requested_term_match,
            },
            "detail_evidence": {
                "status_code": detail.status_code,
                "html_bytes": detail.html_bytes,
                "target_employer_verified": True,
                "structured_location_count": len(location_payload),
                "raw_html_persisted": False,
            },
            "observed_at_utc": observed_at_utc,
        },
    )


def decode_response_text(response: requests.Response) -> str:
    content = response.content[:MAX_RESPONSE_BYTES]
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        encoding = response.encoding or response.apparent_encoding or "utf-8"
        try:
            return content.decode(encoding, errors="replace")
        except LookupError:
            return content.decode("utf-8", errors="replace")


def fetch_url(url: str) -> tuple[str, str, int]:
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return decode_response_text(response), response.url, response.status_code


class SuccessFactorsConnector(JobSourceConnector):
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
        *,
        target_key: str,
        max_detail_pages: int = MAX_DETAIL_PAGES_HARD_LIMIT,
        fetcher=None,
    ) -> None:
        self.target = target_for(target_key)
        self.source_name = self.target.source_name
        self.max_detail_pages = max(
            0,
            min(max_detail_pages, MAX_DETAIL_PAGES_HARD_LIMIT),
        )
        self.fetcher = fetcher or fetch_url

    def fetch_jobs(
        self,
        profile: SearchProfile,
        search_term: SearchTerm,
    ) -> tuple[list[RawJobRecord], str]:
        listing_html, final_listing_url, listing_status = self.fetcher(
            self.target.listing_url
        )
        if listing_status >= 400:
            raise RuntimeError(
                f"{self.source_name} listing request failed with status {listing_status}"
            )

        candidates = extract_listing_candidates(
            listing_html,
            final_listing_url,
            target=self.target,
            requested_term=search_term.search_term,
        )
        selected = select_listing_candidates(
            candidates,
            limit=self.max_detail_pages,
        )

        observed_at_utc = datetime.now(UTC).isoformat()
        accepted: list[tuple[ListingCandidate, DetailPage]] = []

        for candidate in selected:
            detail_html, detail_final_url, detail_status = self.fetcher(candidate.url)
            detail = parse_detail_page(
                requested_url=candidate.url,
                final_url=detail_final_url,
                status_code=detail_status,
                html=detail_html,
            )
            if detail_supports_record(candidate, detail, self.target):
                accepted.append((candidate, detail))

        request_count = 1 + len(selected)
        records = [
            build_raw_job_record(
                candidate=candidate,
                detail=detail,
                target=self.target,
                listing_url=final_listing_url,
                observed_at_utc=observed_at_utc,
                request_count=request_count,
                max_detail_pages=self.max_detail_pages,
            )
            for candidate, detail in accepted
        ]
        return records, final_listing_url
