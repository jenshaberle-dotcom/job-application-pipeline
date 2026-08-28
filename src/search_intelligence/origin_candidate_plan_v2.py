from __future__ import annotations

import re
from typing import Sequence

from src.search_intelligence.origin_source_discovery_agent import (
    LOCALITY_TOKENS,
    OriginDiscoveryCandidate,
    acronym_tokens,
    company_identity_tokens,
    corporate_identity_aliases,
    normalize_candidate_url,
    tokenize,
)

GENERATED_PROVIDER_KIND_V2 = "generated_company_domain_candidate_v2"
PRIMARY_TLDS = ("de", "com")
SECONDARY_TLDS = ("eu", "group")

# Ordered surface shapes. Root comes first deliberately: an employer homepage
# that visibly exposes career/job navigation is valid origin evidence and lets
# downstream delegation/inventory layers decide what is actually required.
SURFACE_SHAPES = (
    "root",
    "karriere",
    "jobs",
    "careers",
    "career",
    "job_host",
    "careers_host",
    "stellenangebote",
)


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _join(tokens: Sequence[str], *, compact: bool = False, limit: int = 4) -> str:
    parts = [token for token in tokens[:limit] if token]
    return "".join(parts) if compact else "-".join(parts)


def _add_base(result: list[str], value: str) -> None:
    base = value.strip().casefold().strip("-.")
    if len(base) < 2 or base in result:
        return
    result.append(base)


def prioritized_domain_bases(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
) -> tuple[str, ...]:
    """Return evidence-derived domain bases in breadth-oriented priority order.

    This intentionally promotes explicit short brands/acronyms even when the
    same token is already part of the identity-token set. The previous planner
    removed those duplicates before domain planning, which caused KKH/MTU/IPH
    style hypotheses to disappear or land hundreds of candidates behind the
    active probe budget.
    """

    identity = list(
        company_identity_tokens(
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
        )
    )
    acronyms = list(acronym_tokens(company_name))
    localities = [token for token in identity if token in LOCALITY_TOKENS]
    non_local = [token for token in identity if token not in LOCALITY_TOKENS]

    bases: list[str] = []

    # Existing explicit corporate aliases remain highest-confidence evidence.
    for alias in corporate_identity_aliases(company_key, company_name):
        alias_tokens = [token for token in tokenize(alias) if token]
        _add_base(bases, _join(alias_tokens, limit=3))
        if len(alias_tokens) == 1:
            _add_base(bases, alias_tokens[0])

    # Explicit all-caps/parenthesized short brands are strong generic evidence.
    for acronym in acronyms:
        _add_base(bases, acronym)
        for locality in localities[:1]:
            _add_base(bases, f"{acronym}-{locality}")

    # Single-token employers should not be forced through synthetic long forms.
    if len(non_local) == 1:
        _add_base(bases, non_local[0])

    # Multi-token brand forms: dashed and compact variants get equal opportunity.
    if non_local:
        _add_base(bases, _join(non_local[:2]))
        _add_base(bases, _join(non_local[:2], compact=True))
        _add_base(bases, _join(non_local))
        _add_base(bases, _join(non_local, compact=True))

    # The normalized candidate key is useful, but it must not monopolize budget.
    _add_base(bases, _compact(company_key))

    return tuple(bases)


def _surface_url(host: str, shape: str) -> str:
    if shape == "root":
        return f"https://{host}/"
    if shape == "karriere":
        return f"https://{host}/karriere"
    if shape == "jobs":
        return f"https://{host}/jobs"
    if shape == "careers":
        return f"https://{host}/careers"
    if shape == "career":
        return f"https://{host}/career"
    if shape == "job_host":
        return f"https://jobs.{host}/"
    if shape == "careers_host":
        return f"https://careers.{host}/"
    if shape == "stellenangebote":
        return f"https://{host}/stellenangebote"
    raise ValueError(f"unsupported surface shape: {shape}")


def generate_company_url_candidates_v2(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    max_candidates: int = 30,
) -> tuple[OriginDiscoveryCandidate, ...]:
    """Generate bounded candidates breadth-first across independent host families.

    The old planner exhausted many path variants on the first host family before
    moving to another brand/TLD hypothesis. V2 instead gives each evidence-derived
    base/TLD family one surface attempt before deepening any family.
    """

    if max_candidates <= 0:
        return ()

    bases = prioritized_domain_bases(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    )
    if not bases:
        return ()

    host_families: list[tuple[str, int]] = []
    seen_hosts: set[str] = set()

    # Primary German/global TLDs are explored before secondary TLDs, but breadth
    # is preserved across all bases within each TLD tier.
    for tlds, priority in ((PRIMARY_TLDS, 20), (SECONDARY_TLDS, 35)):
        for base in bases:
            for tld in tlds:
                host = f"{base}.{tld}"
                if host not in seen_hosts:
                    seen_hosts.add(host)
                    host_families.append((host, priority))

    result: list[OriginDiscoveryCandidate] = []
    seen_urls: set[str] = set()

    # Round-robin by surface shape: every host family gets a root chance before
    # any family receives a second path candidate.
    for shape_index, shape in enumerate(SURFACE_SHAPES):
        for host, base_priority in host_families:
            raw = _surface_url(host, shape)
            normalized = normalize_candidate_url(raw)
            if normalized is None or normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            result.append(
                OriginDiscoveryCandidate(
                    url=normalized,
                    provider=GENERATED_PROVIDER_KIND_V2,
                    reason=f"breadth-first company-domain hypothesis: {shape}",
                    source_priority=base_priority + shape_index,
                    evidence={
                        "planner": "breadth_first_v2",
                        "surface_shape": shape,
                    },
                )
            )
            if len(result) >= max_candidates:
                return tuple(result)

    return tuple(result)
