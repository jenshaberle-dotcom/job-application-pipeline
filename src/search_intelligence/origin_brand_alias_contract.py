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
import src.search_intelligence.origin_source_discovery_agent as origin_agent

_INSTALL_MARKER = "_origin_brand_alias_contract_installed"
_ORIGINAL_VARIANTS = "_origin_brand_alias_original_brand_surface_variants"
_ORIGINAL_TOKENS = "_origin_brand_alias_original_company_identity_tokens"

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
_LEGAL_TAIL_PATTERN = re.compile(
    r"\b(?:gmbh|se|ag|kg|kgaa|mbh|ohg|ug|inc|ltd|limited|corp|corporation)\b.*$",
    re.IGNORECASE,
)


def _trim_legal_tail(value: str) -> str:
    """Remove the first legal-form suffix and everything after it."""

    return _LEGAL_TAIL_PATTERN.sub("", str(value or "")).strip(" &,+@.-")


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
    trimmed = _trim_legal_tail(raw) or raw
    aliases: list[str] = []

    first_surface = trimmed.split(maxsplit=1)[0] if trimmed else ""
    if first_surface and (
        re.search(r"[.&+@]", first_surface)
        or re.search(r"[A-Za-z]\d|\d[A-Za-z]", first_surface)
    ):
        compact = _compact_symbol_surface(first_surface)
        if compact and len(compact) >= 2:
            aliases.append(compact)

    raw_tokens = [
        token
        for token in re.split(r"[^A-Za-z0-9]+", trimmed)
        if token
    ]
    has_internal_camel = any(re.search(r"[a-z][A-Z]", token) for token in raw_tokens)
    words = _camel_words(trimmed)
    lowered = [word.lower() for word in words if word.lower() not in _ALIAS_STOPWORDS]
    if len(lowered) >= 2 and has_internal_camel:
        initialism = "".join(part[0] for part in lowered if part)
        # Three-plus-letter initials are useful market aliases; two letters are
        # too collision-prone. Emit the initialism before longer variants so a
        # bounded four-query Basic search spends its fourth query on it.
        if 3 <= len(initialism) <= 8 and not initialism.isdigit():
            aliases.append(initialism)
        aliases.extend(("-".join(lowered), "".join(lowered)))

    result: list[str] = []
    for alias in aliases:
        normalized = re.sub(r"[^a-z0-9-]+", "", alias.lower()).strip("-")
        if len(normalized) < 2 or normalized in result:
            continue
        result.append(normalized)
    return tuple(result[:4])


def _identity_alias_tokens(company_name: str) -> tuple[str, ...]:
    """Return distinctive compact and long split tokens for identity scoring."""

    tokens: list[str] = []
    for alias in market_brand_aliases(company_name):
        compact = re.sub(r"[^a-z0-9]+", "", alias.lower())
        if len(compact) >= 3 and compact not in tokens:
            tokens.append(compact)
        for part in re.split(r"[^a-z0-9]+", alias.lower()):
            if (
                len(part) >= 3
                and part not in origin_agent.LEGAL_OR_GENERIC_TOKENS
                and part not in {"and", "und", "the", "der", "die", "das"}
                and part not in tokens
            ):
                tokens.append(part)
    return tuple(tokens)


def install_origin_brand_alias_contract() -> None:
    """Patch brand surfaces and identity tokens exactly once."""

    if bool(getattr(adaptive, _INSTALL_MARKER, False)):
        return

    original_variants = adaptive.brand_surface_variants
    original_tokens = origin_agent.company_identity_tokens
    setattr(adaptive, _ORIGINAL_VARIANTS, original_variants)
    setattr(origin_agent, _ORIGINAL_TOKENS, original_tokens)

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

    def company_identity_tokens_with_market_aliases(
        *,
        company_key: str,
        company_name: str,
        source_family_candidate: str | None = None,
    ) -> tuple[str, ...]:
        existing = list(
            original_tokens(
                company_key=company_key,
                company_name=company_name,
                source_family_candidate=source_family_candidate,
            )
        )
        for token in _identity_alias_tokens(company_name):
            if token not in existing:
                existing.append(token)
        return tuple(existing)

    adaptive.brand_surface_variants = brand_surface_variants_with_market_aliases
    origin_agent.company_identity_tokens = company_identity_tokens_with_market_aliases
    setattr(adaptive, _INSTALL_MARKER, True)


__all__ = [
    "install_origin_brand_alias_contract",
    "market_brand_aliases",
]
