"""Provider-aware deterministic navigation for employer-origin acquisition proof.

This module performs no network I/O and grants no employer, tenant, product, or
qualification authority. Callers may use it only after source-host binding has
already been established. It recognizes a bounded ATS family from the already
fetched page and exposes provider-specific listing/detail routes that are visible
or deterministically derivable from that already-authorized provider surface.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse

from src.connectors.employer_origin_provider_delegation import (
    explicit_canonical_provider_detail_urls,
)
from src.connectors.personio import (
    build_personio_xml_url,
    extract_positions,
    first_text,
)
from src.search_intelligence.ats_provider_registry import (
    classify_provider_names,
    recognize_ats_provider,
)


RECRUITING_HOST_LABELS = {
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "recruiting",
    "recruitment",
}

_SUCCESSFACTORS_GO_ROUTE = re.compile(
    r"^/go/[^/?#]+/[0-9]+/?$",
    flags=re.IGNORECASE,
)
_ANCHOR = re.compile(
    r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_PERSONIO_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{2,128}$")


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _host_is_authorized(
    value: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> bool:
    normalized = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    return bool(_host(value) and _host(value) in normalized)


def _recruiting_host(value: str) -> bool:
    labels = {part for part in _host(value).split(".") if part}
    return bool(labels.intersection(RECRUITING_HOST_LABELS))


def authorized_ats_provider(
    *,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    delegated_hosts: tuple[str, ...] | set[str] = (),
) -> str | None:
    """Recognize one ATS family without widening already-established host authority.

    Canonical ATS host suffixes are accepted directly. A concrete canonical ATS
    detail URL explicitly embedded by an already-authorized employer page is also
    strong provider evidence when all such strict surfaces agree on one provider;
    it still grants no target-host authority by itself. Branded/CNAME recruiting
    hosts otherwise require existing source authority plus an explicit root
    delegation or recruiting hostname label. Ambiguous multi-provider evidence
    fails closed.
    """

    if not _host_is_authorized(page_url, allowed_hosts):
        return None

    direct = recognize_ats_provider(page_url)
    if direct is not None:
        return direct.provider

    explicit_details = explicit_canonical_provider_detail_urls(
        page_url=page_url,
        html=html,
        allowed_hosts=allowed_hosts,
    )
    explicit_providers = {provider for provider, _url in explicit_details}
    if len(explicit_providers) == 1:
        return next(iter(explicit_providers))
    if len(explicit_providers) > 1:
        return None

    page_host = _host(page_url)
    delegated = {
        str(item).casefold().strip(".") for item in delegated_hosts if str(item)
    }
    if page_host not in delegated and not _recruiting_host(page_url):
        return None

    providers = classify_provider_names(html[:500_000])
    if len(providers) != 1:
        return None
    return providers[0]


def _canonical_personio_host(page_url: str) -> str | None:
    recognition = recognize_ats_provider(page_url)
    if recognition is None or recognition.provider != "personio":
        return None
    page_host = _host(page_url)
    if not page_host.endswith(".jobs.personio.de"):
        return None
    return page_host


def provider_listing_urls(
    *,
    provider: str,
    page_url: str,
    html: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 5,
) -> tuple[str, ...]:
    """Return bounded provider-specific listing routes from one authorized page.

    SuccessFactors exposes static same-host ``/go/<slug>/<numeric-id>/`` routes.
    Canonical Personio tenant hosts have an existing repository-backed public XML
    inventory contract. The XML route is derived only from a canonical Personio
    host that is already source-authorized; branded/CNAME hints are insufficient.
    """

    if limit < 1 or not _host_is_authorized(page_url, allowed_hosts):
        return ()

    if provider == "personio":
        personio_host = _canonical_personio_host(page_url)
        if personio_host is None:
            return ()
        return (build_personio_xml_url(host=personio_host, language="de"),)

    if provider != "successfactors":
        return ()

    current = page_url.split("#", 1)[0].rstrip("/")
    result: list[str] = []
    seen: set[str] = set()
    for raw_href, _raw_label in _ANCHOR.findall(html):
        candidate = urljoin(page_url, unescape(raw_href).strip())
        parsed = urlparse(candidate)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        if not _host_is_authorized(candidate, allowed_hosts):
            continue
        normalized = candidate.split("#", 1)[0].rstrip("/")
        if normalized == current or normalized in seen:
            continue
        if not _SUCCESSFACTORS_GO_ROUTE.fullmatch(parsed.path or ""):
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return tuple(result)


def provider_detail_urls(
    *,
    provider: str,
    page_url: str,
    body: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 5,
) -> tuple[str, ...]:
    """Derive strict provider detail URLs from an already-fetched provider listing.

    The first supported detail inventory is Personio XML. A detail URL is emitted
    only when the fetched page is the canonical tenant's ``/xml`` resource and a
    bounded, syntactically valid position ID is present. The resulting URL stays
    on that exact already-authorized Personio host. The caller must still fetch it
    and pass the canonical genuine-job content proof.
    """

    if limit < 1 or provider != "personio":
        return ()
    if not _host_is_authorized(page_url, allowed_hosts):
        return ()
    personio_host = _canonical_personio_host(page_url)
    parsed = urlparse(page_url)
    if personio_host is None or parsed.path.rstrip("/").casefold() != "/xml":
        return ()

    try:
        positions = extract_positions(body.encode("utf-8"))
    except Exception:
        return ()

    result: list[str] = []
    seen: set[str] = set()
    for position in positions:
        job_id = first_text(position, {"id"}).strip()
        if not job_id or not _PERSONIO_JOB_ID.fullmatch(job_id):
            continue
        candidate = f"https://{personio_host}/job/{job_id}?language=de"
        if candidate in seen or not _host_is_authorized(candidate, allowed_hosts):
            continue
        seen.add(candidate)
        result.append(candidate)
        if len(result) >= limit:
            break
    return tuple(result)


__all__ = [
    "authorized_ats_provider",
    "provider_detail_urls",
    "provider_listing_urls",
]
