"""Deterministic B-ITE Employer-Origin provider adapter.

Authority is derived only from an employer page that embeds the public B-ITE loader
and exactly one tenant/listing binding.  The tenant asset may then supply the
public runtime configuration required for the provider inventory endpoint.  No
employer, tenant, key, job id, or vacancy URL is hard-coded here.

The adapter deliberately keeps provider mechanics separate from source validity.
Callers must still pass a concrete detail through the unchanged
``genuine_job_detail_proof`` gate before treating it as a real job.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from urllib.parse import urlparse

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    PageSnapshot,
    canonical_url,
    genuine_job_detail_proof,
)

BITE_LOADER_URL = "https://static.b-ite.com/jobs-api/loader-v1/api-loader-v1.min.js"
BITE_ASSET_HOST = "cs-assets.b-ite.com"
BITE_API_HOST = "jobs.b-ite.com"
BITE_API_ENDPOINT = "https://jobs.b-ite.com/api/v1/postings/search"
# Public provider protocol marker used by the already-qualified JobsApi-v5 probe.
# It is provider-wide transport metadata, not tenant or employer authority.
BITE_JOBS_API_CLIENT = "v5-20260624-f577606"
BITE_MAX_PAGE_SIZE = 1000
BITE_MAX_POSTINGS = 1000
BITE_MAX_RAW_BYTES = 5_000_000

_BINDING_RE = re.compile(
    r"data-bite-jobs-api-listing\s*=\s*['\"]"
    r"(?P<customer>[a-zA-Z0-9_-]{1,80}):(?P<asset>[a-zA-Z0-9_-]{1,160})"
    r"['\"]",
    flags=re.IGNORECASE,
)
_KEY_RE = re.compile(r"(?:['\"]?key['\"]?)\s*:\s*['\"]([0-9a-fA-F]{32,128})['\"]")
_JS_IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]{0,80}"
_JS_NUMBER = r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
_CHANNEL_RE = re.compile(
    rf"(?:['\"]?channel['\"]?)\s*:\s*(?P<value>{_JS_NUMBER}|{_JS_IDENTIFIER})",
    flags=re.IGNORECASE,
)
_LOCALE_RE = re.compile(r"(?:['\"]?locale['\"]?)\s*:\s*['\"]([A-Za-z0-9_-]{2,16})['\"]")
_PAGE_RE = re.compile(
    rf"(?:['\"]?page['\"]?)\s*:\s*\{{[^{{}}]{{0,500}}?"
    rf"(?:['\"]?offset['\"]?)\s*:\s*(?P<offset>{_JS_NUMBER})[^{{}}]{{0,300}}?"
    rf"(?:['\"]?num['\"]?)\s*:\s*(?P<num>{_JS_NUMBER})[^{{}}]{{0,300}}?\}}",
    flags=re.IGNORECASE | re.DOTALL,
)
_SORT_RE = re.compile(
    r"(?:['\"]?sort['\"]?)\s*:\s*\{[^{}]{0,500}?"
    r"(?:['\"]?by['\"]?)\s*:\s*['\"]([^'\"]{1,80})['\"][^{}]{0,300}?"
    r"(?:['\"]?order['\"]?)\s*:\s*['\"](asc|desc)['\"][^{}]{0,300}?\}",
    flags=re.IGNORECASE | re.DOTALL,
)
_FILTER_RE = re.compile(
    r"(?:['\"]?filter['\"]?)\s*:\s*\{\s*"
    r"['\"]?([A-Za-z0-9_.-]{1,128})['\"]?\s*:\s*\{\s*"
    r"['\"]?in['\"]?\s*:\s*\[([^\]]{1,1000})\]",
    flags=re.IGNORECASE | re.DOTALL,
)
_JS_IDENTIFIER_RE = re.compile(rf"^{_JS_IDENTIFIER}$")
_JS_NUMBER_RE = re.compile(rf"^{_JS_NUMBER}$", flags=re.IGNORECASE)
_JS_STRING_RE = re.compile(r"^(['\"])([^'\"]{1,128})\1$")
_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9+#.]{2,}")


@dataclass(frozen=True)
class BiteBinding:
    employer_page_url: str
    customer: str
    asset_name: str
    asset_url: str


@dataclass(frozen=True)
class BiteRuntimeConfig:
    customer: str
    public_key: str
    channel: int
    locale: str
    page_offset: int
    page_num: int
    sort_by: str
    sort_order: str
    filter_key: str
    filter_values: tuple[str, ...]


@dataclass(frozen=True)
class BitePosting:
    posting_id: str
    title: str
    url: str
    apply_url: str
    employer_name: str
    raw: dict[str, object]


def _https_url(value: object, *, host: str | None = None) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 2000:
        return None
    parsed = urlparse(value)
    actual_host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme.casefold() != "https"
        or not actual_host
        or parsed.username
        or parsed.password
        or (host is not None and actual_host != host.casefold())
    ):
        return None
    return value


def _integer_js_number(value: str) -> int | None:
    if _JS_NUMBER_RE.fullmatch(value.strip()) is None:
        return None
    try:
        number = Decimal(value.strip())
    except InvalidOperation:
        return None
    integral = number.to_integral_value()
    if number != integral:
        return None
    try:
        return int(integral)
    except (OverflowError, ValueError):
        return None


def _scalar_assignments(prefix: str, identifier: str) -> tuple[str, ...]:
    """Return bounded literal assignments for one minified local alias.

    B-ITE tenant assets commonly hoist immutable scalars (for example ``i=0``
    and ``o="tenant"``) and reference those aliases from ``createSearchConfig``.
    We do not execute JavaScript: only literal string/number assignments that
    occur before the config object are eligible.  Conflicting literal values
    fail closed at the caller.
    """

    if _JS_IDENTIFIER_RE.fullmatch(identifier) is None or len(prefix) > 2_000_000:
        return ()
    assignment_re = re.compile(
        rf"(?<![A-Za-z0-9_$.]){re.escape(identifier)}\s*=\s*"
        rf"(?P<value>['\"][^'\"]{{1,128}}['\"]|{_JS_NUMBER})(?=\s*[,;])",
        flags=re.IGNORECASE,
    )
    return tuple(dict.fromkeys(match.group("value") for match in assignment_re.finditer(prefix)))


def _resolve_number_token(token: str, *, prefix: str) -> int | None:
    direct = _integer_js_number(token)
    if direct is not None:
        return direct
    assignments = _scalar_assignments(prefix, token.strip())
    if len(assignments) != 1:
        return None
    return _integer_js_number(assignments[0])


def _resolve_string_token(token: str, *, prefix: str) -> str | None:
    token = token.strip()
    direct = _JS_STRING_RE.fullmatch(token)
    if direct is not None:
        return direct.group(2).strip() or None
    if _JS_IDENTIFIER_RE.fullmatch(token) is None:
        return None
    assignments = _scalar_assignments(prefix, token)
    if len(assignments) != 1:
        return None
    match = _JS_STRING_RE.fullmatch(assignments[0])
    if match is None:
        return None
    return match.group(2).strip() or None


def _resolve_filter_values(raw_values: str, *, prefix: str) -> tuple[str, ...] | None:
    parts = tuple(part.strip() for part in raw_values.split(","))
    if not parts or any(not part for part in parts) or len(parts) > 64:
        return None
    resolved: list[str] = []
    for part in parts:
        value = _resolve_string_token(part, prefix=prefix)
        if value is None or len(value) > 128:
            return None
        resolved.append(value)
    values = tuple(dict.fromkeys(resolved))
    return values or None


def discover_bite_binding(*, page_url: str, html: str) -> BiteBinding | None:
    """Return one exact employer-declared B-ITE tenant binding, otherwise fail closed."""

    if _https_url(page_url) is None or BITE_LOADER_URL.casefold() not in html.casefold():
        return None
    values = {
        (match.group("customer"), match.group("asset"))
        for match in _BINDING_RE.finditer(html)
    }
    if len(values) != 1:
        return None
    customer, asset_name = next(iter(values))
    asset_url = f"https://{BITE_ASSET_HOST}/{customer}/jobs-api/{asset_name}.min.js"
    return BiteBinding(
        employer_page_url=page_url,
        customer=customer,
        asset_name=asset_name,
        asset_url=asset_url,
    )


def parse_bite_runtime(*, binding: BiteBinding, asset_url: str, javascript: str) -> BiteRuntimeConfig | None:
    """Extract only the bounded public JobsApi-v5 runtime fields needed for inventory."""

    if canonical_url(asset_url) != canonical_url(binding.asset_url):
        return None
    if _https_url(asset_url, host=BITE_ASSET_HOST) is None:
        return None

    key_match = _KEY_RE.search(javascript)
    channel_match = _CHANNEL_RE.search(javascript)
    locale_match = _LOCALE_RE.search(javascript)
    page_match = _PAGE_RE.search(javascript)
    sort_match = _SORT_RE.search(javascript)
    filter_match = _FILTER_RE.search(javascript)
    if not all((key_match, channel_match, locale_match, page_match, sort_match, filter_match)):
        return None

    assert key_match and channel_match and locale_match and page_match and sort_match and filter_match
    # Minified provider assets may hoist channel/filter values into local scalar
    # aliases.  Only literal assignments preceding the proven config are resolved.
    prefix = javascript[: key_match.start()]
    page_offset = _integer_js_number(page_match.group("offset"))
    page_num = _integer_js_number(page_match.group("num"))
    channel = _resolve_number_token(channel_match.group("value"), prefix=prefix)
    filter_values = _resolve_filter_values(filter_match.group(2), prefix=prefix)
    if page_offset is None or page_num is None or channel is None or filter_values is None:
        return None
    if page_offset < 0 or not 1 <= page_num <= BITE_MAX_PAGE_SIZE or channel < 0:
        return None

    # Employer ownership of the tenant asset was established by the binding.  The
    # runtime filter must still contain the declared customer somewhere, preventing
    # an unrelated asset body from being accepted under the same URL shape.
    normalized_customer = binding.customer.casefold()
    if not any(normalized_customer in value.casefold() for value in filter_values):
        return None

    return BiteRuntimeConfig(
        customer=binding.customer,
        public_key=key_match.group(1),
        channel=channel,
        locale=locale_match.group(1),
        page_offset=page_offset,
        page_num=page_num,
        sort_by=sort_match.group(1),
        sort_order=sort_match.group(2).casefold(),
        filter_key=filter_match.group(1),
        filter_values=filter_values,
    )


def bite_inventory_payload(*, runtime: BiteRuntimeConfig, origin_url: str) -> dict[str, object]:
    if _https_url(origin_url) is None:
        raise ValueError("B-ITE origin must be absolute HTTPS")
    return {
        "key": runtime.public_key,
        "channel": runtime.channel,
        "locale": runtime.locale,
        "sort": {"by": runtime.sort_by, "order": runtime.sort_order},
        "origin": origin_url,
        "page": {"offset": runtime.page_offset, "num": runtime.page_num},
        "filter": {runtime.filter_key: {"in": list(runtime.filter_values)}},
    }


def parse_bite_postings(body: str, *, page_num: int) -> tuple[BitePosting, ...] | None:
    """Parse one complete bounded provider inventory page.

    ``None`` means the response is not a safely complete B-ITE inventory.  An empty
    tuple is a valid complete inventory containing zero current postings.
    """

    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    raw_postings = payload.get("jobPostings")
    if not isinstance(raw_postings, list) or len(raw_postings) > min(page_num, BITE_MAX_POSTINGS):
        return None
    # A page filled exactly to the requested cap may have an unseen next page.  We
    # refuse to call that a finite authoritative inventory without pagination.
    if len(raw_postings) == page_num:
        return None

    postings: list[BitePosting] = []
    for raw in raw_postings:
        if not isinstance(raw, dict):
            return None
        posting_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        public_url = _https_url(raw.get("url"))
        if not posting_id or len(posting_id) > 160 or len(title) < 3 or len(title) > 500 or public_url is None:
            continue
        apply_url = _https_url(raw.get("applyUrl")) or ""
        employer = raw.get("employer")
        employer_name = str(employer.get("name") or "").strip() if isinstance(employer, dict) else ""
        postings.append(
            BitePosting(
                posting_id=posting_id,
                title=title,
                url=public_url,
                apply_url=apply_url,
                employer_name=employer_name,
                raw=dict(raw),
            )
        )
    return tuple(postings)


def _search_text(posting: BitePosting) -> str:
    values: list[str] = [posting.title]
    keywords = posting.raw.get("keywords")
    if isinstance(keywords, list):
        values.extend(str(value) for value in keywords if value is not None)
    elif isinstance(keywords, str):
        values.append(keywords)
    return " ".join(values).casefold()


def filter_bite_postings(postings: tuple[BitePosting, ...], query: str) -> tuple[BitePosting, ...]:
    """Deterministically query a complete finite inventory by title/keyword evidence."""

    tokens = tuple(token.casefold() for token in _TOKEN_RE.findall(query))
    if not tokens:
        return ()
    result = [posting for posting in postings if all(token in _search_text(posting) for token in tokens)]
    return tuple(result)


def bite_raw_detail_url(public_url: str) -> str | None:
    clean = canonical_url(public_url)
    if _https_url(clean) is None:
        return None
    return f"{clean}/raw"


def prove_bite_raw_detail(
    *,
    posting: BitePosting,
    raw_url: str,
    raw_body: str,
    response_url: str,
    status_code: int,
) -> AcquiredJobPage | None:
    """Project provider raw-detail evidence into the unchanged strict proof gate."""

    expected_raw = bite_raw_detail_url(posting.url)
    if expected_raw is None or canonical_url(raw_url) != canonical_url(expected_raw):
        return None
    if not 200 <= int(status_code) < 400:
        return None
    response_host = (urlparse(response_url).hostname or "").casefold()
    job_host = (urlparse(posting.url).hostname or "").casefold()
    if not response_host or response_host != job_host:
        return None
    if len(raw_body.encode("utf-8", errors="replace")) > BITE_MAX_RAW_BYTES:
        return None

    page = PageSnapshot(
        requested_url=posting.url,
        final_url=posting.url,
        status_code=int(status_code),
        title=posting.title,
        text=raw_body,
        html=raw_body,
        links=(),
    )
    proof = genuine_job_detail_proof(
        page,
        allowed_hosts={job_host},
        known_detail=True,
    )
    if proof is None:
        return None
    return AcquiredJobPage(
        requested_url=posting.url,
        final_url=posting.url,
        status_code=int(status_code),
        title=posting.title,
        html_bytes=len(raw_body.encode("utf-8", errors="replace")),
        proof_kind=proof,
        discovery_source="bite_finite_inventory_raw_detail",
        anchor_text=posting.title,
    )


__all__ = [
    "BITE_API_ENDPOINT",
    "BITE_ASSET_HOST",
    "BITE_JOBS_API_CLIENT",
    "BiteBinding",
    "BitePosting",
    "BiteRuntimeConfig",
    "bite_inventory_payload",
    "bite_raw_detail_url",
    "discover_bite_binding",
    "filter_bite_postings",
    "parse_bite_postings",
    "parse_bite_runtime",
    "prove_bite_raw_detail",
]
