"""Shared employer-origin URL shape policy.

The policy is intentionally conservative about explicit authentication URLs while
avoiding substring false positives in company or host names. For example,
``adesso`` contains ``sso`` as text but is not an SSO/authentication URL.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

_ALLOWED_SCHEMES = {"http", "https"}
_AUTH_HOST_SEGMENTS = {"login", "signin", "sign-in", "auth", "sso", "oauth"}
_AUTH_PATH_SEGMENTS = {"login", "signin", "sign-in", "auth", "sso", "oauth", "saml"}
_AUTH_QUERY_KEYS = {"login", "signin", "auth", "sso", "oauth", "saml", "redirect_uri"}
_AUTH_QUERY_VALUES = {"login", "signin", "sign-in", "sso", "oauth", "saml"}


def _split_path_segments(path: str) -> tuple[str, ...]:
    return tuple(segment.strip().lower() for segment in path.split("/") if segment.strip())


def _split_host_segments(hostname: str | None) -> tuple[str, ...]:
    if not hostname:
        return ()
    return tuple(segment.strip().lower() for segment in hostname.split(".") if segment.strip())


def has_disallowed_source_url_shape(url: str) -> str | None:
    """Return a human reason when a URL shape is unsafe for bounded probing.

    Authentication markers are matched as host/path/query tokens, never as raw
    substrings across the whole URL. This prevents false positives such as
    ``https://www.adesso.de/...`` where the company name happens to contain
    ``sso``.
    """

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return "candidate URL must use http or https"

    host_segments = _split_host_segments(parsed.hostname)
    if any(segment in _AUTH_HOST_SEGMENTS for segment in host_segments):
        return "candidate URL appears to require authentication"

    path_segments = _split_path_segments(parsed.path or "")
    if any(segment in _AUTH_PATH_SEGMENTS for segment in path_segments):
        return "candidate URL appears to require authentication"

    query_pairs = parse_qsl(parsed.query or "", keep_blank_values=True)
    for key, value in query_pairs:
        normalized_key = key.strip().lower().replace("-", "_")
        normalized_value = value.strip().lower().replace("-", "_")
        if normalized_key in _AUTH_QUERY_KEYS or normalized_value in _AUTH_QUERY_VALUES:
            return "candidate URL appears to require authentication"

    return None
