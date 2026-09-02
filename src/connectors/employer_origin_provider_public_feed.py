"""Evidence-bounded public ATS feed acquisition for employer-origin proof.

External and historical project knowledge may define provider-wide capability shapes,
but never establishes an employer, tenant, host, opaque value, or product authority.
Callers must already possess repository-native provider/host authority.

Only fixed same-host provider routes are supported. Structured feed rows merely create
concrete detail candidates; final truth still requires the unchanged
``genuine_job_detail_proof``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib.parse import urlencode, urlparse, urlunparse
from xml.etree import ElementTree as ET

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    allowed_host,
    canonical_url,
    explicit_root_delegated_listing_hosts,
    genuine_job_detail_proof,
    parse_page,
)
from src.connectors.employer_origin_ats_navigation import authorized_ats_provider
from src.search_intelligence.ats_provider_registry import recognize_ats_provider
from src.search_intelligence.multi_origin_evidence import job_detail_url_shape


SUPPORTED_PUBLIC_FEED_PROVIDERS = frozenset(
    {"successfactors", "softgarden", "recruitee", "dvinci"}
)
_MAX_FEED_BODY_BYTES = 5_000_000
_MAX_SITEMAP_URLS = 10_000
_DVINCI_PORTAL_PREFIX = re.compile(r"^/portal/[^/?#]+", flags=re.IGNORECASE)


@dataclass(frozen=True)
class ProviderPublicFeedResult:
    provider: str
    feed_url: str
    detail_candidates: tuple[str, ...]
    acquired_job: AcquiredJobPage | None


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _valid_https(value: str) -> bool:
    parsed = urlparse(value)
    return bool(
        parsed.scheme.casefold() == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
    )


def _same_authorized_host(
    candidate: str,
    feed_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> bool:
    return bool(
        _valid_https(candidate)
        and _host(candidate) == _host(feed_url)
        and allowed_host(candidate, allowed_hosts)
    )


def provider_public_feed_urls(
    *,
    provider: str,
    page_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> tuple[str, ...]:
    """Return fixed provider inventory routes on an already-authorized exact host.

    SuccessFactors intentionally has two independently evidenced fixed routes:
    the project's previously proven same-host ``/sitemap.xml`` URLSet first, then
    the externally salvaged Recruiting Marketing ``/sitemal.xml`` RSS feed.
    Neither contains tenant-derived values.
    """

    if provider not in SUPPORTED_PUBLIC_FEED_PROVIDERS:
        return ()
    if not _valid_https(page_url) or not allowed_host(page_url, allowed_hosts):
        return ()

    parsed = urlparse(page_url)
    host = (parsed.hostname or "").casefold()
    if not host:
        return ()

    if provider == "successfactors":
        return (
            urlunparse(("https", host, "/sitemap.xml", "", "", "")),
            urlunparse(("https", host, "/sitemal.xml", "", "", "")),
        )

    recognition = recognize_ats_provider(page_url)
    if recognition is None or recognition.provider != provider:
        return ()

    if provider == "softgarden":
        if not host.endswith(".career.softgarden.de"):
            return ()
        return (urlunparse(("https", host, "/jobs.feed.json", "", "", "")),)

    if provider == "recruitee":
        if not (host.endswith(".recruitee.com") or host.endswith(".recruitee.io")):
            return ()
        return (urlunparse(("https", host, "/api/offers", "", "", "")),)

    if provider == "dvinci":
        if not host.endswith(".dvinci.de"):
            return ()
        match = _DVINCI_PORTAL_PREFIX.match(parsed.path or "")
        portal_prefix = match.group(0).rstrip("/") if match else ""
        path = f"{portal_prefix}/jobPublication/list.json"
        return (
            urlunparse(
                ("https", host, path, "", urlencode({"fields": "small"}), "")
            ),
        )

    return ()


def provider_public_feed_url(
    *,
    provider: str,
    page_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Compatibility helper returning the first fixed provider feed candidate."""

    urls = provider_public_feed_urls(
        provider=provider,
        page_url=page_url,
        allowed_hosts=allowed_hosts,
    )
    return urls[0] if urls else None


def _local_name(tag: str) -> str:
    return str(tag or "").rsplit("}", 1)[-1].casefold()


def _dedupe_same_host_urls(
    values: list[str],
    *,
    feed_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int,
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        candidate = canonical_url(str(raw or "").strip())
        if not candidate or candidate in seen:
            continue
        if not _same_authorized_host(candidate, feed_url, allowed_hosts):
            continue
        if candidate == canonical_url(feed_url):
            continue
        seen.add(candidate)
        result.append(candidate)
        if len(result) >= limit:
            break
    return tuple(result)


def _successfactors_links(body: str) -> list[str]:
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, ValueError):
        return []

    root_name = _local_name(root.tag)
    if root_name == "rss":
        if not any(_local_name(node.tag) == "channel" for node in root.iter()):
            return []
        links: list[str] = []
        for item in root.iter():
            if _local_name(item.tag) != "item":
                continue
            for child in item:
                if _local_name(child.tag) == "link" and child.text and child.text.strip():
                    links.append(child.text.strip())
                    break
        return links

    if root_name == "urlset":
        links = []
        visited = 0
        for item in root.iter():
            if _local_name(item.tag) != "url":
                continue
            visited += 1
            if visited > _MAX_SITEMAP_URLS:
                break
            for child in item:
                if _local_name(child.tag) != "loc" or not child.text:
                    continue
                candidate = canonical_url(child.text.strip())
                if candidate and job_detail_url_shape(candidate):
                    links.append(candidate)
                break
        return links

    return []


def _softgarden_links(body: str) -> list[str]:
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    elements = payload.get("dataFeedElement")
    count = payload.get("numberOfItems")
    if not isinstance(elements, list) or not isinstance(count, int) or count != len(elements):
        return []
    result: list[str] = []
    for element in elements:
        if not isinstance(element, dict) or not isinstance(element.get("item"), dict):
            return []
        item = element["item"]
        if str(item.get("@type") or "").casefold() not in {"jobposting", ""}:
            continue
        value = item.get("url")
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
    return result


def _recruitee_links(body: str) -> list[str]:
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
        return []
    result: list[str] = []
    for offer in payload["offers"]:
        if not isinstance(offer, dict):
            continue
        value = offer.get("careers_url") or offer.get("careers_apply_url")
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
    return result


def _dvinci_links(body: str) -> list[str]:
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    result: list[str] = []
    for publication in payload:
        if not isinstance(publication, dict):
            continue
        publication_id = publication.get("id")
        value = publication.get("jobPublicationURL")
        if publication_id is None or not isinstance(value, str) or not value.strip():
            continue
        result.append(value.strip())
    return result


def parse_provider_public_feed(
    *,
    provider: str,
    feed_url: str,
    body: str,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 20,
) -> tuple[str, ...]:
    """Validate one provider schema and return concrete same-authority detail URLs."""

    if limit < 1 or provider not in SUPPORTED_PUBLIC_FEED_PROVIDERS:
        return ()
    if len(body.encode("utf-8")) > _MAX_FEED_BODY_BYTES:
        return ()
    if not _same_authorized_host(feed_url, feed_url, allowed_hosts):
        return ()

    if provider == "successfactors":
        raw = _successfactors_links(body)
    elif provider == "softgarden":
        raw = _softgarden_links(body)
    elif provider == "recruitee":
        raw = _recruitee_links(body)
    elif provider == "dvinci":
        raw = _dvinci_links(body)
    else:
        return ()

    return _dedupe_same_host_urls(
        raw,
        feed_url=feed_url,
        allowed_hosts=allowed_hosts,
        limit=limit,
    )


def acquire_from_authorized_provider_host(
    *,
    provider: str,
    provider_page_url: str,
    allowed_hosts: tuple[str, ...],
    fetcher,
    max_detail_attempts: int = 1,
) -> ProviderPublicFeedResult | None:
    """Acquire from fixed feeds on a provider host already authorized by the caller."""

    if max_detail_attempts < 1:
        raise ValueError("max_detail_attempts must be >= 1")
    if provider not in SUPPORTED_PUBLIC_FEED_PROVIDERS:
        return None

    feed_urls = provider_public_feed_urls(
        provider=provider,
        page_url=provider_page_url,
        allowed_hosts=allowed_hosts,
    )
    if not feed_urls:
        return None

    last_result: ProviderPublicFeedResult | None = None
    best_result: ProviderPublicFeedResult | None = None

    for feed_url in feed_urls:
        feed_body, feed_final_url, feed_status = fetcher(feed_url)
        if int(feed_status) >= 400 or canonical_url(feed_final_url) != canonical_url(feed_url):
            last_result = ProviderPublicFeedResult(provider, feed_url, (), None)
            continue

        detail_candidates = parse_provider_public_feed(
            provider=provider,
            feed_url=feed_url,
            body=str(feed_body),
            allowed_hosts=allowed_hosts,
        )
        current = ProviderPublicFeedResult(provider, feed_url, detail_candidates, None)
        last_result = current
        if detail_candidates:
            best_result = current

        for detail_url in detail_candidates[:max_detail_attempts]:
            detail_html, detail_final_url, detail_status = fetcher(detail_url)
            page = parse_page(
                requested_url=detail_url,
                html=str(detail_html),
                final_url=str(detail_final_url),
                status_code=int(detail_status),
            )
            proof = genuine_job_detail_proof(
                page,
                allowed_hosts=allowed_hosts,
                known_detail=True,
            )
            if not proof:
                continue
            job = AcquiredJobPage(
                requested_url=page.requested_url,
                final_url=page.final_url,
                status_code=page.status_code,
                title=page.title,
                html_bytes=len(page.html.encode("utf-8")),
                proof_kind=proof,
                discovery_source=f"{provider}_provider_public_feed",
                anchor_text="",
            )
            return ProviderPublicFeedResult(provider, feed_url, detail_candidates, job)

    return best_result or last_result


def acquire_via_provider_public_feed(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    fetcher,
    max_detail_attempts: int = 1,
) -> ProviderPublicFeedResult | None:
    """Recognize an authorized root, then use only its fixed same-host provider feeds."""

    if max_detail_attempts < 1:
        raise ValueError("max_detail_attempts must be >= 1")

    root_html, root_final_url, root_status = fetcher(listing_url)
    root = parse_page(
        requested_url=listing_url,
        html=str(root_html),
        final_url=str(root_final_url),
        status_code=int(root_status),
    )
    if root.status_code >= 400 or not allowed_host(root.final_url, allowed_hosts):
        return None

    delegated_hosts = set(
        explicit_root_delegated_listing_hosts(root, allowed_hosts=allowed_hosts)
    )
    provider = authorized_ats_provider(
        page_url=root.final_url,
        html=root.html,
        allowed_hosts=allowed_hosts,
        delegated_hosts=delegated_hosts,
    )
    if provider not in SUPPORTED_PUBLIC_FEED_PROVIDERS:
        return None

    return acquire_from_authorized_provider_host(
        provider=provider,
        provider_page_url=root.final_url,
        allowed_hosts=allowed_hosts,
        fetcher=fetcher,
        max_detail_attempts=max_detail_attempts,
    )


__all__ = [
    "ProviderPublicFeedResult",
    "SUPPORTED_PUBLIC_FEED_PROVIDERS",
    "acquire_from_authorized_provider_host",
    "acquire_via_provider_public_feed",
    "parse_provider_public_feed",
    "provider_public_feed_url",
    "provider_public_feed_urls",
]
