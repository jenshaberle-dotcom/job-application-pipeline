from __future__ import annotations

import re
from collections.abc import Iterable


def normalize_relevance_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = re.sub(r"\s+", " ", value).strip().casefold()
    return (
        normalized.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _short_term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![0-9a-z]){re.escape(term)}(?![0-9a-z])")


def find_relevance_terms(
    value: str,
    terms: Iterable[str],
) -> tuple[str, ...]:
    """Return deterministic case-insensitive relevance matches.

    Short acronym-like terms (for example AI/BI/KI/UI) require lexical
    boundaries so they cannot match arbitrary substrings such as ``bi`` in
    ``mikrobiologisch``. Longer terms preserve the established substring
    behavior, including useful compounds such as ``datenanalyse``.
    """

    normalized_value = normalize_relevance_text(value)
    matches: list[str] = []

    for term in terms:
        normalized_term = normalize_relevance_text(term)
        if not normalized_term:
            continue

        compact = re.sub(r"[^0-9a-z]", "", normalized_term)
        if len(compact) <= 2 and " " not in normalized_term:
            matched = bool(_short_term_pattern(normalized_term).search(normalized_value))
        else:
            matched = normalized_term in normalized_value

        if matched and term not in matches:
            matches.append(term)

    return tuple(matches)
