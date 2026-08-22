"""Strict same-host parent recovery for stale employer listing roots.

This module performs no network I/O. It derives at most one direct path parent
from a stale HTTPS listing URL and can recognize one explicit high-confidence
job-board link on an already-fetched recovered parent. No company mapping,
locale guess, provider endpoint, or broad navigation authority is introduced.
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


RECOVERABLE_ROOT_HTTP_STATUSES = frozenset({404, 410})
PRIMARY_LISTING_LABELS = frozenset(
    {
        "job board",
        "job search",
        "jobsuche",
        "stellensuche",
        "stellenangebote",
        "offene stellen",
        "current vacancies",
        "aktuelle stellenangebote",
    }
)


def direct_same_host_parent_url(
    url: str,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Return exactly one direct path parent for a stale HTTPS root.

    A path needs at least two non-empty segments so that recovery cannot turn an
    arbitrary one-segment source into a generic host-root crawl. Query and fragment
    are removed. The parent remains on the exact already-authorized host.
    """

    parsed = urlparse(str(url or ""))
    hostname = (parsed.hostname or "").casefold().strip(".")
    allowed = {str(item).casefold().strip(".") for item in allowed_hosts if str(item)}
    if parsed.scheme.casefold() != "https" or not hostname or hostname not in allowed:
        return None
    segments = [segment for segment in (parsed.path or "").split("/") if segment]
    if len(segments) < 2:
        return None
    parent_path = "/" + "/".join(segments[:-1])
    return parsed._replace(path=parent_path, params="", query="", fragment="").geturl().rstrip("/")


def recoverable_root_http_status(status_code: int | None) -> bool:
    try:
        return int(status_code or 0) in RECOVERABLE_ROOT_HTTP_STATUSES
    except (TypeError, ValueError):
        return False


def strict_primary_listing_url(
    page: PageSnapshot,
    *,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Return one explicit high-confidence job-board link from a recovered parent.

    Only exact listing labels are accepted. The URL must stay on an already
    authorized host and must not match the normal non-job exclusions. Multiple
    distinct qualifying destinations are ambiguous and fail closed.
    """

    candidates: list[str] = []
    seen: set[str] = set()
    for raw_url, anchor_text in page.links:
        label = normalize_whitespace(anchor_text).casefold().strip(" :")
        if label not in PRIMARY_LISTING_LABELS:
            continue
        clean = canonical_url(raw_url)
        if not clean or clean in seen or not allowed_host(clean, allowed_hosts) or non_job_url(clean):
            continue
        parsed = urlparse(clean)
        if parsed.scheme.casefold() != "https":
            continue
        seen.add(clean)
        candidates.append(clean)
    if len(candidates) != 1:
        return None
    return candidates[0]


__all__ = [
    "PRIMARY_LISTING_LABELS",
    "RECOVERABLE_ROOT_HTTP_STATUSES",
    "direct_same_host_parent_url",
    "recoverable_root_http_status",
    "strict_primary_listing_url",
]
