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

# Generic breadth shapes. These are deliberately evaluated only after a small
# evidence-backed fast lane for explicit aliases/short brands. This prevents
# both historical failure modes: depth-first path monopolization and V2 root-only
# breadth monopolization.
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
STRONG_SURFACE_SHAPES = (
    "job_host",
    "careers_host",
    "root",
)
MAX_STRONG_BASES = 2


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


def _explicit_strong_bases(
    *,
    company_key: str,
    company_name: str,
) -> tuple[str, ...]:
    """Return only evidence-strong domain bases for the bounded fast lane.

    Strong means explicitly observed in the employer identity as a configured
    corporate alias or an all-caps/parenthesized short brand. No inferred parent,
    provider, tenant or opaque route is introduced here.
    """

    result: list[str] = []
    localities = [token for token in tokenize(company_name) if token in LOCALITY_TOKENS]

    for alias in corporate_identity_aliases(company_key, company_name):
        alias_tokens = [token for token in tokenize(alias) if token]
        _add_base(result, _join(alias_tokens, limit=3))
        if len(alias_tokens) == 1:
            _add_base(result, alias_tokens[0])

    for acronym in acronym_tokens(company_name):
        _add_base(result, acronym)
        for locality in localities[:1]:
            _add_base(result, f"{acronym}-{locality}")

    return tuple(result)


def prioritized_domain_bases(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
) -> tuple[str, ...]:
    """Return evidence-derived domain bases in breadth-oriented priority order.

    Explicit short brands/acronyms remain available even when already present in
    the identity-token set. The legacy planner removed those duplicates and could
    push KKH/MTU/IPH-style hypotheses hundreds of candidates behind the budget.
    """

    identity = list(
        company_identity_tokens(
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
        )
    )
    localities = [token for token in identity if token in LOCALITY_TOKENS]
    non_local = [token for token in identity if token not in LOCALITY_TOKENS]

    bases: list[str] = []

    for base in _explicit_strong_bases(
        company_key=company_key,
        company_name=company_name,
    ):
        _add_base(bases, base)

    if len(non_local) == 1:
        _add_base(bases, non_local[0])

    if non_local:
        _add_base(bases, _join(non_local[:2]))
        _add_base(bases, _join(non_local[:2], compact=True))
        _add_base(bases, _join(non_local))
        _add_base(bases, _join(non_local, compact=True))

    # Preserve the useful acronym+locality form even when the locality came from
    # a normalized key/source-family rather than the literal company name.
    for acronym in acronym_tokens(company_name):
        for locality in localities[:1]:
            _add_base(bases, f"{acronym}-{locality}")

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


def _append_candidate(
    result: list[OriginDiscoveryCandidate],
    seen_urls: set[str],
    *,
    host: str,
    shape: str,
    priority: int,
    reason: str,
    phase: str,
    max_candidates: int,
) -> bool:
    raw = _surface_url(host, shape)
    normalized = normalize_candidate_url(raw)
    if normalized is None or normalized in seen_urls:
        return False
    seen_urls.add(normalized)
    result.append(
        OriginDiscoveryCandidate(
            url=normalized,
            provider=GENERATED_PROVIDER_KIND_V2,
            reason=reason,
            source_priority=priority,
            evidence={
                "planner": "evidence_tiered_breadth_v2",
                "planner_phase": phase,
                "surface_shape": shape,
            },
        )
    )
    return len(result) >= max_candidates


def generate_company_url_candidates_v2(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    max_candidates: int = 30,
) -> tuple[OriginDiscoveryCandidate, ...]:
    """Generate bounded candidates using evidence-tiered breadth.

    Phase A reserves at most half of the active budget (and at most two explicit
    strong bases) for high-value career surfaces of aliases/acronyms. Phase B
    then preserves breadth across independent base/TLD host families. Remaining
    budget may deepen those families. Authority/scoring/probe rules remain in the
    existing discovery layer and are unchanged by this planner.
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

    strong_bases = tuple(
        base
        for base in _explicit_strong_bases(
            company_key=company_key,
            company_name=company_name,
        )
        if base in bases
    )[:MAX_STRONG_BASES]

    result: list[OriginDiscoveryCandidate] = []
    seen_urls: set[str] = set()

    # Never let the fast lane consume more than half of the total budget. For a
    # 12-candidate run this yields six high-value attempts at most, leaving six
    # independent breadth attempts even for alias-rich employers.
    strong_budget = min(max_candidates // 2, len(strong_bases) * len(STRONG_SURFACE_SHAPES))
    strong_emitted = 0
    for shape_index, shape in enumerate(STRONG_SURFACE_SHAPES):
        for base in strong_bases:
            # Job/career subdomains are overwhelmingly global in the current
            # evidence set; root hypotheses still cover both DE and COM below.
            tlds = ("com",) if shape in {"job_host", "careers_host"} else PRIMARY_TLDS
            for tld in tlds:
                if strong_emitted >= strong_budget:
                    break
                if _append_candidate(
                    result,
                    seen_urls,
                    host=f"{base}.{tld}",
                    shape=shape,
                    priority=10 + shape_index,
                    reason=f"evidence-strong alias/short-brand hypothesis: {shape}",
                    phase="strong_fast_lane",
                    max_candidates=max_candidates,
                ):
                    return tuple(result)
                strong_emitted += 1
            if strong_emitted >= strong_budget:
                break
        if strong_emitted >= strong_budget:
            break

    host_families: list[tuple[str, int]] = []
    seen_hosts: set[str] = set()
    for tlds, priority in ((PRIMARY_TLDS, 20), (SECONDARY_TLDS, 35)):
        for base in bases:
            for tld in tlds:
                host = f"{base}.{tld}"
                if host not in seen_hosts:
                    seen_hosts.add(host)
                    host_families.append((host, priority))

    # Phase B1: independent root breadth. This is the main antidote to the old
    # depth-first host-family monoculture.
    for host, base_priority in host_families:
        if _append_candidate(
            result,
            seen_urls,
            host=host,
            shape="root",
            priority=base_priority,
            reason="breadth-first company-domain hypothesis: root",
            phase="host_breadth",
            max_candidates=max_candidates,
        ):
            return tuple(result)

    # Phase B2: only after each reachable host family had a root opportunity do
    # we spend remaining budget on deeper generic career surfaces.
    for shape_index, shape in enumerate(SURFACE_SHAPES[1:], start=1):
        for host, base_priority in host_families:
            if _append_candidate(
                result,
                seen_urls,
                host=host,
                shape=shape,
                priority=base_priority + shape_index,
                reason=f"breadth-first company-domain hypothesis: {shape}",
                phase="selective_depth",
                max_candidates=max_candidates,
            ):
                return tuple(result)

    return tuple(result)
