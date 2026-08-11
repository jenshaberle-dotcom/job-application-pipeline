from __future__ import annotations

from collections.abc import Callable

from src.search_intelligence.origin_source_discovery_agent import (
    GENERATED_PROVIDER_KIND,
    LOCALITY_TOKENS,
    OriginDiscoveryCandidate,
    company_identity_tokens,
)


DEFAULT_TLDS = ("de", "com", "eu", "group")


def _distinctive_brand_bases(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None,
) -> tuple[str, ...]:
    tokens = [
        token
        for token in company_identity_tokens(
            company_key=company_key,
            company_name=company_name,
            source_family_candidate=source_family_candidate,
        )
        if token not in LOCALITY_TOKENS
    ]
    if not tokens:
        return ()

    bases: list[str] = []
    for base in (
        tokens[0],
        "-".join(tokens[:2]),
        "-".join(tokens[:3]),
    ):
        if len(base) >= 2 and base not in bases:
            bases.append(base)
    return tuple(bases)


def _job_host(host: str) -> str:
    return f"https://jobs.{host}/"


def _www_stellenangebote(host: str) -> str:
    return f"https://www.{host}/stellenangebote"


def _www_karriere(host: str) -> str:
    return f"https://www.{host}/karriere"


def _root_stellenangebote(host: str) -> str:
    return f"https://{host}/stellenangebote"


def _root_karriere(host: str) -> str:
    return f"https://{host}/karriere"


def _careers_host(host: str) -> str:
    return f"https://careers.{host}/"


HYPOTHESIS_SHAPES: tuple[Callable[[str], str], ...] = (
    _job_host,
    _www_stellenangebote,
    _www_karriere,
    _root_stellenangebote,
    _root_karriere,
    _careers_host,
)


def generate_bounded_origin_candidate_hypotheses(
    *,
    company_key: str,
    company_name: str,
    source_family_candidate: str | None = None,
    max_candidates: int,
    tlds: tuple[str, ...] = DEFAULT_TLDS,
) -> tuple[OriginDiscoveryCandidate, ...]:
    """Generate source-neutral employer-origin hypotheses with breadth before depth.

    Small budgets first cover a distinctive leading brand across multiple TLDs and
    high-value career host/path shapes. Existing origin identity scoring remains
    responsible for rejecting lookalikes; this helper only improves hypothesis
    diversity and never performs network or persistence work.
    """

    if max_candidates <= 0:
        return ()

    bases = _distinctive_brand_bases(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family_candidate,
    )
    candidates: list[OriginDiscoveryCandidate] = []
    seen: set[str] = set()

    for shape_index, shape in enumerate(HYPOTHESIS_SHAPES):
        for base_index, base in enumerate(bases):
            for tld_index, tld in enumerate(tlds):
                host = f"{base}.{tld}"
                url = shape(host)
                if url in seen:
                    continue
                seen.add(url)
                candidates.append(
                    OriginDiscoveryCandidate(
                        url=url,
                        provider=GENERATED_PROVIDER_KIND,
                        reason="bounded diverse brand/TLD employer-origin hypothesis",
                        source_priority=20 + shape_index * 10 + base_index * 2 + tld_index,
                    )
                )
                if len(candidates) >= max_candidates:
                    return tuple(candidates)

    return tuple(candidates)
