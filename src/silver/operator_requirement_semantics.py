"""Bounded operator-facing semantics for persisted vacancy evidence.

These helpers create no Candidate Fact, hard-filter, ranking, Top-5 or application
authority. They only preserve distinctions that are already observable in the
employer-origin vacancy, such as structured full/part-time scope and the dominant
language of the bounded vacancy text.
"""
from __future__ import annotations

import re
from typing import Iterable


_FULL_TIME = frozenset({"fulltime", "full_time", "full-time", "full time"})
_PART_TIME = frozenset({"parttime", "part_time", "part-time", "part time"})

_DE_MARKERS = frozenset(
    {
        "und", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
        "mit", "für", "von", "im", "in", "auf", "wir", "sie", "ihre", "deine",
        "du", "uns", "unser", "suchen", "erfahrung", "kenntnisse", "aufgaben",
        "anforderungen", "verantwortung", "bewerbung", "arbeitszeit", "stelle",
    }
)
_EN_MARKERS = frozenset(
    {
        "and", "the", "a", "an", "with", "for", "from", "in", "on", "we", "you",
        "your", "our", "are", "will", "role", "skills", "experience", "requirements",
        "responsibilities", "application", "working", "hours", "position", "team",
    }
)
_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß]+")


def _normalized_employment_token(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().replace("_", " ").replace("-", " ").split())


def normalize_employment_scope(values: Iterable[object]) -> str:
    """Map structured employmentType-like values without inventing contract duration."""

    normalized = {_normalized_employment_token(value) for value in values}
    compact = {value.replace(" ", "") for value in normalized if value}
    full = bool(compact & {"fulltime"}) or bool(normalized & _FULL_TIME)
    part = bool(compact & {"parttime"}) or bool(normalized & _PART_TIME)
    if full and part:
        return "full_or_part_time"
    if full:
        return "full_time"
    if part:
        return "part_time"
    return "unknown"


def infer_posting_language(value: object) -> str:
    """Infer only the dominant DE/EN language of bounded vacancy text.

    This is presentation evidence, never an explicit language requirement. The
    detector is intentionally conservative and returns ``mixed`` or ``unknown``
    instead of forcing a language when the text is short or balanced.
    """

    text = str(value or "").strip()
    tokens = [token.casefold() for token in _TOKEN_RE.findall(text)]
    if len(tokens) < 12:
        return "unknown"

    de = sum(token in _DE_MARKERS for token in tokens)
    en = sum(token in _EN_MARKERS for token in tokens)
    if any(char in text.casefold() for char in ("ä", "ö", "ü", "ß")):
        de += 2

    strongest = max(de, en)
    weakest = min(de, en)
    if strongest < 3:
        return "unknown"
    if weakest >= 3 and weakest / strongest >= 0.55:
        return "mixed"
    if de >= en * 1.5:
        return "de"
    if en >= de * 1.5:
        return "en"
    return "mixed"


__all__ = ["infer_posting_language", "normalize_employment_scope"]
