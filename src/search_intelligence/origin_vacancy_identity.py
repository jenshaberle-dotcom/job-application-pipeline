"""Provider-neutral exact vacancy identity evidence.

This module intentionally extracts identifiers only when the origin text labels them
explicitly (for example ``Kennziffer`` or ``Requisition ID``). It never mines free
numbers and never falls back to title/company similarity. The identity namespace is
the normalized Origin host, which allows locale/path aliases on the same employer
origin to resolve to one vacancy without inventing global URL rewrite rules.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit


MAX_ID_SCAN_CHARS = 20_000
MAX_IDENTIFIER_CHARS = 96


@dataclass(frozen=True)
class VacancyIdentifierEvidence:
    value: str
    normalized_value: str
    label: str
    evidence_kind: str = "explicit_label"


# Strong labels only. Generic words such as "reference" or "id" alone are omitted
# because they create false identities in ordinary page copy.
_LABEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "kennziffer",
        re.compile(
            r"\bkennziffer\s*(?::|#|-)?\s*([A-Z0-9][A-Z0-9._/-]{1,95})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "stellen-id",
        re.compile(
            r"\bstellen[\s_-]*id\s*(?::|#|-)?\s*([A-Z0-9][A-Z0-9._/-]{1,95})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "job-id",
        re.compile(
            r"\bjob[\s_-]*id\s*(?::|#|-)?\s*([A-Z0-9][A-Z0-9._/-]{1,95})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "requisition-id",
        re.compile(
            r"\b(?:requisition|req)[\s_-]*id\s*(?::|#|-)?\s*([A-Z0-9][A-Z0-9._/-]{1,95})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reference-number",
        re.compile(
            r"\b(?:reference|reference\s+number|reference\s+no\.?|job\s+reference)\s*(?::|#|-)?\s*([A-Z0-9][A-Z0-9._/-]{2,95})\b",
            re.IGNORECASE,
        ),
    ),
)


def normalize_vacancy_identifier(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw or len(raw) > MAX_IDENTIFIER_CHARS:
        return None
    normalized = re.sub(r"\s+", "", raw).strip(".:,;()[]{}")
    if len(normalized) < 2 or not re.search(r"[0-9]", normalized):
        return None
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", normalized):
        return None
    return normalized.casefold()


def extract_explicit_vacancy_identifier(text: str | None) -> VacancyIdentifierEvidence | None:
    """Return the first strongly-labelled vacancy identifier from bounded text."""

    haystack = str(text or "")[:MAX_ID_SCAN_CHARS]
    if not haystack.strip():
        return None
    for label, pattern in _LABEL_PATTERNS:
        match = pattern.search(haystack)
        if not match:
            continue
        value = match.group(1).strip()
        normalized = normalize_vacancy_identifier(value)
        if normalized is None:
            continue
        return VacancyIdentifierEvidence(
            value=value,
            normalized_value=normalized,
            label=label,
        )
    return None


def origin_host_namespace(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.casefold().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def exact_origin_vacancy_identity(
    *,
    origin_url: str | None,
    identifier: str | None,
) -> tuple[str, str, str] | None:
    """Build a cross-projection identity only from host + explicit identifier."""

    namespace = origin_host_namespace(origin_url)
    normalized_identifier = normalize_vacancy_identifier(identifier)
    if not namespace or not normalized_identifier:
        return None
    return (namespace, "origin_vacancy_identifier", normalized_identifier)


__all__ = [
    "VacancyIdentifierEvidence",
    "exact_origin_vacancy_identity",
    "extract_explicit_vacancy_identifier",
    "normalize_vacancy_identifier",
    "origin_host_namespace",
]
