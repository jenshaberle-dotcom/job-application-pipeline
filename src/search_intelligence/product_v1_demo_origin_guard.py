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

EMPLOYER_ORIGIN_SOURCE_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
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


def evaluate_demo_origin_guard(
    *,
    source_url: str | None,
    canonical_source_type: str | None,
    lifecycle_status: str | None,
    origin_validation_status: str | None,
    product_readiness_status: str | None,
    source_name: str | None = None,
) -> DemoOriginGuard:
    """Fail closed for current Product actions while preserving discovery provenance.

    ``source_name`` is intentionally not an authority gate. A vacancy may have been
    discovered by BA, StepStone or another market sensor and later resolved onto an
    Employer-Origin URL. Only the final Product action URL and current Product truth
    decide actionability here.
    """

    del source_name  # discovery provenance is diagnostic, never Product authority
    url = (source_url or "").strip() or None
    if str(lifecycle_status or "") != "active_confirmed":
        return DemoOriginGuard(False, "current_lifecycle_not_confirmed", None)
    if str(origin_validation_status or "") != "validated":
        return DemoOriginGuard(False, "employer_origin_not_validated", None)
    if str(canonical_source_type or "") not in EMPLOYER_ORIGIN_SOURCE_TYPES:
        return DemoOriginGuard(False, "source_is_not_employer_origin", None)
    if not _absolute_https(url):
        return DemoOriginGuard(False, "employer_origin_https_url_required", None)
    if _aggregator_host(url):
        return DemoOriginGuard(False, "aggregator_url_cannot_be_product_action_url", None)
    if str(product_readiness_status or "") == "blocked_inactive":
        return DemoOriginGuard(False, "product_is_inactive", None)
    return DemoOriginGuard(True, "current_employer_origin_confirmed", url)
