"""Pure Greenhouse provider-navigation primitives for bounded acquisition proof.

No function in this module performs network I/O. A Greenhouse cascade starts only
when an already-authorized employer page contains one concrete canonical
Greenhouse board URL. Board identity is then checked against the employer host
before jobs or detail candidates are emitted.
"""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlparse


_GREENHOUSE_HOSTS = {
    "boards-api.greenhouse.io",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
}
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{2,128}$")
_URL = re.compile(r"(?:https?:)?//[^\s\"'<>\\]+", flags=re.IGNORECASE)
_COMMON_HOST_LABELS = {
    "www",
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "recruiting",
    "recruitment",
}


def _decoded(value: str) -> str:
    return (
        unescape(value or "")
        .replace(r"\/", "/")
        .replace(r"\u002F", "/")
        .replace(r"\u002f", "/")
    )


def _board_token_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    parts = [part for part in (parsed.path or "").split("/") if part]
    if host == "boards-api.greenhouse.io":
        if len(parts) < 3 or parts[:2] != ["v1", "boards"]:
            return None
        token = parts[2]
    elif host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        if not parts:
            return None
        token = parts[0]
    else:
        return None
    return token if _TOKEN.fullmatch(token) else None


def explicit_greenhouse_board_token(html: str) -> str | None:
    """Return one uniquely observed canonical Greenhouse board token, else fail closed."""

    tokens: set[str] = set()
    for match in _URL.finditer(_decoded(html)):
        raw = match.group(0).rstrip("),;]")
        url = f"https:{raw}" if raw.startswith("//") else raw
        token = _board_token_from_url(url)
        if token:
            tokens.add(token)
    if len(tokens) != 1:
        return None
    return next(iter(tokens))


def greenhouse_metadata_url(board_token: str) -> str | None:
    if not _TOKEN.fullmatch(board_token or ""):
        return None
    return f"https://boards-api.greenhouse.io/v1/boards/{board_token}"


def greenhouse_jobs_url(board_token: str) -> str | None:
    if not _TOKEN.fullmatch(board_token or ""):
        return None
    return f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


def _normalized_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _employer_host_identity_labels(employer_url: str) -> tuple[str, ...]:
    host = (urlparse(employer_url).hostname or "").casefold().strip(".")
    parts = [part for part in host.split(".") if part]
    if len(parts) < 2:
        return ()
    candidates = [
        _normalized_token(part)
        for part in parts[:-1]
        if part not in _COMMON_HOST_LABELS and len(_normalized_token(part)) >= 5
    ]
    return tuple(dict.fromkeys(item for item in candidates if item))


def greenhouse_metadata_matches_employer(*, body: str, employer_url: str) -> bool:
    """Require a single-token board name to exactly match an employer-host identity label."""

    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    board_name = _normalized_token(str(payload.get("name") or ""))
    return bool(board_name and board_name in _employer_host_identity_labels(employer_url))


def greenhouse_detail_urls_from_jobs(
    *,
    body: str,
    board_token: str,
    limit: int = 5,
) -> tuple[str, ...]:
    """Return token-consistent concrete Greenhouse detail URLs from a jobs payload."""

    if limit < 1 or not _TOKEN.fullmatch(board_token or ""):
        return ()
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return ()
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        return ()

    result: list[str] = []
    seen: set[str] = set()
    token = board_token.casefold()
    for item in jobs:
        if not isinstance(item, dict):
            continue
        url = str(item.get("absolute_url") or "").strip()
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold()
        parts = [part.casefold() for part in (parsed.path or "").split("/") if part]
        if parsed.scheme.casefold() != "https" or host not in {
            "boards.greenhouse.io",
            "job-boards.greenhouse.io",
        }:
            continue
        if token not in parts:
            continue
        token_index = parts.index(token)
        try:
            jobs_index = parts.index("jobs", token_index + 1)
        except ValueError:
            continue
        if jobs_index + 1 >= len(parts) or not re.fullmatch(r"[0-9]{4,}", parts[jobs_index + 1]):
            continue
        normalized = url.split("#", 1)[0]
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return tuple(result)


def canonical_greenhouse_host(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold().strip(".")
    if parsed.scheme.casefold() != "https" or host not in _GREENHOUSE_HOSTS:
        return None
    return host


__all__ = [
    "canonical_greenhouse_host",
    "explicit_greenhouse_board_token",
    "greenhouse_detail_urls_from_jobs",
    "greenhouse_jobs_url",
    "greenhouse_metadata_matches_employer",
    "greenhouse_metadata_url",
]
