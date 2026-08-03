"""Bridge symbol-aware brand surfaces into origin identity scoring.

The adaptive URL generator already preserves digits and verbalizes symbols such
as ``1&1`` -> ``1and1``. The legacy origin scorer tokenizes the display name
independently and can therefore discard the same brand completely. That creates
an impossible contract: the default finder generates a candidate URL that the
identity gate can never accept.

This module installs a narrow, idempotent extension of the existing identity
function. It only adds domain-safe tokens derived from the same generic brand
surface contract used by adaptive discovery. Purely numeric and generic tokens
remain excluded. Existing identity tokens and all downstream thresholds stay
unchanged.
"""

from __future__ import annotations

import re
from typing import Callable

from src.search_intelligence.adaptive_origin_search import brand_surface_variants
import src.search_intelligence.origin_source_discovery_agent as origin_agent

IdentityFunction = Callable[..., tuple[str, ...]]

_ORIGINAL_ATTRIBUTE = "_symbol_brand_original_company_identity_tokens"
_INSTALL_MARKER = "_symbol_brand_identity_bridge_installed"


def symbol_brand_identity_tokens(
    *,
    company_name: str,
    company_key: str | None = None,
) -> tuple[str, ...]:
    """Return distinctive domain-safe identity tokens for symbol brands."""

    tokens: list[str] = []
    for variant in brand_surface_variants(
        company_name=company_name,
        company_key=company_key,
    ):
        compact = re.sub(r"[^a-z0-9]+", "", variant.lower())
        if (
            len(compact) < 2
            or compact.isdigit()
            or compact in origin_agent.LEGAL_OR_GENERIC_TOKENS
            or compact in {"and", "und", "plus", "at"}
            or compact in tokens
        ):
            continue
        tokens.append(compact)
    return tuple(tokens)


def install_symbol_brand_identity_bridge() -> None:
    """Extend the legacy scorer once, preserving its existing contract."""

    if bool(getattr(origin_agent, _INSTALL_MARKER, False)):
        return

    original: IdentityFunction = origin_agent.company_identity_tokens
    setattr(origin_agent, _ORIGINAL_ATTRIBUTE, original)

    def company_identity_tokens_with_symbol_brands(
        *,
        company_key: str,
        company_name: str,
        source_family_candidate: str | None = None,
    ) -> tuple[str, ...]:
        existing = list(
            original(
                company_key=company_key,
                company_name=company_name,
                source_family_candidate=source_family_candidate,
            )
        )
        for token in symbol_brand_identity_tokens(
            company_name=company_name,
            company_key=company_key,
        ):
            if token not in existing:
                existing.append(token)
        return tuple(existing)

    origin_agent.company_identity_tokens = company_identity_tokens_with_symbol_brands
    setattr(origin_agent, _INSTALL_MARKER, True)


__all__ = [
    "install_symbol_brand_identity_bridge",
    "symbol_brand_identity_tokens",
]
