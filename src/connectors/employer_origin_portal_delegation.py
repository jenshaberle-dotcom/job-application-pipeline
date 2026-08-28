"""Evidence-bounded first-party -> career-portal delegation.

This module handles a narrow residual class where an employer career page exposes
an explicit external/subdomain portal CTA whose wording is stronger than the
legacy generic listing vocabulary.  It intentionally does *not* widen
``LISTING_TEXT_MARKERS`` globally.

A new-label delegation requires both:

1. an explicit strong portal CTA such as ``Job finden`` / ``Zum Jobportal``; and
2. a destination that is structurally bound to the employer/career context by
   either the same registered domain or an explicit career/jobs host label.

The result is a concrete portal URL, not generic host authority.  Ambiguous
multi-portal evidence is left for the caller to reject fail-closed.
"""

from __future__ import annotations

from urllib.parse import urlparse

from src.connectors.employer_origin_acquisition import (
    PageSnapshot,
    allowed_host,
    canonical_url,
    non_job_url,
    normalize_whitespace,
)


STRONG_PORTAL_CTA_MARKERS = (
    "job finden",
    "zum jobportal",
    "zum job portal",
    "jetzt einen job finden",
)

CAREER_HOST_LABELS = {
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "recruiting",
    "recruitment",
}

NON_DELEGATED_HOST_SUFFIXES = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
)


def _registered_domain(url_or_host: str) -> str:
    host = (urlparse(url_or_host).hostname or url_or_host).casefold().strip(".")
    host = host.removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _same_registered_domain(left: str, right: str) -> bool:
    domain = _registered_domain(left)
    return bool(domain and domain == _registered_domain(right))


def _career_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    labels = {part for part in host.split(".") if part}
    return bool(labels.intersection(CAREER_HOST_LABELS))


def _non_delegated_host(hostname: str) -> bool:
    lowered = hostname.casefold().strip(".")
    return any(
        lowered == suffix or lowered.endswith(f".{suffix}")
        for suffix in NON_DELEGATED_HOST_SUFFIXES
    )


def _strong_portal_cta(anchor_text: str) -> bool:
    text = normalize_whitespace(anchor_text).casefold()
    return bool(text and any(marker in text for marker in STRONG_PORTAL_CTA_MARKERS))


def explicit_bounded_portal_urls(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
    limit: int = 3,
) -> tuple[str, ...]:
    """Return explicit portal URLs that satisfy the narrow extra-label contract."""

    if limit < 1:
        return ()

    result: list[str] = []
    seen: set[str] = set()
    for raw_url, anchor_text in page.links:
        clean = canonical_url(raw_url)
        parsed = urlparse(clean)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme.casefold() != "https" or not host:
            continue
        if allowed_host(clean, allowed_hosts) or non_job_url(clean) or _non_delegated_host(host):
            continue
        if not _strong_portal_cta(anchor_text):
            continue
        if not (_same_registered_domain(page.final_url, clean) or _career_host(clean)):
            continue
        if clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if len(result) >= limit:
            break
    return tuple(result)


__all__ = [
    "STRONG_PORTAL_CTA_MARKERS",
    "explicit_bounded_portal_urls",
]
