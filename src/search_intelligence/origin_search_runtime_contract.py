"""Install shared origin-search normalization and follow-up safeguards.

The URL finder has several entry points. This module keeps them on one runtime
contract before the staged controller is imported:

- symbol/numeric brand identity scoring is installed everywhere;
- legal suffix cleanup cannot leave dangling operators such as ``&``;
- site-follow-up queries are never generated for job boards, review sites,
  knowledge sites, lead databases, or shared ATS platform hosts.

The exclusions affect only *site-follow-up query generation*. A concrete tenant
URL on a shared ATS host may still be assessed and selected by the existing
identity and career-evidence gates.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.search_intelligence import adaptive_origin_search as adaptive
from src.search_intelligence.symbol_brand_identity_bridge import (
    install_symbol_brand_identity_bridge,
)

_INSTALL_MARKER = "_origin_search_runtime_contract_installed"
_ORIGINAL_STRIP = "_origin_search_original_strip_legal_suffixes"
_ORIGINAL_FOLLOWUP = "_origin_search_original_domain_followup_queries"

DANGLING_OPERATORS = {"&", "+", "@"}

# These domains may contain useful evidence or tenant URLs, but they are not
# employer corporate domains and must not seed broad ``site:...`` follow-ups.
FOLLOWUP_EXCLUDED_DOMAINS = (
    "wikipedia.org",
    "kununu.com",
    "glassdoor.com",
    "glassdoor.de",
    "stepstone.de",
    "linkedin.com",
    "indeed.com",
    "xing.com",
    "monster.de",
    "jobware.de",
    "stellenanzeigen.de",
    "xn--jobbrse-d1a.de",
    "jobboerse.de",
    "eujobs.co",
    "get-in-it.de",
    "rocketjobs.pl",
    "leadiq.com",
    "leading-employers.org",
    "arbeitnow.com",
    "datacareer.de",
    "talent.com",
    "jooble.org",
    "adzuna.de",
    "simplyhired.de",
    "ziprecruiter.com",
    # Shared ATS / recruiting platforms: concrete tenant URLs remain valid
    # candidates, but platform-wide site searches are noisy and unsafe.
    "smartrecruiters.com",
    "myworkdayjobs.com",
    "workdayjobs.com",
    "successfactors.com",
    "successfactors.eu",
    "sapsf.com",
    "sapsf.eu",
    "softgarden.io",
    "greenhouse.io",
    "lever.co",
    "personio.de",
    "rexx-systems.com",
    "onlyfy.jobs",
    "dvinci-hr.com",
)


def _matches_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def is_followup_excluded_domain(hostname: str | None) -> bool:
    host = str(hostname or "").lower().strip(".")
    return bool(host) and any(
        _matches_domain(host, domain) for domain in FOLLOWUP_EXCLUDED_DOMAINS
    )


def install_origin_search_runtime_contract() -> None:
    """Install the shared contract once per Python process."""

    if bool(getattr(adaptive, _INSTALL_MARKER, False)):
        install_symbol_brand_identity_bridge()
        return

    install_symbol_brand_identity_bridge()

    # Legal forms observed in the candidate inventory. Extending this set is
    # safer than turning legal words into brand/domain identity.
    adaptive.LEGAL_SUFFIXES.update(
        {
            "kgaa",
            "ev",
            "e",
            "v",
            "plc",
            "llc",
            "sa",
            "nv",
            "bv",
        }
    )

    original_strip = adaptive._strip_legal_suffixes
    original_followup = adaptive.domain_followup_queries
    setattr(adaptive, _ORIGINAL_STRIP, original_strip)
    setattr(adaptive, _ORIGINAL_FOLLOWUP, original_followup)

    def strip_legal_suffixes_without_dangling_operator(value: str) -> str:
        cleaned = original_strip(value)
        parts = cleaned.split()
        while parts and parts[0] in DANGLING_OPERATORS:
            parts.pop(0)
        while parts and parts[-1] in DANGLING_OPERATORS:
            parts.pop()
        return " ".join(parts)

    def guarded_domain_followup_queries(
        domains: Iterable[str],
        *,
        maximum: int = 4,
    ) -> tuple[str, ...]:
        filtered = [
            str(domain)
            for domain in domains
            if not is_followup_excluded_domain(str(domain))
        ]
        return original_followup(filtered, maximum=maximum)

    adaptive._strip_legal_suffixes = strip_legal_suffixes_without_dangling_operator
    adaptive.domain_followup_queries = guarded_domain_followup_queries
    setattr(adaptive, _INSTALL_MARKER, True)


__all__ = [
    "FOLLOWUP_EXCLUDED_DOMAINS",
    "install_origin_search_runtime_contract",
    "is_followup_excluded_domain",
]
