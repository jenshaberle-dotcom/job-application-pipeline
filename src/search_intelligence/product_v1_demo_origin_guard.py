from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


AGGREGATOR_HOST_SUFFIXES = (
    "arbeitsagentur.de",
    "gute-jobs.de",
    "stepstone.de",
    "indeed.com",
    "linkedin.com",
)

AGGREGATOR_SOURCE_FAMILIES = frozenset(
    {
        "bundesagentur_fuer_arbeit",
        "gute_jobs",
        "gute-jobs",
        "stepstone",
        "indeed",
        "linkedin",
    }
)

# Compatibility vocabulary for grouped discovery diagnostics:
# source_is_discovery_or_aggregator
EMPLOYER_ORIGIN_SOURCE_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)

KNOWN_EMPLOYER_ORIGIN_SOURCE_PREFIXES = (
    "personio:",
    "successfactors:",
    "greenhouse:",
    "workday:",
    "enercity:",
    "hdi:",
    "finanz_informatik:",
)


@dataclass(frozen=True)
class DemoOriginGuard:
    eligible: bool
    reason: str
    employer_origin_url: str | None


def _absolute_https(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlsplit(url.strip())
    return parsed.scheme == "https" and bool(parsed.netloc)


def _host(url: str | None) -> str:
    if not url:
        return ""
    return (urlsplit(url.strip()).hostname or "").casefold()


def _aggregator_host(url: str | None) -> bool:
    host = _host(url)
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in AGGREGATOR_HOST_SUFFIXES
    )


def _source_family(source_name: str | None) -> str:
    return str(source_name or "").strip().casefold().split(":", 1)[0]


def _known_origin_source(source_name: str | None) -> bool:
    normalized = str(source_name or "").strip().casefold()
    return any(
        normalized.startswith(prefix)
        for prefix in KNOWN_EMPLOYER_ORIGIN_SOURCE_PREFIXES
    )


def evaluate_demo_origin_guard(
    *,
    source_url: str | None,
    canonical_source_type: str | None,
    lifecycle_status: str | None,
    origin_validation_status: str | None,
    product_readiness_status: str | None,
    source_name: str | None = None,
    resolved_employer_origin_url: str | None = None,
    resolved_origin_verified: bool = False,
) -> DemoOriginGuard:
    """Resolve one current Product action URL without confusing discovery with origin."""

    discovery_url = (source_url or "").strip() or None
    resolved_url = (resolved_employer_origin_url or "").strip() or None

    if str(lifecycle_status or "") != "active_confirmed":
        return DemoOriginGuard(False, "current_lifecycle_not_confirmed", None)
    if str(origin_validation_status or "") != "validated":
        return DemoOriginGuard(False, "employer_origin_not_validated", None)
    if str(product_readiness_status or "") == "blocked_inactive":
        return DemoOriginGuard(False, "product_is_inactive", None)

    if resolved_origin_verified:
        if not _absolute_https(resolved_url):
            return DemoOriginGuard(False, "resolved_employer_origin_https_url_required", None)
        if _aggregator_host(resolved_url):
            return DemoOriginGuard(False, "aggregator_url_cannot_be_product_action_url", None)
        return DemoOriginGuard(True, "verified_employer_origin_resolution", resolved_url)

    if _aggregator_host(discovery_url):
        return DemoOriginGuard(False, "aggregator_url_cannot_be_product_action_url", None)
    if _source_family(source_name) in AGGREGATOR_SOURCE_FAMILIES:
        return DemoOriginGuard(False, "aggregator_source_is_discovery_only", None)

    source_type_valid = str(canonical_source_type or "") in EMPLOYER_ORIGIN_SOURCE_TYPES
    if not source_type_valid and not _known_origin_source(source_name):
        return DemoOriginGuard(False, "source_is_not_employer_origin", None)
    if not _absolute_https(discovery_url):
        return DemoOriginGuard(False, "employer_origin_https_url_required", None)
    return DemoOriginGuard(True, "current_employer_origin_confirmed", discovery_url)
