"""Strict same-host parent recovery for stale employer listing roots.

This module performs no network I/O. It derives at most one direct path parent
from a stale HTTPS listing URL. The caller still has to fetch that parent and may
only proceed through ordinary explicit navigation evidence from the recovered
page. No company mapping, locale guess, or provider endpoint is introduced.
"""

from __future__ import annotations

from urllib.parse import urlparse


RECOVERABLE_ROOT_HTTP_STATUSES = frozenset({404, 410})


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


__all__ = [
    "RECOVERABLE_ROOT_HTTP_STATUSES",
    "direct_same_host_parent_url",
    "recoverable_root_http_status",
]
