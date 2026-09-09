from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Callable
from urllib.parse import parse_qsl, urlparse

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    PageSnapshot,
    allowed_host,
    canonical_url,
    explicit_root_delegated_listing_hosts,
    genuine_job_detail_proof,
    parse_page,
)
from src.connectors.employer_origin_acquisition_v4 import discover_navigation_candidates
from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_listing_urls,
)
from src.connectors.employer_origin_form_navigation import (
    JobSearchFormRequest,
    discover_strict_job_search_form_requests,
)
from src.connectors.employer_origin_workday_detail import (
    workday_cxs_detail_page,
    workday_cxs_detail_url,
)
from src.connectors.employer_origin_workday_navigation import (
    WorkdayBoardRoute,
    explicit_workday_board_routes_from_employer_page,
    workday_board_route,
)

MAX_BODY_BYTES = 5_000_000
DEFAULT_PAGE_SIZE = 20
DEFAULT_PAGE_CAP = 3
DEFAULT_JOB_CAP = 30

_KEYWORD_FIELD_EXACT = frozenset({"q", "query", "keyword", "keywords", "search", "searchtext"})
_KEYWORD_FIELD_MARKERS = ("keyword", "search", "query", "job", "position", "vacan", "stellen")
_NON_KEYWORD_FIELD_MARKERS = (
    "location",
    "city",
    "zip",
    "postal",
    "radius",
    "department",
    "category",
    "country",
    "region",
)
_NEXT_LABELS = frozenset(
    {
        "next",
        "next page",
        "weiter",
        "weiter >",
        "nächste",
        "nächster",
        "nächste seite",
        ">",
        "›",
        "»",
    }
)
_PAGE_KEYS = frozenset({"page", "p", "pagenumber", "pageindex", "offset", "start"})


@dataclass(frozen=True)
class SearchRequest:
    url: str
    method: str = "GET"
    fields: tuple[tuple[str, object], ...] = ()
    payload_kind: str = "query"


@dataclass(frozen=True)
class GenericSearchOutcome:
    mechanism: str
    query: str
    pages_requested: int
    detail_candidates_seen: int
    jobs: tuple[AcquiredJobPage, ...]
    exhausted: bool
    stop_reason: str
    final_url: str


RequestExecutor = Callable[[SearchRequest], tuple[str, str, int]]


def _bounded_body(value: object) -> str:
    text = str(value)
    if len(text.encode("utf-8", errors="replace")) > MAX_BODY_BYTES:
        raise RuntimeError("generic search response body cap exceeded")
    return text


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().strip(".")


def _workday_route(
    root: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...],
) -> WorkdayBoardRoute | None:
    direct = workday_board_route(root.final_url, allowed_hosts=allowed_hosts)
    if direct is not None:
        return direct
    routes = explicit_workday_board_routes_from_employer_page(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=allowed_hosts,
        limit=2,
    )
    return routes[0] if len(routes) == 1 else None


def _workday_inventory_fields(
    *,
    query: str,
    limit: int,
    offset: int,
) -> tuple[tuple[str, object], ...]:
    return (
        ("appliedFacets", {}),
        ("limit", limit),
        ("offset", offset),
        ("searchText", query),
    )


def _workday_postings(body: str) -> tuple[list[dict], int | None]:
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return [], None
    if not isinstance(payload, dict):
        return [], None
    postings = payload.get("jobPostings")
    if not isinstance(postings, list):
        return [], None
    rows = [row for row in postings if isinstance(row, dict)]
    total = payload.get("total")
    return rows, int(total) if isinstance(total, int) and total >= 0 else None


def _workday_public_detail(
    route: WorkdayBoardRoute,
    posting: dict,
) -> str | None:
    value = posting.get("externalPath")
    if not isinstance(value, str) or len(value) > 700:
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/job/")
        or "//" in parsed.path
        or any(segment in {".", ".."} for segment in parsed.path.split("/"))
    ):
        return None
    return f"{route.public_board_url}{parsed.path}"


def _prove_workday_detail(
    *,
    route: WorkdayBoardRoute,
    public_detail_url: str,
    execute: RequestExecutor,
) -> AcquiredJobPage | None:
    cxs_url = workday_cxs_detail_url(
        public_detail_url,
        public_board_url=route.public_board_url,
        allowed_hosts={route.host},
    )
    if cxs_url is None:
        return None
    body_raw, final_raw, status_raw = execute(SearchRequest(cxs_url))
    body = _bounded_body(body_raw)
    page = workday_cxs_detail_page(
        public_detail_url=public_detail_url,
        public_board_url=route.public_board_url,
        response_url=str(final_raw),
        status_code=int(status_raw),
        body=body,
        allowed_hosts={route.host},
    )
    if page is None:
        return None
    proof = genuine_job_detail_proof(page, allowed_hosts={route.host}, known_detail=True)
    if not proof:
        return None
    return AcquiredJobPage(
        requested_url=public_detail_url,
        final_url=public_detail_url,
        status_code=int(status_raw),
        title=page.title,
        html_bytes=len(page.html.encode("utf-8", errors="replace")),
        proof_kind=proof,
        discovery_source="workday_targeted_search",
        anchor_text="",
    )


def search_workday(
    *,
    root: PageSnapshot,
    query: str,
    allowed_hosts: tuple[str, ...],
    execute: RequestExecutor,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_cap: int = DEFAULT_PAGE_CAP,
    job_cap: int = DEFAULT_JOB_CAP,
) -> GenericSearchOutcome | None:
    route = _workday_route(root, allowed_hosts=allowed_hosts)
    if route is None:
        return None

    jobs: list[AcquiredJobPage] = []
    seen_details: set[str] = set()
    pages = 0
    candidates_seen = 0
    exhausted = False
    stop_reason = "page_cap"

    for page_index in range(page_cap):
        offset = page_index * page_size
        request = SearchRequest(
            route.inventory_url,
            "POST",
            _workday_inventory_fields(
                query=query,
                limit=page_size,
                offset=offset,
            ),
            "json",
        )
        body_raw, final_raw, status_raw = execute(request)
        pages += 1
        body = _bounded_body(body_raw)
        if int(status_raw) >= 400 or canonical_url(str(final_raw)) != canonical_url(
            route.inventory_url
        ):
            return GenericSearchOutcome(
                "workday_cxs",
                query,
                pages,
                candidates_seen,
                tuple(jobs),
                False,
                "inventory_request_failed",
                root.final_url,
            )
        postings, total = _workday_postings(body)
        if not postings:
            exhausted = True
            stop_reason = "empty_page"
            break
        new_on_page = 0
        for posting in postings:
            detail_url = _workday_public_detail(route, posting)
            if not detail_url or detail_url in seen_details:
                continue
            seen_details.add(detail_url)
            candidates_seen += 1
            new_on_page += 1
            job = _prove_workday_detail(
                route=route,
                public_detail_url=detail_url,
                execute=execute,
            )
            if job is not None:
                jobs.append(job)
            if len(jobs) >= job_cap:
                return GenericSearchOutcome(
                    "workday_cxs",
                    query,
                    pages,
                    candidates_seen,
                    tuple(jobs),
                    False,
                    "job_cap",
                    root.final_url,
                )
        if total is not None and offset + len(postings) >= total:
            exhausted = True
            stop_reason = "reported_total_exhausted"
            break
        if len(postings) < page_size:
            exhausted = True
            stop_reason = "short_page"
            break
        if new_on_page == 0:
            exhausted = True
            stop_reason = "no_new_candidates"
            break

    return GenericSearchOutcome(
        "workday_cxs",
        query,
        pages,
        candidates_seen,
        tuple(jobs),
        exhausted,
        stop_reason,
        root.final_url,
    )


def _keyword_field_name(form: JobSearchFormRequest) -> str | None:
    candidates: list[str] = []
    for name, _value in form.fields:
        lowered = name.casefold()
        if any(marker in lowered for marker in _NON_KEYWORD_FIELD_MARKERS):
            continue
        if lowered in _KEYWORD_FIELD_EXACT or any(
            marker in lowered for marker in _KEYWORD_FIELD_MARKERS
        ):
            candidates.append(name)
    distinct = list(dict.fromkeys(candidates))
    return distinct[0] if len(distinct) == 1 else None


def bind_search_form(
    form: JobSearchFormRequest,
    query: str,
) -> SearchRequest | None:
    keyword_name = _keyword_field_name(form)
    if keyword_name is None:
        return None
    fields = tuple(
        (name, query if name == keyword_name else value)
        for name, value in form.fields
    )
    return SearchRequest(
        form.url,
        form.method,
        fields,
        "query" if form.method.upper() == "GET" else "form",
    )


def _same_host(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme.casefold() == "https" and _host(url) == host


def _next_page_url(
    page: PageSnapshot,
    *,
    host: str,
    seen: set[str],
) -> str | None:
    next_labeled: list[str] = []
    numeric: list[tuple[int, str]] = []
    for raw_url, raw_label in page.links:
        url = canonical_url(raw_url)
        if not url or url in seen or not _same_host(url, host):
            continue
        label = re.sub(r"\s+", " ", raw_label or "").strip().casefold()
        if label in _NEXT_LABELS:
            next_labeled.append(url)
            continue
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        page_values = [
            value for key, value in query.items() if key.casefold() in _PAGE_KEYS
        ]
        if not page_values or not label.isdigit():
            continue
        numeric.append((int(label), url))
    distinct_next = list(dict.fromkeys(next_labeled))
    if len(distinct_next) == 1:
        return distinct_next[0]
    if numeric:
        numeric.sort()
        return numeric[0][1]
    return None


def _detail_candidates(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...],
) -> list[tuple[str, str, bool]]:
    result: list[tuple[str, str, bool]] = []
    for item in discover_navigation_candidates(page, allowed_hosts=allowed_hosts):
        if item.kind != "detail":
            continue
        result.append((item.url, item.discovery_source, item.known_detail))
    return result


def _prove_html_detail(
    *,
    detail_url: str,
    discovery_source: str,
    known_detail: bool,
    allowed_hosts: tuple[str, ...],
    execute: RequestExecutor,
) -> AcquiredJobPage | None:
    body_raw, final_raw, status_raw = execute(SearchRequest(detail_url))
    body = _bounded_body(body_raw)
    page = parse_page(
        requested_url=detail_url,
        html=body,
        final_url=str(final_raw),
        status_code=int(status_raw),
    )
    proof = genuine_job_detail_proof(
        page,
        allowed_hosts=allowed_hosts,
        known_detail=known_detail,
    )
    if not proof:
        return None
    return AcquiredJobPage(
        requested_url=page.requested_url,
        final_url=page.final_url,
        status_code=page.status_code,
        title=page.title,
        html_bytes=len(page.html.encode("utf-8", errors="replace")),
        proof_kind=proof,
        discovery_source=f"targeted_search:{discovery_source}",
        anchor_text="",
    )


def search_form_surface(
    *,
    root: PageSnapshot,
    query: str,
    allowed_hosts: tuple[str, ...],
    execute: RequestExecutor,
    page_cap: int = DEFAULT_PAGE_CAP,
    job_cap: int = DEFAULT_JOB_CAP,
) -> GenericSearchOutcome | None:
    forms = discover_strict_job_search_form_requests(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=allowed_hosts,
    )
    if len(forms) != 1:
        return None
    request = bind_search_form(forms[0], query)
    if request is None:
        return None

    jobs: list[AcquiredJobPage] = []
    seen_pages: set[str] = set()
    seen_details: set[str] = set()
    pages = 0
    candidates_seen = 0
    current = request
    host = _host(request.url)
    exhausted = False
    stop_reason = "page_cap"

    while pages < page_cap:
        body_raw, final_raw, status_raw = execute(current)
        pages += 1
        body = _bounded_body(body_raw)
        page = parse_page(
            requested_url=current.url,
            html=body,
            final_url=str(final_raw),
            status_code=int(status_raw),
        )
        if page.status_code >= 400 or not allowed_host(
            page.final_url,
            allowed_hosts,
        ):
            return GenericSearchOutcome(
                "strict_html_form",
                query,
                pages,
                candidates_seen,
                tuple(jobs),
                False,
                "search_request_failed",
                root.final_url,
            )
        page_key = canonical_url(page.final_url)
        if page_key in seen_pages:
            exhausted = True
            stop_reason = "repeated_page"
            break
        seen_pages.add(page_key)

        new_candidates = 0
        for detail_url, discovery_source, known_detail in _detail_candidates(
            page,
            allowed_hosts=allowed_hosts,
        ):
            clean = canonical_url(detail_url)
            if not clean or clean in seen_details:
                continue
            seen_details.add(clean)
            candidates_seen += 1
            new_candidates += 1
            job = _prove_html_detail(
                detail_url=detail_url,
                discovery_source=discovery_source,
                known_detail=known_detail,
                allowed_hosts=allowed_hosts,
                execute=execute,
            )
            if job is not None:
                jobs.append(job)
            if len(jobs) >= job_cap:
                return GenericSearchOutcome(
                    "strict_html_form",
                    query,
                    pages,
                    candidates_seen,
                    tuple(jobs),
                    False,
                    "job_cap",
                    root.final_url,
                )

        next_url = _next_page_url(page, host=host, seen=seen_pages)
        if next_url is None:
            exhausted = True
            stop_reason = "no_next_page"
            break
        if new_candidates == 0 and pages > 1:
            exhausted = True
            stop_reason = "no_new_candidates"
            break
        current = SearchRequest(next_url)

    return GenericSearchOutcome(
        "strict_html_form",
        query,
        pages,
        candidates_seen,
        tuple(jobs),
        exhausted,
        stop_reason,
        root.final_url,
    )


def _single_listing_surface(
    root: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...],
) -> str | None:
    delegated_hosts = explicit_root_delegated_listing_hosts(
        root,
        allowed_hosts=allowed_hosts,
    )
    effective_hosts = tuple(dict.fromkeys([*allowed_hosts, *delegated_hosts]))
    provider = authorized_ats_provider(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=allowed_hosts,
        delegated_hosts=delegated_hosts,
    )
    if provider:
        urls = provider_listing_urls(
            provider=provider,
            page_url=root.final_url,
            html=root.html,
            allowed_hosts=effective_hosts,
        )
        if len(urls) == 1:
            return urls[0]
    listings = [
        item.url
        for item in discover_navigation_candidates(
            root,
            allowed_hosts=effective_hosts,
        )
        if item.kind == "listing"
    ]
    listings = list(dict.fromkeys(listings))
    return listings[0] if len(listings) == 1 else None


def search_generic_origin(
    *,
    origin_url: str,
    query: str,
    execute: RequestExecutor,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_cap: int = DEFAULT_PAGE_CAP,
    job_cap: int = DEFAULT_JOB_CAP,
) -> GenericSearchOutcome:
    root_body_raw, root_final_raw, root_status_raw = execute(
        SearchRequest(origin_url)
    )
    root_body = _bounded_body(root_body_raw)
    root = parse_page(
        requested_url=origin_url,
        html=root_body,
        final_url=str(root_final_raw),
        status_code=int(root_status_raw),
    )
    root_host = _host(root.final_url)
    if root.status_code >= 400 or not root_host:
        return GenericSearchOutcome(
            "none",
            query,
            1,
            0,
            (),
            False,
            "origin_unreachable",
            root.final_url,
        )
    allowed_hosts: tuple[str, ...] = (root_host,)

    outcome = search_workday(
        root=root,
        query=query,
        allowed_hosts=allowed_hosts,
        execute=execute,
        page_size=page_size,
        page_cap=page_cap,
        job_cap=job_cap,
    )
    if outcome is not None:
        return outcome

    outcome = search_form_surface(
        root=root,
        query=query,
        allowed_hosts=allowed_hosts,
        execute=execute,
        page_cap=page_cap,
        job_cap=job_cap,
    )
    if outcome is not None:
        return outcome

    listing_url = _single_listing_surface(root, allowed_hosts=allowed_hosts)
    if listing_url:
        listing_host = _host(listing_url)
        effective_hosts = tuple(dict.fromkeys([root_host, listing_host]))
        body_raw, final_raw, status_raw = execute(SearchRequest(listing_url))
        listing = parse_page(
            requested_url=listing_url,
            html=_bounded_body(body_raw),
            final_url=str(final_raw),
            status_code=int(status_raw),
        )
        if listing.status_code < 400:
            outcome = search_workday(
                root=listing,
                query=query,
                allowed_hosts=effective_hosts,
                execute=execute,
                page_size=page_size,
                page_cap=page_cap,
                job_cap=job_cap,
            )
            if outcome is not None:
                return outcome
            outcome = search_form_surface(
                root=listing,
                query=query,
                allowed_hosts=effective_hosts,
                execute=execute,
                page_cap=page_cap,
                job_cap=job_cap,
            )
            if outcome is not None:
                return outcome

    return GenericSearchOutcome(
        "none",
        query,
        1,
        0,
        (),
        False,
        "no_deterministic_targeted_search_surface",
        root.final_url,
    )


__all__ = [
    "DEFAULT_JOB_CAP",
    "DEFAULT_PAGE_CAP",
    "DEFAULT_PAGE_SIZE",
    "GenericSearchOutcome",
    "SearchRequest",
    "bind_search_form",
    "search_generic_origin",
    "search_workday",
]
