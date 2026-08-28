"""Strict deterministic Workday board navigation for employer-origin acquisition.

This module performs no network I/O and grants no host authority. It derives
Workday's public CXS inventory route only from an already-authorized canonical
``*.wdN.myworkdayjobs.com`` board URL, or from explicit canonical Workday anchors
observed on an already-authorized employer page when those anchors provide
unambiguous board context. Callers remain responsible for granting target-host
authority, metering requests, and proving final job details with the canonical
acceptance boundary.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

from src.search_intelligence.ats_provider_registry import recognize_ats_provider


_WORKDAY_HOST = re.compile(
    r"^(?P<tenant>[a-z0-9][a-z0-9-]{0,62})\.wd(?P<shard>[0-9]{1,3})\.myworkdayjobs\.com$",
    flags=re.IGNORECASE,
)
_WORKDAY_LOCALE = re.compile(r"^[a-z]{2}-[a-z]{2}$", flags=re.IGNORECASE)
_WORKDAY_SITE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_RESERVED_SITE_SEGMENTS = {
    "introduceyourself",
    "job",
    "jobs",
    "login",
    "wday",
}
_WORKDAY_CONTROL_SEGMENTS = frozenset({"introduceyourself", "login"})
_ANCHOR = re.compile(
    r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class WorkdayBoardRoute:
    host: str
    tenant: str
    site: str
    locale: str
    public_board_url: str
    inventory_url: str


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _authorized_host(value: str, allowed_hosts: tuple[str, ...] | set[str]) -> bool:
    host = _host(value)
    normalized = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(host and host in normalized)


def _visible_text(raw: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", raw or ""))).strip()


def workday_board_route(
    page_url: str,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
) -> WorkdayBoardRoute | None:
    """Derive one exact public Workday board/CXS pair from an authorized board URL."""

    if not _authorized_host(page_url, allowed_hosts):
        return None
    recognition = recognize_ats_provider(page_url)
    if recognition is None or recognition.provider != "workday":
        return None

    parsed = urlparse(page_url)
    host = _host(page_url)
    match = _WORKDAY_HOST.fullmatch(host)
    if match is None or parsed.scheme.casefold() != "https":
        return None

    segments = [segment for segment in parsed.path.split("/") if segment]
    locale = ""
    if len(segments) == 1:
        site = segments[0]
    elif len(segments) == 2 and _WORKDAY_LOCALE.fullmatch(segments[0]):
        locale, site = segments
    else:
        return None
    if not _WORKDAY_SITE.fullmatch(site) or site.casefold() in _RESERVED_SITE_SEGMENTS:
        return None

    tenant = match.group("tenant").casefold()
    public_path = f"/{locale}/{site}" if locale else f"/{site}"
    public_board_url = f"https://{host}{public_path}"
    inventory_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    return WorkdayBoardRoute(
        host=host,
        tenant=tenant,
        site=site,
        locale=locale,
        public_board_url=public_board_url,
        inventory_url=inventory_url,
    )


def explicit_workday_board_routes_from_employer_page(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 3,
) -> tuple[WorkdayBoardRoute, ...]:
    """Derive Workday boards from explicit canonical anchors without guessing.

    A visible canonical board anchor is sufficient. Control-path evidence is more
    constrained: at least two distinct observed control kinds (currently
    ``login`` and ``introduceYourself``) must agree on the exact canonical host,
    locale and site before their common board prefix is emitted. A company name,
    provider-name text, or one isolated control URL can never create a board.
    """

    if limit < 1 or not _authorized_host(page_url, allowed_hosts):
        return ()

    evidence: dict[tuple[str, str, str], dict[str, object]] = {}
    for raw_href, raw_label in _ANCHOR.findall(html or ""):
        label = _visible_text(raw_label)
        if not label:
            continue
        candidate = urljoin(page_url, unescape(raw_href).strip())
        parsed = urlparse(candidate)
        host = _host(candidate)
        if parsed.scheme.casefold() != "https" or not host or _WORKDAY_HOST.fullmatch(host) is None:
            continue
        recognition = recognize_ats_provider(candidate)
        if recognition is None or recognition.provider != "workday":
            continue

        segments = [segment for segment in parsed.path.split("/") if segment]
        locale = ""
        site = ""
        control = ""
        direct = False

        if len(segments) == 1:
            site = segments[0]
            direct = True
        elif len(segments) == 2:
            if _WORKDAY_LOCALE.fullmatch(segments[0]):
                locale, site = segments
                direct = True
            elif segments[1].casefold() in _WORKDAY_CONTROL_SEGMENTS:
                site, control = segments
                control = control.casefold()
        elif (
            len(segments) == 3
            and _WORKDAY_LOCALE.fullmatch(segments[0])
            and segments[2].casefold() in _WORKDAY_CONTROL_SEGMENTS
        ):
            locale, site, control = segments
            control = control.casefold()
        else:
            continue

        if not _WORKDAY_SITE.fullmatch(site) or site.casefold() in _RESERVED_SITE_SEGMENTS:
            continue

        key = (host, locale, site)
        bucket = evidence.setdefault(key, {"direct": False, "controls": set()})
        if direct:
            bucket["direct"] = True
        elif control:
            controls = bucket["controls"]
            if isinstance(controls, set):
                controls.add(control)

    result: list[WorkdayBoardRoute] = []
    for (host, locale, site), bucket in evidence.items():
        controls = bucket.get("controls")
        control_count = len(controls) if isinstance(controls, set) else 0
        if not bool(bucket.get("direct")) and control_count < 2:
            continue
        path = f"/{locale}/{site}" if locale else f"/{site}"
        route = workday_board_route(
            f"https://{host}{path}",
            allowed_hosts={host},
        )
        if route is None:
            continue
        result.append(route)
        if len(result) >= limit:
            break
    return tuple(result)


def workday_inventory_json_fields() -> tuple[tuple[str, object], ...]:
    """Return the bounded first-page CXS request body without pagination."""

    return (
        ("appliedFacets", {}),
        ("limit", 20),
        ("offset", 0),
        ("searchText", ""),
    )


def workday_detail_urls_from_inventory(
    *,
    inventory_url: str,
    body: str,
    public_board_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 5,
) -> tuple[str, ...]:
    """Project strict public Workday detail URLs from one exact CXS inventory."""

    if limit < 1:
        return ()
    board = workday_board_route(public_board_url, allowed_hosts=allowed_hosts)
    if board is None or inventory_url.split("#", 1)[0].rstrip("/") != board.inventory_url:
        return ()

    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return ()
    postings = payload.get("jobPostings") if isinstance(payload, dict) else None
    if not isinstance(postings, list):
        return ()

    result: list[str] = []
    seen: set[str] = set()
    for posting in postings:
        if not isinstance(posting, dict):
            continue
        external_path = posting.get("externalPath")
        if not isinstance(external_path, str) or len(external_path) > 700:
            continue
        parsed = urlparse(external_path)
        path = parsed.path
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or not path.startswith("/job/")
            or "//" in path
            or any(segment in {".", ".."} for segment in path.split("/"))
        ):
            continue
        candidate = f"{board.public_board_url}{path}"
        if candidate in seen or not _authorized_host(candidate, allowed_hosts):
            continue
        seen.add(candidate)
        result.append(candidate)
        if len(result) >= limit:
            break
    return tuple(result)


__all__ = [
    "WorkdayBoardRoute",
    "explicit_workday_board_routes_from_employer_page",
    "workday_board_route",
    "workday_detail_urls_from_inventory",
    "workday_inventory_json_fields",
]
