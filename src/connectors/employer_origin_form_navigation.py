"""Strict deterministic job-search form discovery for employer-origin acquisition.

The helpers in this module do not perform network I/O. They only turn an HTML
form into a bounded request description when the form is visibly search/filter
oriented, remains on an already-authorized HTTPS host, and contains no login,
application-upload, contact, or newsletter controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from src.connectors.employer_origin_acquisition import (
    allowed_host,
    canonical_url,
    non_job_url,
)


SEARCH_FIELD_MARKERS = (
    "filter",
    "search",
    "query",
    "keyword",
    "job",
    "position",
    "vacan",
    "stellen",
    "location",
    "city",
    "zip",
    "radius",
    "department",
    "category",
)

JOB_ACTION_MARKERS = (
    "/jobs",
    "/job-search",
    "/jobsearch",
    "/jobsuche",
    "/stellen",
    "/vacan",
    "/positions",
    "/openings",
    "/opportunities",
    "/offers",
    "/career",
    "/karriere",
)

JOB_CONTEXT_MARKERS = (
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "stellen",
    "vacan",
    "recruit",
)

BLOCKED_FIELD_MARKERS = (
    "password",
    "passwd",
    "username",
    "login",
    "email",
    "e-mail",
    "attachment",
    "upload",
    "resume",
    "cv",
    "coverletter",
    "cover_letter",
    "application",
    "bewerbung",
    "newsletter",
    "contact",
    "kontakt",
)

BLOCKED_ACTION_MARKERS = (
    "/login",
    "/signin",
    "/sign-in",
    "/apply",
    "/application",
    "/bewerbung",
    "/contact",
    "/kontakt",
    "/newsletter",
)

MAX_FORM_FIELDS = 20
MAX_FORM_PAYLOAD_CHARS = 4096


@dataclass(frozen=True)
class JobSearchFormRequest:
    url: str
    method: str
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _Control:
    name: str
    input_type: str
    value: str
    checked: bool


@dataclass(frozen=True)
class _RawForm:
    action: str
    method: str
    controls: tuple[_Control, ...]


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[_RawForm] = []
        self._action: str | None = None
        self._method = "GET"
        self._controls: list[_Control] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        attributes = {str(name).casefold(): str(value or "") for name, value in attrs}
        if lowered == "form":
            if self._action is not None:
                return
            self._action = attributes.get("action", "")
            self._method = (attributes.get("method") or "GET").upper()
            self._controls = []
            return
        if lowered != "input" or self._action is None:
            return
        name = attributes.get("name", "").strip()
        if not name:
            return
        self._controls.append(
            _Control(
                name=name,
                input_type=(attributes.get("type") or "text").casefold(),
                value=attributes.get("value", ""),
                checked="checked" in attributes,
            )
        )

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "form" or self._action is None:
            return
        self.forms.append(
            _RawForm(
                action=self._action,
                method=self._method,
                controls=tuple(self._controls),
            )
        )
        self._action = None
        self._method = "GET"
        self._controls = []


def _contains_marker(value: str, markers: tuple[str, ...]) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in markers)


def _compact_query_allowed(*, page_url: str, action: str) -> bool:
    """Allow an otherwise ambiguous ``q`` field only on a strict job search surface."""

    page = urlparse(page_url)
    target = urlparse(action)
    page_surface = f"{page.hostname or ''}{page.path}".casefold()
    target_path = (target.path or "").rstrip("/").casefold()
    return target_path == "/search" and _contains_marker(page_surface, JOB_CONTEXT_MARKERS)


def _request_fields(
    controls: tuple[_Control, ...],
    *,
    allow_compact_query: bool = False,
) -> tuple[tuple[str, str], ...] | None:
    if len(controls) > MAX_FORM_FIELDS:
        return None

    result: list[tuple[str, str]] = []
    searchable = 0
    for control in controls:
        name = control.name.strip()
        lowered_name = name.casefold()
        if _contains_marker(lowered_name, BLOCKED_FIELD_MARKERS):
            return None
        if control.input_type in {"password", "email", "file"}:
            return None
        if control.input_type in {"submit", "button", "reset", "image"}:
            continue
        if control.input_type in {"checkbox", "radio"} and not control.checked:
            continue

        compact_query = allow_compact_query and lowered_name == "q"
        if _contains_marker(lowered_name, SEARCH_FIELD_MARKERS) or compact_query:
            searchable += 1
        if (
            control.input_type == "hidden"
            or _contains_marker(lowered_name, SEARCH_FIELD_MARKERS)
            or compact_query
        ):
            result.append((name, control.value))

    if searchable == 0:
        return None
    if sum(len(name) + len(value) for name, value in result) > MAX_FORM_PAYLOAD_CHARS:
        return None
    return tuple(result)


def discover_strict_job_search_form_requests(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> tuple[JobSearchFormRequest, ...]:
    """Return only explicit, same-authority GET/POST search-form requests.

    Search/filter field names are required. A compact ``q`` field is accepted only
    for an exact same-authority ``/search`` action when the source page itself has
    explicit job/career context. Login/application/contact/newsletter controls
    fail closed. Multiple distinct forms are returned to the caller so the
    acquisition layer can refuse ambiguous execution rather than ranking by guesswork.
    """

    parser = _FormParser()
    parser.feed(html or "")

    result: list[JobSearchFormRequest] = []
    seen: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
    for form in parser.forms:
        if form.method not in {"GET", "POST"}:
            continue
        action = canonical_url(urljoin(page_url, form.action or page_url))
        parsed = urlparse(action)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        if not allowed_host(action, allowed_hosts) or non_job_url(action):
            continue
        if _contains_marker(f"{parsed.path}?{parsed.query}", BLOCKED_ACTION_MARKERS):
            continue

        compact_query = _compact_query_allowed(page_url=page_url, action=action)
        fields = _request_fields(form.controls, allow_compact_query=compact_query)
        if fields is None:
            continue
        field_surface = " ".join(name for name, _value in fields)
        if not (
            _contains_marker(f"{parsed.path}?{parsed.query}", JOB_ACTION_MARKERS)
            or _contains_marker(field_surface, SEARCH_FIELD_MARKERS)
            or compact_query
        ):
            continue

        key = (action, form.method, fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(JobSearchFormRequest(action, form.method, fields))

    return tuple(result)


__all__ = [
    "JobSearchFormRequest",
    "discover_strict_job_search_form_requests",
]
