"""Install bounded market-brand aliases before origin search/scoring.

Company inventory names are legal/display names, while career hosts often use a
short market brand. The generic search contract already handles symbol brands
such as ``1&1`` but still misses common surfaces such as:

- dotted brands: ``E.ON`` -> ``eon``;
- internal CamelCase: ``bridgingIT`` -> ``bridging-it``;
- stable initials from a multi-part market name: ``CompuGroup Medical`` -> ``cgm``.

Aliases are derived mechanically. No company or URL is allowlisted. The patch is
installed before the symbol-brand identity bridge so the same aliases are used by
query generation and identity scoring.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from src.search_intelligence import adaptive_origin_search as adaptive
import src.search_intelligence.origin_source_discovery_agent as origin_agent

_INSTALL_MARKER = "_origin_brand_alias_contract_installed"
_ORIGINAL_VARIANTS = "_origin_brand_alias_original_brand_surface_variants"
_ORIGINAL_SCORE = "_origin_brand_alias_original_company_identity_score"

_ALIAS_STOPWORDS = {
    "ag",
    "se",
    "gmbh",
    "kg",
    "kgaa",
    "mbh",
    "co",
    "ohg",
    "ug",
    "inc",
    "ltd",
    "limited",
    "corp",
    "corporation",
}


def _camel_words(value: str) -> tuple[str, ...]:
    words: list[str] = []
    for raw in re.split(r"[^A-Za-z0-9]+", str(value or "")):
        if not raw:
            continue
        parts = re.findall(
            r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|[A-Z]+|\d+",
            raw,
        )
        words.extend(part for part in parts if part)
    return tuple(words)


def _compact_symbol_surface(value: str) -> str:
    """Compact a displayed brand before legal-token stripping can erase it."""

    text = adaptive._ascii(value)
    text = text.replace("&", "and").replace("+", "plus").replace("@", "at")
    return re.sub(r"[^a-z0-9]+", "", text)


def market_brand_aliases(company_name: str) -> tuple[str, ...]:
    """Return high-value generic aliases in search priority order."""

    raw = str(company_name or "").strip()
    aliases: list[str] = []

    first_surface = raw.split(maxsplit=1)[0] if raw else ""
    if first_surface and (
        re.search(r"[.&+@]", first_surface)
        or re.search(r"[A-Za-z]\d|\d[A-Za-z]", first_surface)
    ):
        compact = _compact_symbol_surface(first_surface)
        if compact and len(compact) >= 2:
            aliases.append(compact)

    raw_tokens = [
        token
        for token in re.split(r"[^A-Za-z0-9]+", raw)
        if token
    ]
    has_internal_camel = any(re.search(r"[a-z][A-Z]", token) for token in raw_tokens)
    words = _camel_words(raw)
    lowered = [word.lower() for word in words if word.lower() not in _ALIAS_STOPWORDS]
    if len(lowered) >= 2:
        dashed = "-".join(lowered)
        compact = "".join(lowered)
        # Internal CamelCase is a strong market-brand signal. Preserve both the
        # human/domain hyphen form and the compact form.
        if has_internal_camel:
            aliases.extend((dashed, compact))

        initialism = "".join(part[0] for part in lowered if part)
        # Initialisms are emitted only when internal CamelCase proves the word
        # boundary. This avoids generic acronyms for ordinary multi-word names.
        if has_internal_camel and 3 <= len(initialism) <= 8 and not initialism.isdigit():
            aliases.append(initialism)

    result: list[str] = []
    for alias in aliases:
        normalized = re.sub(r"[^a-z0-9-]+", "", alias.lower()).strip("-")
        if len(normalized) < 2 or normalized in result:
            continue
        result.append(normalized)
    return tuple(result[:4])


def _compact_alias_match(hostname: str, aliases: tuple[str, ...]) -> str | None:
    labels = [re.sub(r"[^a-z0-9]+", "", label.lower()) for label in hostname.split(".")]
    for alias in aliases:
        compact = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if len(compact) < 3:
            continue
        for label in labels:
            if compact == label or (len(compact) >= 5 and compact in label):
                return alias
    return None


def install_origin_brand_alias_contract() -> None:
    """Patch brand-surface generation and compact host identity exactly once."""

    if bool(getattr(adaptive, _INSTALL_MARKER, False)):
        return

    original_variants = adaptive.brand_surface_variants
    original_score = origin_agent.company_identity_score
    setattr(adaptive, _ORIGINAL_VARIANTS, original_variants)
    setattr(origin_agent, _ORIGINAL_SCORE, original_score)

    def brand_surface_variants_with_market_aliases(
        *,
        company_name: str,
        company_key: str | None = None,
    ) -> tuple[str, ...]:
        existing = list(
            original_variants(company_name=company_name, company_key=company_key)
        )
        if not existing:
            return tuple(market_brand_aliases(company_name))

        ordered = [existing[0]]
        ordered.extend(market_brand_aliases(company_name))
        ordered.extend(existing[1:])

        result: list[str] = []
        for item in ordered:
            if item and item not in result:
                result.append(item)
        return tuple(result[:8])

    def company_identity_score_with_compact_market_alias(
        *,
        url: str | None,
        company_key: str,
        company_name: str,
        source_family_candidate: str | None = None,
    ) -> tuple[float, tuple[str, ...]]:
        score, reasons = original_score(
            url=url,
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
        )
        normalized = origin_agent.normalize_candidate_url(url)
        if normalized is None:
            return score, reasons
        hostname = str(urlparse(normalized).hostname or "").lower()
        matched = _compact_alias_match(hostname, market_brand_aliases(company_name))
        if matched is None:
            return score, reasons
        return max(score, 0.55), tuple(
            (*reasons, f"compact market-brand alias found in host: {matched}")
        )

    adaptive.brand_surface_variants = brand_surface_variants_with_market_aliases
    origin_agent.company_identity_score = company_identity_score_with_compact_market_alias
    setattr(adaptive, _INSTALL_MARKER, True)


__all__ = [
    "install_origin_brand_alias_contract",
    "market_brand_aliases",
]
