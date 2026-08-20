"""Bounded acquisition-first helpers for generated employer-origin connectors.

This module answers one narrow question: can an employer-origin connector reach a
real job-detail page? It deliberately does not decide whether that job is a
profile, role, skill, or location match. Callers inject the fetcher and choose a
small follow-up budget; this module performs no persistence and no provider calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from src.search_intelligence.connector_feasibility import classify_evidence_links
from src.search_intelligence.connector_feasibility_query_runtime import (
    extract_trusted_query_job_detail_links,
)
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


NON_JOB_URL_MARKERS = (
    "/privacy",
    "/datenschutz",
    "/impressum",
    "/imprint",
    "/legal",
    "/cookie",
    "/contact",
    "/kontakt",
    "/faq",
    "/blog",
    "/news",
    "/newsletter",
    "/press",
    "/presse",
    "/resources",
    "/resource/",
)

LISTING_URL_MARKERS = (
    "/jobs",
    "/job-search",
    "/jobsearch",
    "/jobsuche",
    "/stellen",
    "/stellenangebote",
    "/offene-stellen",
    "/vacancies",
    "/vacancy",
    "/positions",
    "/open-positions",
    "/openings",
    "/opportunities",
    "/our-offers",
    "/job-board",
    "/jobboard",
)

LISTING_TEXT_MARKERS = (
    "jobs",
    "stellenangebote",
    "offene stellen",
    "jobsuche",
    "vacancies",
    "vacancy",
    "open positions",
    "openings",
    "opportunities",
    "our offers",
    "job board",
    "job search",
    "view jobs",
    "to the jobs",
    "search jobs",
    "see jobs",
    "job opportunities",
    "stellen entdecken",
)

NON_DELEGATED_HOST_SUFFIXES = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
)

JOB_CONTENT_MARKERS = (
    "jobposting",
    "job details",
    "job detail",
    "stellenbeschreibung",
    "job description",
    "jetzt bewerben",
    "bewerben",
    "apply now",
    "apply for this job",
    "responsibilities",
    "your responsibilities",
    "requirements",
    "your profile",
    "aufgaben",
    "anforderungen",
    "qualifikationen",
    "was du mitbringst",
    "was sie mitbringen",
)

GENERIC_PAGE_TITLES = {
    "jobs",
    "jobs & karriere",
    "karriere",
    "career",
    "careers",
    "stellenangebote",
    "job search",
    "jobsuche",
    "job portal",
    "career site",
    "login",
}


@dataclass(frozen=True)
class PageSnapshot:
    requested_url: str
    final_url: str
    status_code: int
    title: str
    text: str
    html: str
    links: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class NavigationCandidate:
    url: str
    kind: str
    discovery_source: str
    anchor_text: str = ""
    known_detail: bool = False


@dataclass(frozen=True)
class AcquiredJobPage:
    requested_url: str
    final_url: str
    status_code: int
    title: str
    html_bytes: int
    proof_kind: str
    discovery_source: str
    anchor_text: str


class PageExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._href: str | None = None
        self._link_text: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered == "title":
            self._in_title = True
        if lowered != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self._href = urljoin(self.base_url, href)
        self._link_text = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._in_title:
            self.title_parts.append(data)
        if self._href:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "title":
            self._in_title = False
        if lowered == "a" and self._href:
            self.links.append(
                (canonical_url(self._href), normalize_whitespace(" ".join(self._link_text)))
            )
            self._href = None
            self._link_text = []

    @property
    def title(self) -> str:
        return normalize_whitespace(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return normalize_whitespace(" ".join(self.text_parts))


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def canonical_url(value: str) -> str:
    return str(value or "").split("#", 1)[0].rstrip("/")


def url_host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold()


def allowed_host(url: str, allowed_hosts: tuple[str, ...] | set[str]) -> bool:
    normalized = {str(item).casefold() for item in allowed_hosts if str(item)}
    return bool(url_host(url) and url_host(url) in normalized)


def non_job_url(url: str) -> bool:
    lowered = canonical_url(url).casefold()
    return any(marker in lowered for marker in NON_JOB_URL_MARKERS)


def parse_page(
    *,
    requested_url: str,
    html: str,
    final_url: str,
    status_code: int,
) -> PageSnapshot:
    observed_url = final_url or requested_url
    parser = PageExtractor(observed_url)
    parser.feed(html)
    return PageSnapshot(
        requested_url=requested_url,
        final_url=observed_url,
        status_code=int(status_code),
        title=parser.title,
        text=parser.text,
        html=html,
        links=tuple(parser.links),
    )


def _decode_embedded_url_text(value: str) -> str:
    decoded = unescape(value or "")
    return decoded.replace(r"\/", "/").replace(r"\u002F", "/").replace(r"\u002f", "/")


def extract_embedded_detail_urls(
    html: str,
    base_url: str,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 12,
) -> tuple[str, ...]:
    """Reuse bounded deterministic detail URL extraction for JS/JSON-backed portals."""

    decoded = _decode_embedded_url_text(html)
    patterns = (
        r"https?://[^\s\"'<>]+",
        r"/(?:job|jobs|stellenangebote|offene-stellen|stellen-finden|karriere/jobs|karriere/offene-stellen)/[^\s\"'<>]+",
    )
    result: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, decoded, flags=re.IGNORECASE):
            raw = match.group(0).strip().strip("\"'`),;")
            candidate = canonical_url(urljoin(base_url, raw.replace("&amp;", "&")))
            if not candidate or candidate in seen:
                continue
            if not allowed_host(candidate, allowed_hosts) or non_job_url(candidate):
                continue
            if not job_detail_url_shape(candidate):
                continue
            seen.add(candidate)
            result.append(candidate)
            if len(result) >= limit:
                return tuple(result)
    return tuple(result)


def looks_like_listing_navigation(url: str, anchor_text: str) -> bool:
    if non_job_url(url) or job_detail_url_shape(url):
        return False
    parsed = urlparse(canonical_url(url))
    lowered_url_surface = f"{parsed.path}?{parsed.query}".casefold()
    lowered_text = normalize_whitespace(anchor_text).casefold()
    return any(marker in lowered_url_surface for marker in LISTING_URL_MARKERS) or any(
        marker in lowered_text for marker in LISTING_TEXT_MARKERS
    )


def _non_delegated_host(hostname: str) -> bool:
    lowered = hostname.casefold().strip(".")
    return any(
        lowered == suffix or lowered.endswith(f".{suffix}")
        for suffix in NON_DELEGATED_HOST_SUFFIXES
    )


def explicit_root_delegated_listing_hosts(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
) -> tuple[str, ...]:
    """Derive one-hop host delegation only from explicit employer-root job anchors."""

    delegated: list[str] = []
    seen: set[str] = set()
    for raw_url, anchor_text in page.links:
        clean = canonical_url(raw_url)
        parsed = urlparse(clean)
        hostname = (parsed.hostname or "").casefold()
        if parsed.scheme.casefold() != "https" or not hostname:
            continue
        if allowed_host(clean, allowed_hosts) or non_job_url(clean) or _non_delegated_host(hostname):
            continue
        lowered_text = normalize_whitespace(anchor_text).casefold()
        if not lowered_text or not any(marker in lowered_text for marker in LISTING_TEXT_MARKERS):
            continue
        if hostname in seen:
            continue
        seen.add(hostname)
        delegated.append(hostname)
    return tuple(delegated)


def _add_candidate(
    target: list[NavigationCandidate],
    seen: set[str],
    *,
    url: str,
    kind: str,
    discovery_source: str,
    anchor_text: str = "",
    known_detail: bool = False,
    allowed_hosts: tuple[str, ...] | set[str],
) -> None:
    clean = canonical_url(url)
    if (
        not clean
        or clean in seen
        or not allowed_host(clean, allowed_hosts)
        or non_job_url(clean)
    ):
        return
    seen.add(clean)
    target.append(
        NavigationCandidate(
            clean,
            kind,
            discovery_source,
            anchor_text,
            known_detail,
        )
    )


def _classified_navigation_candidates(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
) -> tuple[NavigationCandidate, ...]:
    """Project already-qualified deterministic Listing/Detail link evidence."""

    classification = classify_evidence_links(page.final_url, page.html, limit=500)
    result: list[NavigationCandidate] = []
    seen: set[str] = set()
    for item in classification.accepted:
        if item.evidence_type == "job_detail_candidate_evidence":
            _add_candidate(
                result,
                seen,
                url=item.url,
                kind="detail",
                discovery_source="classified_detail",
                anchor_text=item.label,
                allowed_hosts=allowed_hosts,
            )
        elif item.evidence_type == "job_search_page_evidence":
            _add_candidate(
                result,
                seen,
                url=item.url,
                kind="listing",
                discovery_source="classified_listing",
                anchor_text=item.label,
                allowed_hosts=allowed_hosts,
            )

    for item in extract_trusted_query_job_detail_links(page.final_url, page.html):
        _add_candidate(
            result,
            seen,
            url=item.url,
            kind="detail",
            discovery_source="query_detail",
            anchor_text=item.label,
            allowed_hosts=allowed_hosts,
        )
    return tuple(result)


def discover_navigation_candidates(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
    known_detail_urls: tuple[str, ...] = (),
) -> tuple[NavigationCandidate, ...]:
    """Rank concrete details before one bounded intermediate job-list hop."""

    current = canonical_url(page.final_url)
    seen: set[str] = {current}
    direct: list[NavigationCandidate] = []
    intermediate: list[NavigationCandidate] = []

    for url in known_detail_urls:
        _add_candidate(
            direct,
            seen,
            url=url,
            kind="detail",
            discovery_source="known_detail_evidence",
            known_detail=True,
            allowed_hosts=allowed_hosts,
        )

    for url, anchor_text in page.links:
        clean = canonical_url(url)
        if not clean or clean in seen or not allowed_host(clean, allowed_hosts) or non_job_url(clean):
            continue
        if job_detail_url_shape(clean):
            _add_candidate(
                direct,
                seen,
                url=clean,
                kind="detail",
                discovery_source="anchor_detail",
                anchor_text=anchor_text,
                allowed_hosts=allowed_hosts,
            )
            continue
        if looks_like_listing_navigation(clean, anchor_text):
            _add_candidate(
                intermediate,
                seen,
                url=clean,
                kind="listing",
                discovery_source="anchor_listing",
                anchor_text=anchor_text,
                allowed_hosts=allowed_hosts,
            )

    for item in _classified_navigation_candidates(page, allowed_hosts=allowed_hosts):
        target = direct if item.kind == "detail" else intermediate
        _add_candidate(
            target,
            seen,
            url=item.url,
            kind=item.kind,
            discovery_source=item.discovery_source,
            anchor_text=item.anchor_text,
            allowed_hosts=allowed_hosts,
        )

    for clean in extract_embedded_detail_urls(
        page.html,
        page.final_url,
        allowed_hosts=allowed_hosts,
    ):
        _add_candidate(
            direct,
            seen,
            url=clean,
            kind="detail",
            discovery_source="embedded_detail",
            allowed_hosts=allowed_hosts,
        )

    return tuple([*direct, *intermediate])


def genuine_job_detail_proof(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
    known_detail: bool = False,
) -> str | None:
    if page.status_code >= 400 or not allowed_host(page.final_url, allowed_hosts) or non_job_url(page.final_url):
        return None
    if len(page.html.encode("utf-8")) < 120:
        return None

    if re.search(r'["\']@type["\']\s*:\s*["\']JobPosting["\']', page.html, flags=re.IGNORECASE):
        return "jsonld_jobposting"

    title = normalize_whitespace(page.title)
    generic_title = not title or title.casefold() in GENERIC_PAGE_TITLES
    evidence = f"{page.title} {page.text} {page.html}".casefold()
    content_signal = any(marker in evidence for marker in JOB_CONTENT_MARKERS)

    if job_detail_url_shape(page.final_url) and content_signal and not generic_title:
        return "job_url_and_job_content"
    if known_detail and content_signal and not generic_title:
        return "known_detail_and_job_content"
    return None


def acquire_genuine_job_pages(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    known_detail_urls: tuple[str, ...],
    fetcher,
    max_followup_requests: int = 2,
    max_results: int = 1,
) -> tuple[list[AcquiredJobPage], str]:
    """Acquire genuine jobs without profile/location qualification.

    The default budget is exactly three logical requests total: one root/listing
    request plus at most two follow-ups. A direct employer-root jobs anchor may
    delegate one exact external recruiting host for this proof only; delegation
    is never transitive.
    """

    if max_followup_requests < 0:
        raise ValueError("max_followup_requests must be >= 0")
    if max_results < 1:
        raise ValueError("max_results must be >= 1")

    listing_html, listing_final_url, listing_status = fetcher(listing_url)
    root = parse_page(
        requested_url=listing_url,
        html=str(listing_html),
        final_url=str(listing_final_url),
        status_code=int(listing_status),
    )
    if root.status_code >= 400:
        raise RuntimeError(f"listing request failed with status {root.status_code}")
    if not allowed_host(root.final_url, allowed_hosts):
        raise RuntimeError("listing source binding mismatch")

    root_known = canonical_url(listing_url) in {
        canonical_url(url) for url in known_detail_urls
    }
    root_proof = genuine_job_detail_proof(
        root,
        allowed_hosts=allowed_hosts,
        known_detail=root_known,
    )
    if root_proof:
        return [
            AcquiredJobPage(
                requested_url=root.requested_url,
                final_url=root.final_url,
                status_code=root.status_code,
                title=root.title,
                html_bytes=len(root.html.encode("utf-8")),
                proof_kind=root_proof,
                discovery_source="listing_url_is_job_detail",
                anchor_text="",
            )
        ], root.final_url

    delegated_hosts = explicit_root_delegated_listing_hosts(
        root,
        allowed_hosts=allowed_hosts,
    )
    effective_allowed_hosts = tuple(dict.fromkeys([*allowed_hosts, *delegated_hosts]))

    remaining = max_followup_requests
    queue: list[tuple[NavigationCandidate, int]] = [
        (candidate, 0)
        for candidate in discover_navigation_candidates(
            root,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    ]
    fetched: set[str] = {
        canonical_url(root.requested_url),
        canonical_url(root.final_url),
    }
    results: list[AcquiredJobPage] = []

    while queue and remaining > 0 and len(results) < max_results:
        candidate, depth = queue.pop(0)
        clean = canonical_url(candidate.url)
        if not clean or clean in fetched:
            continue
        fetched.add(clean)
        remaining -= 1
        html, final_url, status_code = fetcher(candidate.url)
        page = parse_page(
            requested_url=candidate.url,
            html=str(html),
            final_url=str(final_url),
            status_code=int(status_code),
        )
        proof = genuine_job_detail_proof(
            page,
            allowed_hosts=effective_allowed_hosts,
            known_detail=candidate.known_detail,
        )
        if proof:
            results.append(
                AcquiredJobPage(
                    requested_url=page.requested_url,
                    final_url=page.final_url,
                    status_code=page.status_code,
                    title=page.title,
                    html_bytes=len(page.html.encode("utf-8")),
                    proof_kind=proof,
                    discovery_source=candidate.discovery_source,
                    anchor_text=candidate.anchor_text,
                )
            )
            continue

        if candidate.kind == "listing" and depth == 0 and remaining > 0:
            discovered = discover_navigation_candidates(
                page,
                allowed_hosts=effective_allowed_hosts,
                known_detail_urls=(),
            )
            next_items = [
                (item, 1)
                for item in discovered
                if item.kind == "detail" and canonical_url(item.url) not in fetched
            ]
            queue = [*next_items, *queue]

    return results, root.final_url
