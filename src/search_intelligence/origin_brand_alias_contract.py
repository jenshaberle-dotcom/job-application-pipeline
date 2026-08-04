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

from src.search_intelligence import adaptive_origin_search as adaptive

_INSTALL_MARKER = "_origin_brand_alias_contract_installed"
_ORIGINAL_VARIANTS = "_origin_brand_alias_original_brand_surface_variants"

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
    "group",
    "gruppe",
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


def market_brand_aliases(company_name: str) -> tuple[str, ...]:
    """Return high-value generic aliases in search priority order."""

    raw = str(company_name or "").strip()
    aliases: list[str] = []

    first_surface = raw.split(maxsplit=1)[0] if raw else ""
    if first_surface and (
        re.search(r"[.&+@]", first_surface)
        or re.search(r"[A-Za-z]\d|\d[A-Za-z]", first_surface)
    ):
        compact = adaptive._domain_surface(first_surface)
        if compact and len(compact) >= 2:
            aliases.append(compact)

    words = _camel_words(raw)
    lowered = [word.lower() for word in words if word.lower() not in _ALIAS_STOPWORDS]
    if len(lowered) >= 2:
        dashed = "-".join(lowered)
        compact = "".join(lowered)
        # Internal CamelCase is a strong market-brand signal. Preserve both the
        # human/domain hyphen form and the compact form.
        has_internal_camel = any(
            re.search(r"[a-z][A-Z]", token)
            for token in re.split(r"[^A-Za-z0-9]+", raw)
            if token
        )
        if has_internal_camel:
            aliases.extend((dashed, compact))

        initialism = "".join(part[0] for part in lowered if part)
        # Two-letter initials are too collision-prone. Three to eight letters
        # cover market names such as CompuGroup Medical -> cgm.
        if 3 <= len(initialism) <= 8 and not initialism.isdigit():
            aliases.append(initialism)

    result: list[str] = []
    for alias in aliases:
        normalized = re.sub(r"[^a-z0-9-]+", "", alias.lower()).strip("-")
        if len(normalized) < 2 or normalized in result:
            continue
        result.append(normalized)
    return tuple(result[:4])


def install_origin_brand_alias_contract() -> None:
    """Patch brand-surface generation exactly once."""

    if bool(getattr(adaptive, _INSTALL_MARKER, False)):
        return

    original = adaptive.brand_surface_variants
    setattr(adaptive, _ORIGINAL_VARIANTS, original)

    def brand_surface_variants_with_market_aliases(
        *,
        company_name: str,
        company_key: str | None = None,
    ) -> tuple[str, ...]:
        existing = list(
            original(company_name=company_name, company_key=company_key)
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

    adaptive.brand_surface_variants = brand_surface_variants_with_market_aliases
    setattr(adaptive, _INSTALL_MARKER, True)


__all__ = [
    "install_origin_brand_alias_contract",
    "market_brand_aliases",
]
