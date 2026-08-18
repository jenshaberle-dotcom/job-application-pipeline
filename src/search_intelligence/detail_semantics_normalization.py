"""Deterministic canonicalization for grounded Detail Semantics source values.

The model may identify a field and quote an observed value, but it never owns the
canonical representation. This module normalizes only the already-grounded source
value. It deliberately does not infer seniority from years of experience or add
semantic meaning that is absent from the observed phrase.
"""

from __future__ import annotations

import re

from src.search_intelligence.detail_semantics_gap import SEMANTIC_FIELD_NAMES

_YEARS_OF_EXPERIENCE = re.compile(
    r"^\s*\d+(?:[.,]\d+)?\+?\s*(?:years?|yrs?|jahre?n?)\b.*(?:experience|erfahrung).*$",
    re.IGNORECASE,
)


def normalize_detail_semantic_value(*, field: str, observed_value: str) -> str:
    """Return a canonical value derived only from one grounded source phrase.

    Role and location preserve source spelling after whitespace cleanup because
    changing either can alter identity. Seniority, skills and remote/work-model
    phrases are case-normalized so downstream comparisons are stable while the
    evidence reference retains the verbatim observed value for audit.

    Explicit years-of-experience text is not a seniority label and therefore
    fails closed rather than being converted into junior/senior semantics.
    """

    field_name = str(field or "").strip().casefold()
    if field_name not in SEMANTIC_FIELD_NAMES:
        raise ValueError(f"unsupported Detail Semantics normalization field: {field_name or '<empty>'}")

    cleaned = " ".join(str(observed_value or "").split()).strip()
    if not cleaned:
        raise ValueError("observed Detail Semantics value must be non-empty")

    if field_name == "seniority" and _YEARS_OF_EXPERIENCE.match(cleaned):
        raise ValueError("years-of-experience evidence must not be normalized into seniority")

    if field_name in {"seniority", "skills", "remote"}:
        return cleaned.casefold()
    return cleaned


__all__ = ["normalize_detail_semantic_value"]
